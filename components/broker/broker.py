"""Launch a single Claude Code smoke invocation through the local DPoP broker."""

import argparse
import asyncio
import hmac
import json
import logging
import os
import re
import secrets
import shutil
import signal
import socket
import ssl
import stat
import tempfile
import time
import uuid
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import jwt
import uvicorn
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request
from starlette.requests import ClientDisconnect
from starlette.responses import Response

from gateway import (
    BODY_LIMIT, Failure, Invocation, Trust, access_credential, enforce_policy, error_response,
    read_messages, strict_json, validate_access_token,
)
from lab_invoke import GATEWAY, ExchangeLogin, LoginError, ProofClient, exchange_token, login, tls_client

REPO = Path(__file__).resolve().parents[2]
LOG = logging.getLogger("uvicorn.error")
PROMPT = "Reply with the synthetic lab response."
CHILD_ENV = ("HOME", "PATH", "USER", "LOGNAME", "SHELL", "TERM", "LANG", "LC_ALL", "TMPDIR")


def audit(event, request_id, gateway_id=None):
    if gateway_id is None:
        LOG.info("broker event=%s broker_request_id=%s", event, request_id)
    else:
        LOG.info("broker event=%s broker_request_id=%s gateway_request_id=%s",
                 event, request_id, gateway_id)


