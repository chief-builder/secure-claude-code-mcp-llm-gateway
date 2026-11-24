"""Proof validation shared by the lab authorization server and gateway."""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import time
from dataclasses import dataclass

import jwt
from cryptography.hazmat.primitives.asymmetric import ec

from foundation import FoundationError, read_object

MAX_PROOF = 8192
PROOF_AGE = 30
SKEW = 5
NONCE_AGE = 60


class InvalidProof(Exception):
    pass


class NonceRequired(Exception):
    def __init__(self, nonce):
        self.nonce = nonce


def encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def decode(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError
    raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    if encode(raw) != value:
        raise ValueError
    return raw


def token_hash(token):
    return encode(hashlib.sha256(token.encode("ascii")).digest())


def thumbprint(jwk):
    canonical = json.dumps(jwk, separators=(",", ":"), sort_keys=True)
    return token_hash(canonical)


def valid_thumbprint(value):
    try:
        return isinstance(value, str) and len(value) == 43 and len(decode(value)) == 32
    except ValueError:
        return False


def nonce_key(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise FoundationError("Nonce key must be an owner-only regular file")
        value = handle.read(33)
    if len(value) != 32:
        raise FoundationError("Expected a 32-byte nonce key")
    return value


@dataclass(frozen=True)
class Proof:
    jkt: str
    jti: str
    issued: int
    nonce_expires: int

    @property
    def replay_until(self):
        return min(self.issued + PROOF_AGE, self.nonce_expires)

    def check_time(self, now):
        if not now - PROOF_AGE <= self.issued <= now + SKEW or now >= self.nonce_expires:
            raise InvalidProof


class Verifier:
    def __init__(self, endpoint, key):
        if len(key) != 32:
            raise FoundationError("Expected a 32-byte nonce key")
        self.endpoint = endpoint
        self.key = key

    def nonce_mac(self, jkt, payload):
        return hmac.digest(self.key, f"{self.endpoint}\n{jkt}\n".encode("ascii") + payload, "sha256")

    def new_nonce(self, jkt, now):
        payload = now.to_bytes(8, "big") + secrets.token_bytes(16)
        return encode(payload + self.nonce_mac(jkt, payload))

    def nonce_expiry(self, value, jkt, now):
        try:
            if not isinstance(value, str) or len(value) != 75:
                raise ValueError
            raw = decode(value)
            payload, mac = raw[:24], raw[24:]
            issued = int.from_bytes(payload[:8], "big")
            if (not now - NONCE_AGE < issued <= now + SKEW
                    or not hmac.compare_digest(self.nonce_mac(jkt, payload), mac)):
                raise ValueError
        except ValueError:
            raise NonceRequired(self.new_nonce(jkt, now)) from None
        return issued + NONCE_AGE

    def validate(self, values, *, token=None, binding=None):
        if len(values) != 1 or len(values[0]) > MAX_PROOF:
            raise InvalidProof
        try:
            h, p, s = (decode(part) for part in values[0].split("."))
            header, claims = read_object(h), read_object(p)
            jwk = header.get("jwk")
            if (set(header) != {"typ", "alg", "jwk"} or header["typ"] != "dpop+jwt"
                    or header["alg"] != "ES256" or not isinstance(jwk, dict)
                    or set(jwk) != {"kty", "crv", "x", "y"}
                    or jwk["kty"] != "EC" or jwk["crv"] != "P-256" or len(s) != 64):
                raise ValueError
            x, y = decode(jwk["x"]), decode(jwk["y"])
            if len(x) != 32 or len(y) != 32:
                raise ValueError
            public = ec.EllipticCurvePublicNumbers(int.from_bytes(x, "big"),
                                                  int.from_bytes(y, "big"), ec.SECP256R1()).public_key()
            jwt.api_jws.decode_complete(values[0], public, algorithms=["ES256"])
            jkt = thumbprint(jwk)
            now = int(time.time())
            issued, jti = claims.get("iat"), claims.get("jti")
            required = {"jti", "htm", "htu", "iat", "nonce"}
            if token is not None:
                required.add("ath")
            if (set(claims) - required or claims.get("htm") != "POST"
                    or claims.get("htu") != self.endpoint or type(issued) is not int
                    or not now - PROOF_AGE <= issued <= now + SKEW
                    or not isinstance(jti, str) or not re.fullmatch(r"[A-Za-z0-9_-]{22,128}", jti)):
                raise ValueError
            if token is not None:
                ath = claims.get("ath")
                if (not valid_thumbprint(binding) or not valid_thumbprint(ath)
                        or not hmac.compare_digest(binding, jkt)
                        or not hmac.compare_digest(ath, token_hash(token))):
                    raise ValueError
        except (ValueError, jwt.PyJWTError, FoundationError):
            raise InvalidProof from None
        return Proof(jkt, jti, issued, self.nonce_expiry(claims.get("nonce"), jkt, now))
