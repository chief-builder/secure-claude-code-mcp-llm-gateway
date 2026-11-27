"""Loopback MCP gateway for the synthetic lab: DPoP-bound tokens and per-tool rules."""

import argparse
import asyncio
import base64
import binascii
import json
import logging
import os
import re
import sqlite3
import ssl
import uuid
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect
from starlette.responses import JSONResponse, Response

# The token, proof and replay checks are the LLM gateway's own, not copies of them.
from dpop import InvalidProof, NonceRequired, Verifier, nonce_key
from exchange import ReplayStore
from foundation import ISSUER, MCP_RESOURCE, MCP_SCOPE, FoundationError
from gateway import (Failure, Trust, access_credential, enforce_policy, record_proof, strict_json,
                     validate_access_token)

VERSION = "2026-07-28"
UPSTREAM = "http://127.0.0.1:8767/mcp"
METADATA_PATH = "/.well-known/oauth-protected-resource/mcp"
METADATA = MCP_RESOURCE.removesuffix("/mcp") + METADATA_PATH
BODY_LIMIT = REPLY_LIMIT = 1024 * 1024
DEADLINE = 30
REPLAY_DATABASE = "mcp-gateway-request-proof-replay.sqlite3"
PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"
CAPABILITIES = "io.modelcontextprotocol/clientCapabilities"
SERVER_INFO = "io.modelcontextprotocol/serverInfo"
NAME = re.compile(r"[A-Za-z0-9_.-]{1,128}", re.ASCII)
METHODS = ("server/discover", "tools/list", "tools/call")
LOG = logging.getLogger("uvicorn.error")

HEADER_MISMATCH, UNSUPPORTED_VERSION, INVALID_PARAMS, METHOD_NOT_FOUND = -32020, -32022, -32602, -32601


class RpcError(Exception):
    """A refusal that is reported to the caller as a JSON-RPC error."""

    def __init__(self, status, code, message, event, call_id, data=None):
        self.status = status
        self.event = event
        self.body = {"jsonrpc": "2.0", "id": call_id, "error": {"code": code, "message": message}}
        if data is not None:
            self.body["error"]["data"] = data


def audit(event, request_id, subject=None, tool=None):
    # The subject comes from a verified token and the tool from the policy file.
    # Nothing chosen by the caller is written, and never arguments or results.
    line = f"mcp_gateway event={event} request_id={request_id}"
    if subject is not None:
        line += f" subject={subject if NAME.fullmatch(subject) else 'unprintable'}"
    if tool is not None:
        line += f" tool={tool}"
    LOG.info(line)


def load_tool_policy(path):
    """Read which tools each user may use. Anything unexpected stops startup."""
    data = strict_json(Path(path).read_bytes())
    tools = data.get("tools")
    if set(data) != {"tools"} or not isinstance(tools, dict):
        raise ValueError("Tool policy must be an object with one field, tools")
    policy = {}
    for subject, names in tools.items():
        if (not NAME.fullmatch(subject) or not isinstance(names, list) or len(set(map(str, names))) != len(names)
                or not all(isinstance(name, str) and NAME.fullmatch(name) for name in names)):
            raise ValueError("Invalid tool policy entry")
        policy[subject] = frozenset(names)
    return policy


def sendable_json(body):
    """Strict JSON that can also be written back out.

    Python reads an out-of-range number as infinity and accepts half of a character
    pair, and neither can be sent on. Refusing them here means a request or a reply
    is refused as malformed instead of failing later, when it is relayed.
    """
    data = strict_json(body)
    json.dumps(data, allow_nan=False, ensure_ascii=False).encode("utf-8")
    return data


