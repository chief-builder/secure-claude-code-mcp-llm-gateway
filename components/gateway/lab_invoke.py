"""Invoke the lab gateway through Component 3 browser sign-in and exchange."""

import argparse
import json
import secrets
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from gateway import CLIENT, ISSUER, SCOPE, TARGET
from dpop import encode, token_hash, thumbprint
from exchange import ASSERTION, ASSERTION_TYPE, GRANT
from foundation import CANDIDATE, MCP_RESOURCE, MCP_SCOPE, public_jwk
from lab_exchange import ExchangeLogin, LoginError, login, tls_client

GATEWAY = "https://127.0.0.1:8082/v1/messages"
REQUEST = {"model": "synthetic-lab", "max_tokens": 32,
           "messages": [{"role": "user", "content": "Return the synthetic lab response."}]}


class ProofClient:
    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        public = self.key.public_key().public_numbers()
        self.jwk = {"kty": "EC", "crv": "P-256", "x": encode(public.x.to_bytes(32, "big")),
                    "y": encode(public.y.to_bytes(32, "big"))}
        self.jkt = thumbprint(self.jwk)
        self.nonces = {}

    def sign(self, endpoint, token=None):
        claims = {"htm": "POST", "htu": endpoint, "iat": int(time.time()),
                  "jti": secrets.token_urlsafe(24)}
        if endpoint in self.nonces:
            claims["nonce"] = self.nonces[endpoint]
        if token is not None:
            claims["ath"] = token_hash(token)
        return jwt.encode(claims, self.key, algorithm="ES256",
                          headers={"typ": "dpop+jwt", "jwk": self.jwk})

    def remember_nonce(self, endpoint, response):
        values = response.headers.get_list("dpop-nonce")
        if len(values) != 1 or not values[0] or len(values[0]) > 256 or "," in values[0]:
            raise ValueError("Invalid nonce challenge")
        self.nonces[endpoint] = values[0]


def exchange_token(args, subject, proof, *, signing_key=None, mcp=False):
    endpoint = ISSUER + "/token"
    key = signing_key
    if key is None:
        key = serialization.load_pem_private_key((args.client_dir / "assertion.key").read_bytes(), None)
    kid = public_jwk(key.public_key())["kid"]
    with tls_client(args.as_ca) as authority:
        for attempt in range(2):
            now = int(time.time())
            assertion = jwt.encode(
                {"iss": CLIENT, "sub": CLIENT, "aud": ISSUER, "iat": now,
                 "exp": now + 30, "jti": secrets.token_urlsafe(24)},
                key, algorithm="RS256", headers={"kid": kid, "typ": ASSERTION_TYPE},
            )
            headers = {"DPoP": proof.sign(endpoint)} if proof is not None else {}
            response = authority.post(endpoint, headers=headers, data={
                "grant_type": GRANT, "subject_token": subject,
                "subject_token_type": CANDIDATE["subject_token_type"],
                **({"resource": MCP_RESOURCE, "scope": MCP_SCOPE} if mcp
                   else {"audience": TARGET, "scope": SCOPE}),
                "client_assertion_type": ASSERTION, "client_assertion": assertion,
            })
            if (proof is not None and attempt == 0 and response.status_code == 400
                    and response.json().get("error") == "use_dpop_nonce"):
                proof.remember_nonce(endpoint, response)
                continue
            result = response.raise_for_status().json()
            token = result["access_token"]
            if proof is not None:
                if result.get("token_type") != "DPoP":
                    raise ValueError("Expected a DPoP access token")
                keys = authority.get(ISSUER + "/jwks").raise_for_status().json()["keys"]
                header = jwt.get_unverified_header(token)
                jwk, = [entry for entry in keys if entry["kid"] == header["kid"]]
                audience, scope = (MCP_RESOURCE, MCP_SCOPE) if mcp else (TARGET, SCOPE)
                claims = jwt.decode(token, jwt.PyJWK.from_dict(jwk).key, algorithms=["RS256"],
                                    audience=audience, issuer=ISSUER)
                # The library accepts a list containing the audience; require it alone.
                if (claims["aud"] != audience or claims.get("cnf") != {"jkt": proof.jkt}
                        or claims.get("scope") != scope):
                    raise ValueError("Unexpected access token audience, binding or scope")
            return token


