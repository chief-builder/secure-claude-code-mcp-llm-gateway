"""Disposable browser-to-exchange probe. Prints outcome codes only."""

import argparse
import json
import os
import secrets
import sys
import time
from pathlib import Path

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from exchange import ACCESS, ASSERTION, CLIENT, GRANT, SCOPE, TARGET
from foundation import CANDIDATE, EXCHANGE_CLIENT_JWKS, ISSUER, public_jwk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "oauth-lab"))
from login import login
from oidc import Keycloak, LoginError, tls_client


class ExchangeLogin(Keycloak):
    def validate_id_token(self, token, access_token, nonce):
        identity = super().validate_id_token(token, access_token, nonce)
        self.subject_token = token
        self.upstream_access_token = access_token
        return identity


def provision(client_dir, as_keys):
    client_dir.mkdir(mode=0o700)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    fd = os.open(client_dir / "assertion.key", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as target:
        target.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption()))
    with (as_keys / EXCHANGE_CLIENT_JWKS).open("x") as target:
        json.dump({"keys": [public_jwk(key.public_key())]}, target)


def probe(args):
    key_file = args.client_dir / "assertion.key"
    directory = args.client_dir.lstat()
    info = key_file.lstat()
    if (directory.st_uid != os.getuid() or directory.st_mode & 0o777 != 0o700
            or args.client_dir.is_symlink() or info.st_uid != os.getuid()
            or info.st_mode & 0o777 != 0o600 or not key_file.is_file()
            or key_file.is_symlink() or info.st_nlink != 1):
        raise ValueError
    key = serialization.load_pem_private_key(key_file.read_bytes(), password=None)
    kid = public_jwk(key.public_key())["kid"]
    with tls_client(args.keycloak_ca) as upstream, tls_client(args.as_ca) as client:
        keycloak = ExchangeLogin(upstream)
        login(keycloak)
        jwks = client.get(ISSUER + "/jwks").raise_for_status().json()["keys"]
        jwk, = jwks

        def send(subject):
            now = int(time.time())
            assertion = jwt.encode(
                {"iss": CLIENT, "sub": CLIENT, "aud": ISSUER,
                 "iat": now, "exp": now + 30, "jti": secrets.token_urlsafe(24)},
                key, algorithm="RS256", headers={"kid": kid},
            )
            return client.post(ISSUER + "/token", data={
                "grant_type": GRANT, "subject_token": subject,
                "subject_token_type": CANDIDATE["subject_token_type"], "audience": TARGET,
                "scope": SCOPE, "client_assertion_type": ASSERTION, "client_assertion": assertion,
            })

        result = send(keycloak.subject_token).raise_for_status().json()
        token = result["access_token"]
        header = jwt.get_unverified_header(token)
        claims = jwt.decode(token, jwt.PyJWK.from_dict(jwk).key, algorithms=["RS256"],
                            audience=TARGET, issuer=ISSUER,
                            options={"require": ["iat", "exp", "sub", "jti", "client_id", "scope"]})
        if (header != {"alg": "RS256", "typ": "at+jwt", "kid": jwk["kid"]}
                or claims["sub"] != args.expected_subject or claims["client_id"] != CLIENT
                or claims["scope"] != SCOPE or not 0 < claims["exp"] - claims["iat"] <= 300
                or result.get("issued_token_type") != ACCESS or result.get("token_type") != "Bearer"
                or result.get("expires_in") != claims["exp"] - claims["iat"]
                or result.get("scope") != SCOPE or "refresh_token" in result):
            raise ValueError
        for upstream_key in keycloak.keys.values():
            try:
                jwt.decode(token, upstream_key, algorithms=["RS256"], audience=TARGET, issuer=ISSUER)
            except jwt.InvalidSignatureError:
                continue
            raise ValueError
        for rejected in (keycloak.subject_token, keycloak.upstream_access_token, token):
            response = send(rejected)
            if response.status_code != 400 or response.json() != {"error": "invalid_request"}:
                raise ValueError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init-client")
    init.add_argument("client_dir", type=Path)
    init.add_argument("as_keys", type=Path)
    run = commands.add_parser("probe")
    run.add_argument("client_dir", type=Path)
    run.add_argument("--keycloak-ca", required=True)
    run.add_argument("--as-ca", required=True)
    run.add_argument("--expected-subject", required=True)
    args = parser.parse_args()
    try:
        if args.command == "init-client":
            provision(args.client_dir, args.as_keys)
        else:
            probe(args)
    except (OSError, ValueError, TypeError, KeyError, AttributeError,
            httpx.HTTPError, LoginError, jwt.PyJWTError):
        print("component_03_failed", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    print("component_03_succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
