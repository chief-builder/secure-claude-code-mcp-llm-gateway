"""Synthetic lab token exchange and durable one-time use."""

import base64
import hashlib
import json
import logging
import os
import re
import sqlite3
import stat
import time
import uuid
from contextlib import closing
from urllib.parse import parse_qsl

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from dpop import InvalidProof, NonceRequired
from foundation import EXCHANGE_CANDIDATE as CANDIDATE
from foundation import ISSUER, UPSTREAM, FoundationError, read_object

CLIENT = CANDIDATE["client_id"]
SOURCE = CANDIDATE["source_audience"]
TARGET = CANDIDATE["target"]
SCOPE = CANDIDATE["scope"]
GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"
ASSERTION = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
# RFC 10070: clients should type their assertion, and servers should not reject
# untyped ones. "JWT" is the generic type many libraries add by default.
ASSERTION_TYPE = "client-authentication+jwt"
ACCEPTED_ASSERTION_TYPES = (ASSERTION_TYPE, "JWT", None)
ACCESS = "urn:ietf:params:oauth:token-type:access_token"
REQUIRED = {"grant_type", "subject_token", "subject_token_type", "audience", "scope"}
AUTH_FIELDS = {"client_assertion", "client_assertion_type"}
FIELDS = REQUIRED | AUTH_FIELDS | {"requested_token_type", "client_id"}
HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache"}
LOG = logging.getLogger("uvicorn.error")
AS_REPLAY_DATABASE = "auth-server-token-exchange-replay.sqlite3"


class Rejected(Exception):
    def __init__(self, code, event):
        self.code = code
        self.event = event


def signing_keys(jwks):
    return {
        key["kid"]: jwt.PyJWK.from_dict(key, algorithm="RS256").key
        for key in jwks["keys"]
        if (key.get("kty"), key.get("use"), key.get("alg")) == ("RSA", "sig", "RS256")
    }


def token_parts(token):
    parts = token.split(".")
    if len(parts) != 3 or any(not re.fullmatch(r"[A-Za-z0-9_-]+", part) for part in parts):
        raise ValueError
    try:
        header, claims = (
            read_object(base64.b64decode(part + "=" * (-len(part) % 4), altchars=b"-_", validate=True))
            for part in parts[:2]
        )
    except FoundationError:
        raise ValueError from None
    if (header.get("alg") != "RS256" or set(header) - {"alg", "kid", "typ"}
            or not isinstance(header.get("kid"), str) or not header["kid"]):
        raise ValueError
    return header, claims


def verify(token, key):
    jwt.decode(token, key, algorithms=["RS256"], options={
        "verify_exp": False, "verify_iat": False, "verify_nbf": False,
        "verify_aud": False, "verify_sub": False, "verify_jti": False,
    })


def valid_times(claims, now, lifetime, age):
    issued, expiry = claims.get("iat"), claims.get("exp")
    nbf = claims.get("nbf", issued)
    return (
        all(type(value) is int for value in (issued, expiry, nbf))
        and now - age <= issued <= now + 5 and nbf <= now + 5
        and 0 < expiry - issued <= lifetime and nbf < expiry and now < expiry
    )


def digest(*parts):
    return hashlib.sha256(json.dumps(parts, separators=(",", ":")).encode()).hexdigest()


