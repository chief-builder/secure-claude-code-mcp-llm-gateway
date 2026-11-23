"""Run the Component 2A native lab login."""

import argparse
import hmac
import re
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qsl, urlsplit

from oidc import CALLBACK_PORT, ISSUER, Keycloak, LoginError, Transaction, tls_client

LOOPBACK = "127.0.0.1"
HOST = f"{LOOPBACK}:{CALLBACK_PORT}"
MAX_CALLBACK_LENGTH = 8192
INVALID_ESCAPE = re.compile(r"%(?![0-9a-fA-F]{2})")


def callback_code(target, host, transaction):
    if (
        host != HOST or len(target) > MAX_CALLBACK_LENGTH
        or not target.startswith("/callback?") or INVALID_ESCAPE.search(target)
        or any(not "!" <= character <= "~" for character in target)
    ):
        raise LoginError("Invalid callback")
    try:
        path = urlsplit(target)
        if path.path != "/callback" or path.fragment:
            raise ValueError
        pairs = parse_qsl(path.query, keep_blank_values=True, strict_parsing=True,
                          errors="strict", max_num_fields=12)
    except ValueError:
        raise LoginError("Malformed callback") from None
    fields = dict(pairs)
    if len(fields) != len(pairs) or {"access_token", "id_token", "refresh_token"} & fields.keys():
        raise LoginError("Unexpected callback fields")
    state = fields.get("state", "")
    if (
        time.monotonic() >= transaction.expires
        or fields.get("iss") != ISSUER
        or not state.isascii()
        or not hmac.compare_digest(state, transaction.state)
    ):
        raise LoginError("Uncorrelated callback")
    code, error = fields.get("code"), fields.get("error")
    if (code is None) == (error is None) or not (code or error):
        raise LoginError("Expected exactly one code or error")
    if any(not "!" <= character <= "~" for character in (code or error)):
        raise LoginError("Malformed code or error")
    return code


class CallbackHandler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(1)
        super().setup()

    def log_message(self, *_):
        pass

    def send_error(self, code, *_args, **_kwargs):
        self.reply(code, b"Invalid request.")

    def reply(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        try:
            hosts = self.headers.get_all("Host", [])
            if len(hosts) != 1 or self.server.consumed:
                raise LoginError("Invalid callback")
            code = callback_code(self.path, hosts[0], self.server.transaction)
        except LoginError:
            self.reply(400, b"Invalid login response.")
            return
        # HTTPServer dispatches serially. Consume before attempting redemption.
        self.server.consumed = True
        if code is not None:
            try:
                self.server.identity = self.server.keycloak.redeem(code, self.server.transaction)
            except LoginError:
                pass
        if self.server.identity is None:
            self.reply(400, b"Login failed. You can close this tab.")
        else:
            self.reply(200, b"Login complete. You can close this tab.")


class CallbackServer(HTTPServer):
    allow_reuse_address = True
    allow_reuse_port = False

    def __init__(self, keycloak, transaction):
        self.keycloak = keycloak
        self.transaction = transaction
        self.consumed = False
        self.identity = None
        super().__init__((LOOPBACK, CALLBACK_PORT), CallbackHandler)

    def handle_error(self, *_):
        # Socket failures must not log a request line, exception, or callback data.
        pass


def login(keycloak, open_browser=webbrowser.open):
    keycloak.discover()
    transaction = Transaction()
    with CallbackServer(keycloak, transaction) as server:
        if not open_browser(transaction.authorization_url()):
            raise LoginError("Could not open the system browser")
        while not server.consumed:
            remaining = transaction.expires - time.monotonic()
            if remaining <= 0:
                raise LoginError("Login timed out")
            server.timeout = remaining
            server.handle_request()
        if server.identity is None:
            raise LoginError("Login denied or token validation failed")
        return server.identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ca-file", required=True, help="PEM of the disposable lab CA")
    args = parser.parse_args()
    try:
        with tls_client(args.ca_file) as client:
            login(Keycloak(client))
    except LoginError as error:
        print(f"component_02a_login_failed: {error}", file=sys.stderr)
        return 1
    except (OSError, webbrowser.Error):
        print("component_02a_login_failed: local setup or listener unavailable", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("component_02a_login_cancelled", file=sys.stderr)
        return 130
    print("component_02a_login_succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
