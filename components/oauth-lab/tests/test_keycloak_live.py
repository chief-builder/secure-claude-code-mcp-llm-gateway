"""Protocol checks against the disposable Keycloak realm when LAB_TLS_DIR is set."""

import os
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlsplit

import httpx
import pytest

from oidc import CLIENT_ID, ENDPOINTS, ISSUER, REDIRECT_URI, Keycloak, LoginError, Transaction, tls_client

LAB_TLS_DIR = os.environ.get("LAB_TLS_DIR")
pytestmark = pytest.mark.skipif(not LAB_TLS_DIR, reason="set LAB_TLS_DIR for live Keycloak checks")


class LoginForm(HTMLParser):
    action = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form" and attrs.get("id") == "kc-form-login":
            self.action = attrs.get("action")


@pytest.fixture
def client():
    with tls_client(os.path.join(LAB_TLS_DIR, "ca.pem")) as client:
        yield client


def authorize(client, transaction, **changes):
    params = dict(parse_qsl(urlsplit(transaction.authorization_url()).query))
    params.update(changes)
    return client.get(ENDPOINTS["authorization_endpoint"],
                      params={key: value for key, value in params.items() if value is not None})


def obtain_code(client, transaction):
    response = authorize(client, transaction)
    if response.status_code == 200:
        form = LoginForm()
        form.feed(response.text)
        assert form.action and form.action.startswith(ISSUER + "/login-actions/authenticate?")
        response = client.post(form.action, data={
            "username": "synthetic-employee", "password": "synthetic-local-only",
        })
    assert response.status_code == 302
    destination = urlsplit(response.headers["location"])
    assert destination._replace(query="").geturl() == REDIRECT_URI
    callback = dict(parse_qsl(destination.query))
    assert callback.get("state") == transaction.state and callback.get("iss") == ISSUER
    assert "error" not in callback and "code" in callback
    return callback["code"]


def test_live_discovery_and_invalid_tls(client):
    Keycloak(client).discover()
    with httpx.Client(trust_env=False, timeout=5) as untrusted:
        with pytest.raises(LoginError, match="Issuer request failed"):
            Keycloak(untrusted).discover()


@pytest.mark.parametrize("redirect", [
    "http://localhost:8766/callback",
    "http://127.0.0.1:8767/callback",
    "http://127.0.0.1:8766/other",
])
def test_live_redirect_registration(client, redirect):
    response = authorize(client, Transaction(), redirect_uri=redirect)
    assert response.status_code == 400 and "location" not in response.headers


@pytest.mark.parametrize("method, challenge", [("plain", "a" * 43), (None, None)])
def test_live_pkce_required(client, method, challenge):
    response = authorize(client, Transaction(), code_challenge_method=method, code_challenge=challenge)
    assert response.status_code == 302
    params = dict(parse_qsl(urlsplit(response.headers["location"]).query))
    assert "error" in params and "code" not in params


@pytest.mark.parametrize("change", [
    {"code_verifier": "a" * 43},
    {"code_verifier": None},
    {"redirect_uri": "http://127.0.0.1:8766/other"},
    {"client_id": "account"},
])
def test_live_code_binding(client, change):
    transaction = Transaction()
    code = obtain_code(client, transaction)
    data = {"grant_type": "authorization_code", "client_id": CLIENT_ID, "code": code,
            "redirect_uri": REDIRECT_URI, "code_verifier": transaction.verifier}
    data.update(change)
    response = client.post(ENDPOINTS["token_endpoint"],
                           data={key: value for key, value in data.items() if value is not None})
    assert response.status_code in (400, 401)
    assert "access_token" not in response.json() and "id_token" not in response.json()


def test_live_token_and_code_replay(client):
    keycloak = Keycloak(client)
    keycloak.discover()
    transaction = Transaction()
    code = obtain_code(client, transaction)
    assert keycloak.redeem(code, transaction)[0] == ISSUER
    with pytest.raises(LoginError, match="Issuer request failed"):
        keycloak.redeem(code, transaction)