def header_text(value):
    """Decode the MCP specification's Base64 form of a header value, if used."""
    match = re.fullmatch(r"=\?base64\?([A-Za-z0-9+/]*={0,2})\?=", value)
    if match is None:
        return value
    try:
        return base64.b64decode(match[1], validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        raise ValueError("Invalid encoded header") from None


async def read_request(request):
    """Return (id, method, params) once the headers are known to agree with the body."""
    content_types = request.headers.getlist("content-type")
    encodings = request.headers.getlist("content-encoding")
    if (len(content_types) != 1 or content_types[0].split(";", 1)[0].strip().lower() != "application/json"
            or (encodings and [value.lower() for value in encodings] != ["identity"])):
        raise Failure(415, "unsupported_media")
    if request.url.query:
        raise Failure(400, "invalid_query")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > BODY_LIMIT:
            raise Failure(413, "body_too_large")
        body.extend(chunk)
    try:
        data = sendable_json(body)
    except (FoundationError, ValueError, RecursionError):
        raise Failure(400, "invalid_json") from None
    call_id, method, params = data.get("id"), data.get("method"), data.get("params")
    # One request with an id: no notifications, and a batch is not a JSON object.
    if (set(data) != {"jsonrpc", "id", "method", "params"} or data["jsonrpc"] != "2.0"
            or type(call_id) not in (str, int) or not isinstance(method, str)):
        raise Failure(400, "invalid_request")

    def refuse(code, message, event, data=None):
        return RpcError(400, code, message, event, call_id, data)

    meta = params.get("_meta") if isinstance(params, dict) else None
    if not isinstance(meta, dict) or not isinstance(meta.get(CAPABILITIES), dict):
        raise refuse(INVALID_PARAMS, "Invalid params", "invalid_params")
    mismatch = refuse(HEADER_MISMATCH, "Headers do not match the request body", "header_mismatch")
    # Without this header a tool server may skip the header checks altogether, so a
    # missing or different value is refused here and never forwarded.
    versions = request.headers.getlist("mcp-protocol-version")
    if len(versions) != 1 or versions[0] != meta.get(PROTOCOL_VERSION):
        raise mismatch
    if versions[0] != VERSION:
        raise refuse(UNSUPPORTED_VERSION, "Unsupported protocol version", "unsupported_version",
                     {"supported": [VERSION], "requested": versions[0]})
    if request.headers.getlist("mcp-method") != [method]:
        raise mismatch
    names = request.headers.getlist("mcp-name")
    if method == "tools/call":
        if not isinstance(params.get("name"), str):
            raise refuse(INVALID_PARAMS, "Invalid params", "invalid_params")
        try:
            if len(names) != 1 or header_text(names[0]) != params["name"]:
                raise ValueError
        except ValueError:
            raise mismatch from None
    elif names:
        raise mismatch
    return call_id, method, params


def upstream_request(credential, method, params):
    """Build the tool server's request from named fields only.

    Nothing of the caller's request is passed on as received: not its token or
    proof, and not its capabilities, so a tool server cannot ask the user for input.
    """
    sent = {"_meta": {PROTOCOL_VERSION: VERSION, CAPABILITIES: {}}}
    headers = {"authorization": f"Bearer {credential}", "content-type": "application/json",
               "accept": "application/json, text/event-stream", "accept-encoding": "identity",
               "mcp-protocol-version": VERSION, "mcp-method": method}
    if method == "tools/call":
        sent["name"], sent["arguments"] = params["name"], params.get("arguments", {})
        headers["mcp-name"] = params["name"]
    elif "cursor" in params:
        sent["cursor"] = params["cursor"]
    return httpx.Request("POST", UPSTREAM, headers=headers,
                         json={"jsonrpc": "2.0", "id": 1, "method": method, "params": sent})


def checked_result(method, reply, allowed):
    """Accept only a complete result, and keep only the fields the caller may see."""
    result = reply.get("result")
    if (set(reply) != {"jsonrpc", "id", "result"} or reply["jsonrpc"] != "2.0" or reply["id"] != 1
            or type(reply["id"]) is not int or not isinstance(result, dict)
            or result.get("resultType") != "complete"):
        # Includes a request for user input and a task handle.
        raise ValueError
    if method == "tools/list":
        tools, cursor = result.get("tools"), result.get("nextCursor")
        if (not isinstance(tools, list) or not isinstance(cursor, (str, type(None)))
                or not all(isinstance(tool, dict) and isinstance(tool.get("name"), str) for tool in tools)
                or len({tool["name"] for tool in tools}) != len(tools)):
            raise ValueError
        # Private and uncached: the list differs per user, whatever the tool server says.
        kept = {"resultType": "complete", "tools": [tool for tool in tools if tool["name"] in allowed],
                "ttlMs": 0, "cacheScope": "private"}
        if cursor is not None:
            kept["nextCursor"] = cursor
        return kept
    content, structured = result.get("content"), result.get("structuredContent")
    if (not isinstance(content, list) or not all(isinstance(item, dict) for item in content)
            or type(result.get("isError", False)) is not bool
            or not isinstance(structured, (dict, type(None)))):
        raise ValueError
    kept = {"resultType": "complete", "content": content, "isError": result.get("isError", False)}
    if structured is not None:
        kept["structuredContent"] = structured
    return kept


async def forward(client, credential, method, params, allowed):
    invalid = Failure(502, "invalid_upstream_response")
    request = upstream_request(credential, method, params)
    try:
        async with asyncio.timeout(DEADLINE):
            upstream = await client.send(request, stream=True)
            try:
                if (upstream.status_code != 200
                        or upstream.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json"
                        or upstream.headers.get("content-encoding", "identity").lower() != "identity"):
                    raise invalid
                body = bytearray()
                async for chunk in upstream.aiter_raw():
                    if len(body) + len(chunk) > REPLY_LIMIT:
                        raise invalid
                    body.extend(chunk)
            finally:
                await upstream.aclose()
        return checked_result(method, sendable_json(body), allowed)
    except (TimeoutError, httpx.TimeoutException):
        raise Failure(504, "upstream_timeout") from None
    except httpx.HTTPError:
        raise Failure(502, "upstream_failed") from None
    except (FoundationError, ValueError, RecursionError):
        raise invalid from None


async def until_finished_or_disconnected(request, work):
    """Await the upstream call, abandoning and closing it if the caller goes away."""
    async def disconnected():
        while (await request.receive())["type"] != "http.disconnect":
            pass

    work, gone = asyncio.ensure_future(work), asyncio.create_task(disconnected())
    try:
        await asyncio.wait({work, gone}, return_when=asyncio.FIRST_COMPLETED)
        if not work.done():
            raise ClientDisconnect
        return work.result()
    finally:
        for task in (work, gone):
            task.cancel()
        await asyncio.gather(work, gone, return_exceptions=True)


def refusal(failure, request_id):
    headers = {"request-id": request_id, "cache-control": "no-store"}
    if failure.challenge:
        # The LLM gateway's challenge for this kind of refusal, plus the scope to ask
        # for and where to find the metadata, as the MCP specification asks.
        challenge = failure.challenge + ("," if " " in failure.challenge else "")
        if "scope=" not in challenge:
            challenge += f' scope="{MCP_SCOPE}",'
        headers["www-authenticate"] = f'{challenge} resource_metadata="{METADATA}"'
    if failure.nonce is not None:
        headers["dpop-nonce"] = failure.nonce
    return Response(status_code=failure.status, headers=headers)


def create_app(as_ca, upstream_credential, policy, *, dpop_nonce_key, dpop_replay_dir,
               trust_transport=None, upstream_transport=None):
    if not re.fullmatch(r"[A-Za-z0-9_-]{22,128}", upstream_credential):
        raise ValueError("Set a disposable credential for the tool server")
    if dpop_nonce_key is None or dpop_replay_dir is None:
        raise ValueError("The MCP gateway runs only with DPoP")
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls.load_verify_locations(cafile=as_ca)
    discovery = {
        "resultType": "complete", "supportedVersions": [VERSION],
        "capabilities": {"tools": {"listChanged": False}}, "ttlMs": 0, "cacheScope": "private",
        "_meta": {SERVER_INFO: {"name": "lab-mcp-gateway", "version": version("secure-claude-code-lab")}},
    }

    @asynccontextmanager
    async def lifespan(app):
        async with (
            httpx.AsyncClient(verify=tls, trust_env=False, follow_redirects=False,
                              timeout=3, transport=trust_transport) as authority,
            httpx.AsyncClient(trust_env=False, follow_redirects=False,
                              timeout=httpx.Timeout(15, connect=2), transport=upstream_transport) as upstream,
        ):
            app.state.verifier = Verifier(MCP_RESOURCE, nonce_key(dpop_nonce_key))
            app.state.replay = ReplayStore(dpop_replay_dir, REPLAY_DATABASE)
            app.state.trust = Trust(authority, dpop=True)
            app.state.upstream = upstream
            yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None,
                  redirect_slashes=False)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get(METADATA_PATH)
    async def metadata():
        return {"resource": MCP_RESOURCE, "authorization_servers": [ISSUER],
                "scopes_supported": [MCP_SCOPE], "bearer_methods_supported": [],
                "dpop_bound_access_tokens_required": True,
                "dpop_signing_alg_values_supported": ["ES256"]}

    @app.post("/mcp")
    async def mcp(request: Request):
        request_id = uuid.uuid4().hex
        subject = tool = None
        outgoing = {"request-id": request_id, "cache-control": "no-store"}
        try:
            if "origin" in request.headers:
                raise Failure(403, "origin_rejected")
            token = access_credential(request, "DPoP")
            claims = await validate_access_token(token, app.state.trust, "DPoP", MCP_RESOURCE)
            if request.scope["scheme"] != "https":
                raise InvalidProof
            proof = app.state.verifier.validate(request.headers.getlist("dpop"), token=token,
                                                 binding=claims["cnf"]["jkt"])
            enforce_policy(claims, "DPoP", MCP_SCOPE)
            subject = claims["sub"]
            call_id, method, params = await read_request(request)
            await run_in_threadpool(record_proof, app.state.replay, proof, claims["exp"])
            # A user the policy does not name is a valid caller with no tools.
            allowed = policy.get(subject, frozenset())
            if method not in METHODS:
                raise RpcError(404, METHOD_NOT_FOUND, "Method not found", "method_refused", call_id)
            if method == "server/discover":
                result = discovery
            else:
                if method == "tools/call":
                    # The same reply whether the tool exists or not, and nothing is forwarded.
                    if params["name"] not in allowed:
                        raise RpcError(200, INVALID_PARAMS, "Unknown tool", "tool_refused", call_id)
                    tool = params["name"]
                    valid = isinstance(params.get("arguments", {}), dict)
                else:
                    valid = isinstance(params.get("cursor", ""), str)
                if not valid:
                    raise RpcError(400, INVALID_PARAMS, "Invalid params", "invalid_params", call_id)
                result = await until_finished_or_disconnected(
                    request, forward(app.state.upstream, upstream_credential, method, params, allowed))
        except RpcError as error:
            audit(error.event, request_id, subject)
            return JSONResponse(error.body, error.status, outgoing)
        except Failure as failure:
            audit(failure.event, request_id, subject, tool)
            return refusal(failure, request_id)
        except NonceRequired as challenge:
            audit("dpop_nonce_required", request_id)
            return refusal(Failure(401, "dpop_nonce_required", 'DPoP error="use_dpop_nonce"',
                                   challenge.nonce), request_id)
        except InvalidProof:
            audit("dpop_rejected", request_id)
            return refusal(Failure(401, "dpop_rejected", 'DPoP error="invalid_dpop_proof"'), request_id)
        except (FoundationError, sqlite3.Error, OSError):
            audit("replay_unavailable", request_id, subject)
            return refusal(Failure(503, "replay_unavailable"), request_id)
        except ClientDisconnect:
            audit("client_disconnected", request_id, subject, tool)
            return Response(status_code=400)
        audit({"server/discover": "discovered", "tools/list": "tools_listed",
               "tools/call": "tool_called"}[method], request_id, subject, tool)
        return JSONResponse({"jsonrpc": "2.0", "id": call_id, "result": result}, headers=outgoing)

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-ca", required=True)
    parser.add_argument("--tls-cert", required=True)
    parser.add_argument("--tls-key", required=True)
    parser.add_argument("--dpop-nonce-key", type=Path, required=True)
    parser.add_argument("--dpop-replay-dir", type=Path, required=True)
    parser.add_argument("--tool-policy", type=Path, required=True)
    args = parser.parse_args()
    try:
        app = create_app(args.as_ca, os.environ.get("MCP_GATEWAY_UPSTREAM_TOKEN", ""),
                         load_tool_policy(args.tool_policy), dpop_nonce_key=args.dpop_nonce_key,
                         dpop_replay_dir=args.dpop_replay_dir)
    except (OSError, ValueError, FoundationError):
        parser.exit(1, "MCP gateway CA, tool policy or tool server credential configuration invalid\n")
    uvicorn.run(app, host="127.0.0.1", port=8083, ssl_certfile=args.tls_cert,
                ssl_keyfile=args.tls_key, proxy_headers=False, access_log=False)


if __name__ == "__main__":
    main()