def read_exchange_key(directory):
    if directory.is_symlink():
        raise ValueError("Expected an owner-only lab key directory")
    directory = directory.resolve(strict=True)
    if directory.is_relative_to(REPO):
        raise ValueError("Keep the lab key directory outside the repository")
    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(directory_fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError("Expected an owner-only lab key directory")
        fd = os.open("assertion.key", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
        with os.fdopen(fd, "rb") as file:
            info = os.fstat(file.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
                raise ValueError("Expected an owner-only lab assertion key")
            pem = file.read(65537)
    finally:
        os.close(directory_fd)
    if len(pem) > 65536:
        raise ValueError("Oversized assertion key")
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
        raise ValueError("Expected RSA lab assertion key")
    return key


def acquire(args, proof=None):
    signing = read_exchange_key(args.client_dir)
    with tls_client(args.keycloak_ca) as client:
        identity = ExchangeLogin(client)
        login(identity)
    audit("login_succeeded", uuid.uuid4().hex)
    subject = identity.subject_token
    del identity
    proof = proof if proof is not None else ProofClient()
    token = exchange_token(args, subject, proof, signing_key=signing)
    return token, proof


def https_client(ca):
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls.load_verify_locations(cafile=ca)
    return httpx.AsyncClient(verify=tls, trust_env=False, follow_redirects=False,
                             timeout=httpx.Timeout(15, connect=2))


@dataclass
class Session:
    token: str = field(repr=False)
    proof: ProofClient = field(repr=False)
    expiry: int
    secret: str = field(default_factory=lambda: secrets.token_urlsafe(32), repr=False)
    active: bool = True
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    def check_active(self):
        if not self.active or time.time() >= self.expiry:
            raise Failure(401, "session_expired", "Bearer")


class BrokerInvocation(Invocation):
    upstream_name = "gateway"

    def __init__(self, gateway, session, body, stream, query, request_id):
        super().__init__(gateway, None, body, stream, query, request_id)
        self.session = session

    def report(self, event):
        audit(event, self.request_id)

    async def forward(self, scope, receive, send):
        async with self.session.lock:
            self.session.check_active()
            await super().forward(scope, receive, send)

    async def open_upstream(self, media):
        url = GATEWAY + ("?beta=true" if self.query else "")
        for attempt in range(2):
            self.session.check_active()
            headers = {
                "authorization": f"DPoP {self.session.token}",
                "dpop": self.session.proof.sign(GATEWAY, self.session.token),
                "content-type": "application/json", "accept": media, "accept-encoding": "identity",
            }
            response = await self.client.send(httpx.Request("POST", url, headers=headers,
                                                           content=self.body), stream=True)
            ids = response.headers.get_list("request-id")
            valid_id = ids[0] if len(ids) == 1 and re.fullmatch(r"[0-9a-f]{32}", ids[0]) else None
            challenge = (response.status_code == 401 and response.headers.get_list("www-authenticate")
                         == ['DPoP error="use_dpop_nonce"'])
            audit("gateway_nonce_required" if challenge else "gateway_response", self.request_id, valid_id)
            if attempt != 0 or not challenge:
                return response
            try:
                nonce, = response.headers.get_list("dpop-nonce")
                if not re.fullmatch(r"[A-Za-z0-9_-]{75}", nonce):
                    raise ValueError
                self.session.proof.remember_nonce(GATEWAY, response)
            except ValueError:
                raise Failure(502, "invalid_gateway_nonce") from None
            finally:
                await response.aclose()


def mock_compatible_body(body):
    # The installed CLI may put one system message inside the lab's single user turn.
    data = strict_json(body)
    messages = data.get("messages")
    if not isinstance(messages, list):
        return body
    inline = [message for message in messages
              if isinstance(message, dict) and message.get("role") == "system"]
    if not inline:
        return body
    user = [message for message in messages if isinstance(message, dict) and message.get("role") == "user"]
    if len(messages) != 2 or len(inline) != 1 or len(user) != 1:
        raise Failure(400, "unsupported_inline_system_message")
    blocks = []
    for content in (data.get("system"), inline[0].get("content")):
        if isinstance(content, str):
            blocks.append({"type": "text", "text": content})
        elif isinstance(content, list) and all(isinstance(block, dict) and block.get("type") == "text"
                                               and isinstance(block.get("text"), str) for block in content):
            blocks.extend(content)
        elif content is not None:
            raise Failure(400, "unsupported_inline_system_message")
    if inline[0].get("content") is None:
        raise Failure(400, "unsupported_inline_system_message")
    adapted = json.dumps({**data, "system": blocks, "messages": user},
                         separators=(",", ":"), ensure_ascii=True).encode("ascii")
    if len(adapted) > BODY_LIMIT:
        raise Failure(413, "body_too_large")
    return adapted


def create_app(session, gateway, host):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, redirect_slashes=False)

    @app.post("/v1/messages")
    async def messages(request: Request):
        request_id = uuid.uuid4().hex
        try:
            if (request.headers.getlist("host") != [host] or any(
                name in request.headers for name in ("origin", "forwarded", "dpop")
            ) or any(name.startswith("x-forwarded-") for name in request.headers)):
                raise Failure(400, "local_boundary_rejected")
            supplied = access_credential(request, "Bearer")
            if not hmac.compare_digest(supplied, session.secret):
                raise Failure(401, "local_authentication_failed", "Bearer")
            session.check_active()
            async with asyncio.timeout(15):
                body, stream = await read_messages(request)
                body = mock_compatible_body(body)
        except TimeoutError:
            failure = Failure(400, "local_body_timeout")
            audit(failure.event, request_id)
            return error_response(failure, request_id)
        except Failure as failure:
            audit(failure.event, request_id)
            return error_response(failure, request_id)
        except ClientDisconnect:
            audit("client_disconnected", request_id)
            return Response(status_code=400)
        return BrokerInvocation(gateway, session, body, stream, request.url.query, request_id)

    return app


def child_env(url, secret, config_dir, *, text_only=False):
    env = {key: os.environ[key] for key in CHILD_ENV if key in os.environ}
    env.update(ANTHROPIC_BASE_URL=url, ANTHROPIC_AUTH_TOKEN=secret,
               CLAUDE_CONFIG_DIR=str(config_dir), CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1",
               DISABLE_TELEMETRY="1", DISABLE_ERROR_REPORTING="1", DISABLE_AUTOUPDATER="1")
    if text_only:
        env.update(CLAUDE_CODE_MAX_OUTPUT_TOKENS="128", MAX_THINKING_TOKENS="0",
                   CLAUDE_CODE_DISABLE_THINKING="1", CLAUDE_CODE_MAX_RETRIES="0",
                   CLAUDE_CODE_EFFORT_LEVEL="unset", CLAUDE_CODE_DISABLE_STRUCTURED_OUTPUTS="1",
                   DISABLE_PROMPT_CACHING="1")
    return env


class BrokerServer(uvicorn.Server):
    def capture_signals(self):
        # The launcher owns process signals and always supervises its child.
        return nullcontext()


async def launch(claude, model, session, gateway, *, text_only=False):
    with tempfile.TemporaryDirectory(prefix="llm-broker-") as directory, socket.socket() as listener:
        work = Path(directory)
        config = work / "config"
        config.mkdir(mode=0o700)
        listener.bind(("127.0.0.1", 0))
        host = f"127.0.0.1:{listener.getsockname()[1]}"
        server = BrokerServer(uvicorn.Config(create_app(session, gateway, host),
                                             proxy_headers=False, access_log=False, log_config=None,
                                             timeout_graceful_shutdown=2))
        server_task = asyncio.create_task(server.serve(sockets=[listener]))
        process = None
        try:
            async with asyncio.timeout(5):
                while not server.started:
                    if server_task.done():
                        await server_task
                        raise OSError("Local listener failed to start")
                    await asyncio.sleep(0.01)
            session.check_active()
            process = await asyncio.create_subprocess_exec(
                claude, "--print", "--no-session-persistence", "--tools", "",
                "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
                "--settings", '{"disableAllHooks":true}',
                "--model", model, "--", PROMPT, cwd=work,
                env=child_env(f"http://{host}", session.secret, config, text_only=text_only),
                start_new_session=True,
            )
            child_task = asyncio.create_task(process.wait())
            async with asyncio.timeout(max(1, session.expiry - time.time()) + 60):
                done, _ = await asyncio.wait({child_task, server_task}, return_when=asyncio.FIRST_COMPLETED)
            if child_task in done:
                return child_task.result()
            raise OSError("Local listener stopped unexpectedly")
        finally:
            session.active = False
            server.should_exit = True
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.wait_for(process.wait(), timeout=2)
                except TimeoutError:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    await process.wait()
            await asyncio.wait_for(server_task, timeout=5)


async def supervise_signer(proof, owner):
    while proof.process.poll() is None:
        await asyncio.sleep(0.1)
    owner.cancel()


async def run(args, claude, token, proof):
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    loop.add_signal_handler(signal.SIGTERM, task.cancel)
    monitor = None
    if hasattr(proof, "process"):
        monitor = asyncio.create_task(supervise_signer(proof, task))
    try:
        async with https_client(args.as_ca) as authority, https_client(args.gateway_ca) as gateway:
            claims = await validate_access_token(token, Trust(authority, dpop=True), "DPoP")
            enforce_policy(claims, "DPoP")
            if not hmac.compare_digest(claims["cnf"]["jkt"], proof.jkt):
                raise ValueError("Gateway token has wrong key binding")
            (await gateway.get(GATEWAY.removesuffix("/v1/messages") + "/health")).raise_for_status()
            audit("exchange_verified", uuid.uuid4().hex)
            return await launch(claude, args.model, Session(token, proof, claims["exp"]), gateway,
                                text_only=getattr(args, "text_only", False))
    finally:
        if monitor is not None:
            monitor.cancel()
            await asyncio.gather(monitor, return_exceptions=True)
        loop.remove_signal_handler(signal.SIGTERM)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("client_dir", type=Path)
    parser.add_argument("--keycloak-ca", required=True)
    parser.add_argument("--as-ca", required=True)
    parser.add_argument("--gateway-ca", required=True)
    parser.add_argument("--claude", default="claude")
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--secure-signer", type=Path)
    parser.add_argument("--text-only", action="store_true", help="Use the bounded 8A text CLI profile")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for logger in ("httpx", "httpcore"):
        logging.getLogger(logger).setLevel(logging.WARNING)
    proof = None
    try:
        if args.secure_signer is not None:
            from hardware_signer import HardwareProofClient
            proof = HardwareProofClient(args.secure_signer.resolve(strict=True))
        audit("hardware_signer_selected" if proof is not None else "software_signer_selected", uuid.uuid4().hex)
        claude = shutil.which(args.claude)
        if claude is None:
            raise OSError("Claude Code executable unavailable")
        token, proof = acquire(args, proof)
        return asyncio.run(run(args, str(Path(claude).absolute()), token, proof))
    except (KeyboardInterrupt, asyncio.CancelledError):
        audit("session_cancelled", uuid.uuid4().hex)
        return 130
    except (httpx.HTTPError, jwt.PyJWTError, Failure, LoginError, OSError,
            ValueError, TypeError, KeyError, AttributeError, TimeoutError):
        audit("session_failed", uuid.uuid4().hex)
        return 1
    finally:
        if args.secure_signer is not None and proof is not None:
            proof.close()


if __name__ == "__main__":
    raise SystemExit(main())
