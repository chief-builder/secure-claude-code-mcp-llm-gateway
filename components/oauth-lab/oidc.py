"""Pinned Keycloak OIDC client for the synthetic lab."""

import base64
import hashlib
import hmac
import json
import secrets
import ssl
import time
from dataclasses import dataclass, field
from urllib.parse import urlencode

import httpx
import jwt

ISSUER = "https://127.0.0.1:8080/realms/claude-security-lab"
CLIENT_ID = "macos-oauth-client"
CALLBACK_PORT = 8766
REDIRECT_URI = f"http://127.0.0.1:{CALLBACK_PORT}/callback"
ENDPOINTS = {
    "authorization_endpoint": ISSUER + "/protocol/openid-connect/auth",
    "token_endpoint": ISSUER + "/protocol/openid-connect/token",
    "jwks_uri": ISSUER + "/protocol/openid-connect/certs",
}
TOKEN_LIFETIME = 300
TRANSACTION_LIFETIME = 300
MAX_RESPONSE_BYTES = 65536


class LoginError(Exception):
    """A generic, credential-free login failure."""


def b64url(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def unique_fields(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise LoginError("Duplicate field")
        result[name] = value
    return result


def read_object(value):
    try:
        result = json.loads(value, object_pairs_hook=unique_fields)
    except (ValueError, RecursionError):
        raise LoginError("Malformed JSON") from None
    if not isinstance(result, dict):
        raise LoginError("Expected JSON object")
    return result


@dataclass(frozen=True)
class Transaction:
    state: str = field(default_factory=lambda: secrets.token_urlsafe(32), repr=False)
    nonce: str = field(default_factory=lambda: secrets.token_urlsafe(32), repr=False)
    verifier: str = field(default_factory=lambda: secrets.token_urlsafe(32), repr=False)
    expires: float = field(default_factory=lambda: time.monotonic() + TRANSACTION_LIFETIME)

    def authorization_url(self):
        query = urlencode({
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "response_mode": "query",
            "scope": "openid",
            "state": self.state,
            "nonce": self.nonce,
            "code_challenge_method": "S256",
            "code_challenge": b64url(hashlib.sha256(self.verifier.encode("ascii")).digest()),
        })
        return ENDPOINTS["authorization_endpoint"] + "?" + query


def tls_client(ca_file):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cafile=ca_file)
    return httpx.Client(verify=context, trust_env=False, follow_redirects=False, timeout=5)


class Keycloak:
    def __init__(self, client):
        self.client = client
        self.keys = {}
        self.keys_loaded_at = float("-inf")

    def request(self, method, endpoint, **kwargs):
        try:
            with self.client.stream(method, endpoint, **kwargs) as response:
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_bytes(chunk_size=8192):
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise LoginError("Oversized issuer response")
                return read_object(body)
        except httpx.HTTPError:
            raise LoginError("Issuer request failed") from None

    def discover(self):
        metadata = self.request("GET", ISSUER + "/.well-known/openid-configuration")
        if (
            metadata.get("issuer") != ISSUER
            or any(metadata.get(name) != url for name, url in ENDPOINTS.items())
            or metadata.get("authorization_response_iss_parameter_supported") is not True
            or not isinstance(metadata.get("code_challenge_methods_supported"), list)
            or "S256" not in metadata["code_challenge_methods_supported"]
        ):
            raise LoginError("Issuer metadata does not match the lab profile")
        self.load_keys()

    def load_keys(self):
        self.keys_loaded_at = time.monotonic()
        self.keys = {}
        jwks = self.request("GET", ENDPOINTS["jwks_uri"]).get("keys")
        if not isinstance(jwks, list) or any(not isinstance(key, dict) for key in jwks):
            raise LoginError("Malformed issuer keys")
        keys = {}
        seen = set()
        for key in jwks:
            kid = key.get("kid")
            if not isinstance(kid, str) or not kid or kid in seen:
                raise LoginError("Missing or ambiguous key ID")
            seen.add(kid)
            if (key.get("kty"), key.get("use"), key.get("alg")) != ("RSA", "sig", "RS256"):
                continue
            if {"d", "p", "q", "dp", "dq", "qi", "oth"} & key.keys():
                raise LoginError("Private issuer key parameters")
            try:
                public_key = jwt.PyJWK.from_dict(key, algorithm="RS256").key
                if public_key.key_size < 2048:
                    raise LoginError("Issuer key too small")
            except (jwt.PyJWTError, ValueError, TypeError):
                raise LoginError("Invalid issuer key") from None
            keys[kid] = public_key
        if not keys:
            raise LoginError("No usable issuer keys")
        self.keys = keys

    def redeem(self, code, transaction):
        tokens = self.request("POST", ENDPOINTS["token_endpoint"], data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "code": code,
            "code_verifier": transaction.verifier,
        })
        access_token = tokens.get("access_token")
        token_type = tokens.get("token_type")
        lifetime = tokens.get("expires_in")
        if (
            not isinstance(access_token, str) or not access_token or not access_token.isascii()
            or not isinstance(token_type, str) or token_type.lower() != "bearer"
            or type(lifetime) is not int or not 0 < lifetime <= TOKEN_LIFETIME
        ):
            raise LoginError("Invalid access token response")
        return self.validate_id_token(tokens.get("id_token"), access_token, transaction.nonce)

    def validate_id_token(self, token, access_token, nonce):
        if not isinstance(token, str) or len(token) > MAX_RESPONSE_BYTES:
            raise LoginError("Invalid ID token")
        try:
            segments = jwt.api_jws.decode_complete(token, options={"verify_signature": False})
            # Use strict JSON parsing before accepting either JOSE headers or claims.
            header = read_object(jwt.utils.base64url_decode(token.split(".")[0].encode("ascii")))
            claims = read_object(segments["payload"])
            kid = header.get("kid")
            if (
                header.get("alg") != "RS256"
                or not isinstance(kid, str) or not kid
                or {"jku", "x5u", "jwk", "crit"} & header.keys()
            ):
                raise LoginError("Unexpected ID token header")
            age = time.monotonic() - self.keys_loaded_at
            if age >= 300 or (kid not in self.keys and age >= 5):
                self.load_keys()
            key = self.keys.get(kid)
            if key is None:
                raise LoginError("Unknown issuer key")
            if any(type(claims[name]) is not int for name in ("iat", "exp", "nbf") if name in claims):
                raise LoginError("Invalid ID token times")
            jwt.decode(token, key, algorithms=["RS256"], audience=CLIENT_ID, issuer=ISSUER,
                       options={"require": ["iss", "sub", "aud", "iat", "exp", "nonce"]}, leeway=30)
        except (jwt.PyJWTError, ValueError, TypeError, OverflowError):
            raise LoginError("Invalid ID token") from None
        if (
            claims["aud"] not in (CLIENT_ID, [CLIENT_ID])
            or claims.get("azp", CLIENT_ID) != CLIENT_ID
            or not claims["sub"].strip()
            or not 0 < claims["exp"] - claims["iat"] <= TOKEN_LIFETIME
            or claims.get("nbf", claims["iat"]) >= claims["exp"]
            or claims["nonce"] != nonce
        ):
            raise LoginError("ID token claims do not match the transaction")
        if "at_hash" in claims:
            digest = b64url(hashlib.sha256(access_token.encode("ascii")).digest()[:16])
            at_hash = claims["at_hash"]
            if not isinstance(at_hash, str) or not at_hash.isascii() or not hmac.compare_digest(digest, at_hash):
                raise LoginError("Access token hash mismatch")
        return ISSUER, claims["sub"]
