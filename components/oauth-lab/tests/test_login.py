import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from login import CallbackServer, HOST, callback_code, login
from oidc import CLIENT_ID, ENDPOINTS, ISSUER, REDIRECT_URI, Keycloak, LoginError, Transaction, b64url


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def claims(nonce):
    now = int(time.time())
    return {"iss": ISSUER, "sub": "synthetic", "aud": [CLIENT_ID],
            "azp": CLIENT_ID, "nonce": nonce, "iat": now, "exp": now + 299}


def callback(transaction, **overrides):
    return "/callback?" + urlencode({"state": transaction.state, "iss": ISSUER,
                                     "code": "synthetic-code", **overrides})


def test_authorization_request():
    first, second = Transaction(), Transaction()
    url = urlsplit(first.authorization_url())
    query = parse_qs(url.query)
    assert query["code_challenge"] == [b64url(hashlib.sha256(first.verifier.encode()).digest())]
    assert query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == [REDIRECT_URI]
    assert query["scope"] == ["openid"]
    assert first.state != second.state and first.nonce != second.nonce and first.verifier != second.verifier
    assert first.verifier not in first.authorization_url()


@pytest.mark.parametrize("override", [
    {"state": "wrong"}, {"iss": "https://untrusted.example"}, {"iss": ""},
    {"error": "access_denied"}, {"id_token": "front-channel"}, {"code": ""},
    {"state": ""}, {"access_token": "front-channel"},
])
def test_invalid_callback(override):
    tx = Transaction()
    with pytest.raises(LoginError):
        callback_code(callback(tx, **override), HOST, tx)


def test_callback_path_host_duplicates_and_deadline():
    tx = Transaction()
    for target, host, transaction in [
        (callback(tx) + "&code=duplicate", HOST, tx),
        (callback(tx) + "&state=duplicate", HOST, tx),
        (callback(tx).replace("/callback", "/other"), HOST, tx),
        (callback(tx), "localhost:8766", tx),
        ("/callback?code=unsolicited", HOST, tx),
        (callback(tx), HOST, Transaction(state=tx.state, expires=0)),
    ]:
        with pytest.raises(LoginError):
            callback_code(target, host, transaction)


@pytest.mark.parametrize("overrides", [
    {"issuer": "https://untrusted.example"},
    {"jwks_uri": "https://untrusted.example/keys"},
    {"token_endpoint": "https://untrusted.example/token"},
    {"authorization_response_iss_parameter_supported": False},
    {"code_challenge_methods_supported": "S256"},
])
def test_discovery_pins(overrides):
    def respond(request):
        assert str(request.url) == ISSUER + "/.well-known/openid-configuration"
        return httpx.Response(200, json={
            "issuer": ISSUER, **ENDPOINTS, "code_challenge_methods_supported": ["S256"],
            "authorization_response_iss_parameter_supported": True, **overrides,
        })

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(LoginError, match="metadata"):
            Keycloak(client).discover()


def test_token_response(signing_key):
    tx = Transaction()
    access = "opaque-access"
    payload = claims(tx.nonce)
    payload["at_hash"] = b64url(hashlib.sha256(access.encode()).digest()[:16])
    token = jwt.encode(payload, signing_key, algorithm="RS256", headers={"kid": "test"})

    def respond(request):
        assert str(request.url) == ENDPOINTS["token_endpoint"]
        assert parse_qs(request.content.decode()) == {
            "grant_type": ["authorization_code"], "client_id": [CLIENT_ID],
            "redirect_uri": [REDIRECT_URI], "code": ["synthetic-code"],
            "code_verifier": [tx.verifier],
        }
        return httpx.Response(200, json={
            "id_token": token, "access_token": access, "token_type": "Bearer", "expires_in": 300,
        })

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        keycloak = Keycloak(client)
        keycloak.keys = {"test": signing_key.public_key()}
        keycloak.keys_loaded_at = time.monotonic()
        assert keycloak.redeem("synthetic-code", tx) == (ISSUER, "synthetic")