class ReplayStore:
    def __init__(self, directory, filename=AS_REPLAY_DATABASE):
        info = directory.lstat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700 or not stat.S_ISDIR(info.st_mode):
            raise FoundationError("Invalid replay directory")
        self.path = directory / filename
        fd = os.open(self.path, os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_RDONLY, 0o600)
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
                raise FoundationError("Invalid replay database")
        with closing(self.connect()) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS spent (digest TEXT PRIMARY KEY, expires INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS clock (id INTEGER PRIMARY KEY CHECK(id = 1), high INTEGER NOT NULL)")
            db.execute("INSERT OR IGNORE INTO clock VALUES (1, ?)", (int(time.time()),))

    def connect(self):
        db = sqlite3.connect(self.path.absolute().as_uri() + "?mode=rw", uri=True, timeout=2)
        db.execute("PRAGMA synchronous=FULL")
        return db

    def reserve(self, key, expiry, rejection, action, *, additional=()):
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            now = int(time.time())
            high, = db.execute("SELECT high FROM clock WHERE id = 1").fetchone()
            if now < high - 5:
                raise FoundationError("Replay clock moved backwards")
            db.execute("UPDATE clock SET high = max(high, ?) WHERE id = 1", (now,))
            db.execute("DELETE FROM spent WHERE expires < ?", (now,))
            for reservation, until, error in (*additional, (key, expiry, rejection)):
                inserted = db.execute("INSERT OR IGNORE INTO spent VALUES (?, ?)",
                                      (reservation, until + 5))
                if not inserted.rowcount:
                    raise error
            return action(now)


async def read_form(request):
    if (request.headers.getlist("content-type") != ["application/x-www-form-urlencoded"]
            or "authorization" in request.headers or "content-encoding" in request.headers
            or request.url.query or request.scope["scheme"] != "https"):
        raise ValueError
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > 32768:
            raise ValueError
        body.extend(chunk)
    encoded = body.decode("ascii")
    if re.search(r"%(?![0-9A-Fa-f]{2})", encoded):
        raise ValueError
    pairs = parse_qsl(encoded, keep_blank_values=True, strict_parsing=True,
                      errors="strict", max_num_fields=len(FIELDS))
    form = dict(pairs)
    if len(form) != len(pairs) or form.keys() - FIELDS:
        raise ValueError
    return form


class Exchange:
    def __init__(self, policy_path, key_dir, signing, jwk, registered, trust, verifier=None):
        policy = read_object(policy_path.read_bytes())
        subjects = policy.get("subjects")
        if (set(policy) != {"exchange_enabled", "issuance_enabled", "candidate", "subjects"}
                or policy["exchange_enabled"] is not True or policy["issuance_enabled"] is not True
                or policy["candidate"] != CANDIDATE or not isinstance(subjects, dict) or not subjects
                or any(not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", source)
                       or not isinstance(target, str)
                       or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", target)
                       or target == source for source, target in subjects.items())
                or len(set(subjects.values())) != len(subjects)):
            raise FoundationError("Invalid enabled exchange policy")
        self.subjects = subjects
        self.signing = signing
        self.kid = jwk["kid"]
        self.client_keys = signing_keys(registered)
        self.verifier = verifier
        self.trust = trust
        self.store = ReplayStore(key_dir)

    def authenticate(self, form):
        rejected = Rejected("invalid_client", "client_rejected")
        try:
            if (form.get("client_assertion_type") != ASSERTION
                    or form.get("client_id", CLIENT) != CLIENT):
                raise ValueError
            token = form.get("client_assertion", "")
            header, claims = token_parts(token)
            verify(token, self.client_keys[header["kid"]])
            jti = claims.get("jti")
            if (header.get("typ") not in ACCEPTED_ASSERTION_TYPES
                    or claims.get("iss") != CLIENT or claims.get("sub") != CLIENT
                    # The issuer identifier is the only accepted audience (RFC 10070).
                    or claims.get("aud") != ISSUER
                    or not isinstance(jti, str) or not re.fullmatch(r"[A-Za-z0-9_-]{22,128}", jti)
                    or not valid_times(claims, int(time.time()), 60, 60)):
                raise ValueError
        except (KeyError, ValueError, FoundationError, jwt.PyJWTError):
            raise rejected from None

        def check_time(now):
            if not valid_times(claims, now, 60, 60):
                raise rejected

        self.store.reserve(digest("client", CLIENT, jti), claims["exp"],
                           Rejected("invalid_client", "client_replay"), check_time)

    async def issue(self, form, proof_headers=()):
        await run_in_threadpool(self.authenticate, form)
        proof = None
        if self.verifier is not None:
            proof = self.verifier.validate(proof_headers)
        elif proof_headers:
            raise InvalidProof
        rejected = Rejected("invalid_request", "subject_rejected")
        if form.get("grant_type") not in (None, GRANT):
            raise Rejected("unsupported_grant_type", "grant_rejected")
        if form.get("audience") not in (None, TARGET):
            raise Rejected("invalid_target", "target_rejected")
        if form.get("scope") != SCOPE:
            raise Rejected("invalid_scope", "scope_rejected")
        if (REQUIRED - form.keys() or form["subject_token_type"] != CANDIDATE["subject_token_type"]
                or form.get("requested_token_type", ACCESS) != ACCESS):
            raise rejected
        try:
            token = form["subject_token"]
            header, claims = token_parts(token)
            if not await self.trust.ready(header["kid"]):
                raise FoundationError("Current upstream trust unavailable")
            verify(token, self.trust.keys[header["kid"]])
            subject = self.subjects[claims["sub"]]
            nonce = claims.get("nonce")
            if (claims.get("iss") != UPSTREAM or claims.get("aud") not in (SOURCE, [SOURCE])
                    or claims.get("azp", SOURCE) != SOURCE or claims.get("typ") != "ID"
                    or not isinstance(nonce, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", nonce)
                    or not valid_times(claims, int(time.time()), 300, 60)):
                raise ValueError
        except (KeyError, TypeError, ValueError, jwt.PyJWTError):
            raise rejected from None

        def mint(now):
            if not valid_times(claims, now, 300, 60):
                raise rejected
            if proof is not None:
                proof.check_time(now)
            expires = min(now + 300, claims["exp"])
            try:
                token = jwt.encode({
                    "iss": ISSUER, "aud": TARGET, "sub": subject, "client_id": CLIENT,
                    "iat": now, "exp": expires, "jti": uuid.uuid4().hex, "scope": SCOPE,
                    **({"cnf": {"jkt": proof.jkt}} if proof is not None else {}),
                }, self.signing, algorithm="RS256", headers={"typ": "at+jwt", "kid": self.kid})
            except Exception:
                raise FoundationError("Signing unavailable") from None
            return {"access_token": token, "issued_token_type": ACCESS, "token_type": "DPoP" if proof is not None else "Bearer",
                    "expires_in": expires - now, "scope": SCOPE}

        additional = () if proof is None else (
            (digest("dpop-as", proof.jkt, proof.jti), proof.replay_until, InvalidProof()),
        )
        return await run_in_threadpool(
            self.store.reserve, digest("subject", UPSTREAM, SOURCE, nonce),
            min(claims["exp"], claims["iat"] + 60),
            Rejected("invalid_request", "subject_replay"), mint, additional=additional,
        )


async def token_endpoint(request: Request):
    correlation = uuid.uuid4().hex
    headers = {**HEADERS, "X-Request-ID": correlation}
    try:
        try:
            form = await read_form(request)
        except (ValueError, ClientDisconnect):
            raise Rejected("invalid_request", "form_rejected") from None
        body = await request.app.state.exchange.issue(form, request.headers.getlist("dpop"))
        status, event = 200, "exchange_succeeded"
    except InvalidProof:
        body, status, event = {"error": "invalid_dpop_proof"}, 400, "dpop_rejected"
    except NonceRequired as error:
        headers["DPoP-Nonce"] = error.nonce
        body, status, event = {"error": "use_dpop_nonce"}, 400, "dpop_nonce_required"
    except Rejected as error:
        body, status, event = {"error": error.code}, 400, error.event
    except (FoundationError, sqlite3.Error, OSError):
        body, status, event = {"error": "temporarily_unavailable"}, 503, "dependency_failed"
    LOG.info("token_exchange event=%s correlation_id=%s", event, correlation)
    return JSONResponse(body, status_code=status, headers=headers)
