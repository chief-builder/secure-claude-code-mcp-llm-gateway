"""Key material and pinned configuration for the Component 2B lab."""

import base64
import hashlib
import json
import os
import stat
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = "https://127.0.0.1:8081"
UPSTREAM = "https://127.0.0.1:8080/realms/claude-security-lab"
DISCOVERY = UPSTREAM + "/.well-known/openid-configuration"
UPSTREAM_JWKS = UPSTREAM + "/protocol/openid-connect/certs"
MAX_BYTES = 64 * 1024

CANDIDATE = {
    "client_id": "lab-exchange-service",
    "authentication": "private_key_jwt",
    "client_jwks": "client-jwks.json",
    "issuer": UPSTREAM,
    "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
    "source_audience": "macos-oauth-client",
    "authorized_party_if_present": "macos-oauth-client",
    "target": "urn:lab:llm-gateway",
    "scope": "llm:invoke",
}
EXCHANGE_CLIENT_JWKS = "exchange-client-jwks.json"
EXCHANGE_CANDIDATE = {**CANDIDATE, "client_jwks": EXCHANGE_CLIENT_JWKS}
POLICY = {"exchange_enabled": False, "issuance_enabled": False, "candidate": CANDIDATE}


class FoundationError(Exception):
    """Lab startup or trust failure with a credential-free message."""


def unique_fields(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise FoundationError("Duplicate JSON field")
        result[name] = value
    return result


def read_object(data):
    try:
        result = json.loads(data, object_pairs_hook=unique_fields)
    except (ValueError, RecursionError):
        raise FoundationError("Invalid JSON object") from None
    if not isinstance(result, dict):
        raise FoundationError("Expected JSON object")
    return result


def b64int(number):
    raw = number.to_bytes((number.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def public_jwk(key):
    numbers = key.public_numbers()
    identity = {"kty": "RSA", "n": b64int(numbers.n), "e": b64int(numbers.e)}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode())
    kid = base64.urlsafe_b64encode(digest.digest()).rstrip(b"=").decode("ascii")
    return {**identity, "kid": kid, "use": "sig", "alg": "RS256"}


def checked_rsa_keys(document):
    keys = document.get("keys")
    if not isinstance(keys, list) or not keys:
        raise FoundationError("Invalid JWKS")
    seen = set()
    rsa_keys = set()
    signing_keys = set()
    for key in keys:
        if not isinstance(key, dict):
            raise FoundationError("Invalid JWKS entry")
        kid = key.get("kid")
        if not isinstance(kid, str) or not kid or kid in seen:
            raise FoundationError("Missing or ambiguous key ID")
        seen.add(kid)
        if {"d", "p", "q", "dp", "dq", "qi", "oth", "k"} & key.keys():
            raise FoundationError("JWKS contains private material")
        if key.get("kty") != "RSA":
            continue
        try:
            parsed = jwt.PyJWK.from_dict(key, algorithm="RS256").key
        except (jwt.PyJWTError, ValueError, TypeError, OverflowError):
            raise FoundationError("Invalid RSA public key") from None
        fingerprint = public_jwk(parsed)["kid"]
        rsa_keys.add(fingerprint)
        if key.get("alg") == "RS256" and key.get("use") == "sig":
            if parsed.key_size < 2048 or fingerprint in signing_keys:
                raise FoundationError("Weak or ambiguous RSA signing key")
            signing_keys.add(fingerprint)
    if not signing_keys:
        raise FoundationError("No usable RS256 signing key")
    return rsa_keys


def load_local(key_dir, policy_path, *, exchange=False):
    policy = read_object(policy_path.read_bytes())
    if not exchange and (policy != POLICY or policy["exchange_enabled"] is not False
            or policy["issuance_enabled"] is not False):
        raise FoundationError("Candidate policy does not match the disabled lab profile")

    dir_fd = os.open(key_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        directory = os.fstat(dir_fd)
        if directory.st_uid != os.getuid() or stat.S_IMODE(directory.st_mode) != 0o700:
            raise FoundationError("Key directory must be owned by the current user with mode 0700")
        fd = os.open("signing.key", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
        with os.fdopen(fd, "rb") as source:
            info = os.fstat(source.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
                raise FoundationError("Signing key must be an owner-only regular file")
            pem = source.read(MAX_BYTES + 1)
        client_file = EXCHANGE_CLIENT_JWKS if exchange else CANDIDATE["client_jwks"]
        fd = os.open(client_file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
        with os.fdopen(fd, "rb") as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
                raise FoundationError("Candidate client JWKS must be an owner-controlled regular file")
            client_jwks = source.read(MAX_BYTES + 1)
    finally:
        os.close(dir_fd)
    if max(len(pem), len(client_jwks)) > MAX_BYTES:
        raise FoundationError("Oversized key material")
    try:
        key = serialization.load_pem_private_key(pem, password=None)
    except (TypeError, ValueError):
        raise FoundationError("Invalid AS signing key") from None
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
        raise FoundationError("Expected an RSA signing key of at least 2048 bits")
    jwk = public_jwk(key.public_key())
    client_keys = checked_rsa_keys(read_object(client_jwks))
    if jwk["kid"] in client_keys:
        raise FoundationError("Candidate client key overlaps the AS signing key")
    if exchange:
        return jwk, client_keys, key, read_object(client_jwks)
    return jwk, client_keys


def provision(directory: Path):
    """Explicitly create disposable lab keys in a new directory."""
    signing = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    candidate = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key()
    directory.mkdir(mode=0o700)
    fd = os.open(directory / "signing.key", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as target:
        target.write(signing.private_bytes(serialization.Encoding.PEM,
                                           serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    (directory / "client-jwks.json").write_text(json.dumps({"keys": [public_jwk(candidate)]}) + "\n")