@pytest.mark.parametrize("changes, header", [
    ({"nonce": "other"}, {}),
    ({"nonce": None}, {}),
    ({"iss": "https://untrusted.example"}, {}),
    ({"aud": ["other"]}, {}),
    ({"aud": [CLIENT_ID, "other"]}, {}),
    ({"azp": "other"}, {}),
    ({"sub": None}, {}),
    ({"exp": 0}, {}),
    ({"iat": True}, {}),
    ({"nbf": "123"}, {}),
    ({"at_hash": "bad"}, {}),
    ({}, {"kid": "unknown"}),
    ({}, {"jku": "https://untrusted.example/keys"}),
])
def test_invalid_identity(signing_key, changes, header):
    keycloak = Keycloak(None)
    keycloak.keys = {"test": signing_key.public_key()}
    keycloak.keys_loaded_at = time.monotonic()
    token = jwt.encode({**claims("nonce"), **changes}, signing_key, algorithm="RS256",
                       headers={"kid": "test", **header})
    with pytest.raises(LoginError):
        keycloak.validate_id_token(token, "opaque-access", "nonce")


def test_bad_signature_and_algorithm(signing_key):
    keycloak = Keycloak(None)
    keycloak.keys = {"test": signing_key.public_key()}
    keycloak.keys_loaded_at = time.monotonic()
    for key, algorithm in [(rsa.generate_private_key(public_exponent=65537, key_size=2048), "RS256"),
                           (b"z" * 32, "HS256")]:
        token = jwt.encode(claims("nonce"), key, algorithm=algorithm, headers={"kid": "test"})
        with pytest.raises(LoginError):
            keycloak.validate_id_token(token, "opaque-access", "nonce")


class FakeKeycloak:
    def __init__(self):
        self.redemptions = []

    def discover(self):
        pass

    def redeem(self, code, transaction):
        self.redemptions.append(code)
        return ISSUER, "synthetic"


def test_port_conflict_never_opens_browser():
    keycloak = FakeKeycloak()
    with CallbackServer(keycloak, Transaction()), pytest.raises(OSError):
        login(keycloak, lambda _: pytest.fail("opened browser with an unavailable port"))


def test_listener_rejects_then_redeems_at_most_once(capsys):
    keycloak = FakeKeycloak()
    with ThreadPoolExecutor(max_workers=3) as pool:
        def open_browser(url):
            fields = parse_qs(urlsplit(url).query)
            response_url = REDIRECT_URI + "?" + urlencode({
                "state": fields["state"][0], "iss": ISSUER, "code": "test-code-do-not-log",
            })

            def get(url, **kwargs):
                try:
                    return httpx.get(url, trust_env=False, **kwargs)
                except httpx.TransportError:
                    return None  # The listener may close before processing a replay.

            def browser():
                invalid = get(response_url + "&code=duplicate")
                assert invalid.status_code == 400
                assert invalid.headers["Referrer-Policy"] == "no-referrer"
                assert "test-code-do-not-log" not in invalid.text
                assert get(response_url, headers={"Host": "localhost:8766"}).status_code == 400
                return [pool.submit(get, response_url), pool.submit(get, response_url)]

            nonlocal result
            result = pool.submit(browser)
            return True

        result = None
        assert login(keycloak, open_browser) == (ISSUER, "synthetic")
        responses = [future.result() for future in result.result()]
        assert sum(response is not None and response.status_code == 200 for response in responses) == 1
    assert keycloak.redemptions == ["test-code-do-not-log"]
    assert capsys.readouterr() == ("", "")


def test_duplicate_claim_and_missing_nonce(signing_key):
    import json

    keycloak = Keycloak(None)
    keycloak.keys = {"test": signing_key.public_key()}
    keycloak.keys_loaded_at = time.monotonic()
    payload = claims("nonce")
    del payload["nonce"]
    encoded = json.dumps(payload).encode()
    for raw in (encoded, encoded[:-1] + b', "nonce":"nonce", "nonce":"nonce"}'):
        token = jwt.api_jws.encode(raw, signing_key, algorithm="RS256", headers={"kid": "test"})
        with pytest.raises(LoginError):
            keycloak.validate_id_token(token, "opaque-access", "nonce")


def test_correlated_error_consumes_without_redemption():
    keycloak = FakeKeycloak()
    with ThreadPoolExecutor(max_workers=1) as pool:
        def open_browser(url):
            state = parse_qs(urlsplit(url).query)["state"][0]
            target = REDIRECT_URI + "?" + urlencode({
                "state": state, "iss": ISSUER, "error": "access_denied",
            })
            nonlocal result
            result = pool.submit(httpx.get, target, trust_env=False)
            return True

        result = None
        with pytest.raises(LoginError, match="Login denied"):
            login(keycloak, open_browser)
        assert result.result().status_code == 400
    assert not keycloak.redemptions