@contextmanager
def invoke(client, token, payload, proof):
    for attempt in range(2):
        headers = {"authorization": f"DPoP {token}" if proof is not None else f"Bearer {token}"}
        if proof is not None:
            headers["DPoP"] = proof.sign(GATEWAY, token)
        with client.stream("POST", GATEWAY, headers=headers, json=payload) as response:
            if (proof is not None and attempt == 0 and response.status_code == 401
                    and response.headers.get("www-authenticate") == 'DPoP error="use_dpop_nonce"'):
                proof.remember_nonce(GATEWAY, response)
                continue
            yield response.raise_for_status()
            return


def probe(args):
    with tls_client(args.keycloak_ca) as keycloak_client:
        keycloak = ExchangeLogin(keycloak_client)
        login(keycloak)
    proof = ProofClient() if args.dpop else None
    token = exchange_token(args, keycloak.subject_token, proof)
    mcp_token = None
    if args.mcp:
        # The same sign-in yields one token per target. Ask straight away: the
        # authorization server accepts a sign-in token only while it is fresh.
        mcp_token = exchange_token(args, keycloak.subject_token, proof, mcp=True)
    with tls_client(args.gateway_ca) as client:
        with invoke(client, token, REQUEST, proof) as response:
            result = response.read()
            if not any("MOCK_OK" in block.get("text", "")
                       for block in json.loads(result)["content"]):
                raise ValueError("Unexpected mock JSON result")

        found_text = completed = False
        with invoke(client, token, {**REQUEST, "stream": True}, proof) as response:
            if not response.headers.get("content-type", "").startswith("text/event-stream"):
                raise ValueError("Unexpected mock SSE type")
            for line in response.iter_lines():
                if line.startswith("data: "):
                    event = json.loads(line[6:])
                    found_text |= "MOCK_OK" in event.get("delta", {}).get("text", "")
                    completed |= event.get("type") == "message_stop"
        if not (found_text and completed):
            raise ValueError("Incomplete mock stream")

        if mcp_token is not None:
            # The model gateway must refuse a token issued for the MCP gateway. Check the
            # token is still within its lifetime, so the refusal is not for expiry.
            expiry = jwt.decode(mcp_token, options={"verify_signature": False})["exp"]
            if expiry - time.time() < 30:
                raise ValueError("MCP token too close to expiry to test the refusal")
            refused = client.post(GATEWAY, json=REQUEST, headers={
                "authorization": f"DPoP {mcp_token}", "DPoP": proof.sign(GATEWAY, mcp_token)})
            if (refused.status_code != 401
                    or refused.headers.get("www-authenticate") != 'DPoP error="invalid_token"'):
                raise ValueError("Model gateway accepted an MCP token")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("client_dir", type=Path)
    parser.add_argument("--keycloak-ca", required=True)
    parser.add_argument("--as-ca", required=True)
    parser.add_argument("--gateway-ca", required=True)
    parser.add_argument("--dpop", action="store_true")
    parser.add_argument("--mcp", action="store_true",
                        help="Also obtain an MCP token and check the model gateway refuses it")
    args = parser.parse_args()
    if args.mcp and not args.dpop:
        parser.error("--mcp requires --dpop")
    try:
        probe(args)
    except (httpx.HTTPError, jwt.PyJWTError, LoginError, OSError, ValueError, TypeError,
            KeyError, AttributeError):
        print("component_05_failed" if args.dpop else "component_04_failed", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    print("component_05_succeeded" if args.dpop else "component_04_succeeded")
    if args.mcp:
        print("mcp_token_succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
