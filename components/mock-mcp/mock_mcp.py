"""Mock MCP tool server for the synthetic lab, built with the official MCP SDK."""

import hmac
import os
import re

import uvicorn
from mcp.server import CacheHint, MCPServer

HOST, PORT = "127.0.0.1", 8767


def build_server():
    # Every caller sees the same two tools, so the list may be cached by anyone.
    server = MCPServer("lab-mock-mcp", version="0.1.0", log_level="WARNING",
                       cache_hints={"tools/list": CacheHint(ttl_ms=60_000, scope="public")})

    @server.tool()
    def lab_echo(text: str) -> str:
        """Return the text it is given."""
        return text

    @server.tool()
    def lab_add(a: int, b: int) -> int:
        """Return the sum of two whole numbers."""
        return a + b

    return server


class RequireCredential:
    """Refuse a request without the shared credential before the SDK sees it."""

    def __init__(self, app, credential):
        self.app = app
        self.expected = b"Bearer " + credential.encode("ascii")

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            presented = [value for name, value in scope["headers"] if name == b"authorization"]
            if len(presented) != 1 or not hmac.compare_digest(presented[0], self.expected):
                await send({"type": "http.response.start", "status": 401, "headers": [
                    (b"www-authenticate", b"Bearer"), (b"cache-control", b"no-store"),
                    (b"content-length", b"0")]})
                await send({"type": "http.response.body", "body": b""})
                return
        await self.app(scope, receive, send)


def create_app(credential):
    if not re.fullmatch(r"[A-Za-z0-9_-]{22,128}", credential):
        raise ValueError("Set MOCK_MCP_TOKEN to a disposable mock credential")
    # No sessions and a single JSON reply per request, as revision 2026-07-28 allows.
    app = build_server().streamable_http_app(stateless_http=True, json_response=True, host=HOST)
    app.add_middleware(RequireCredential, credential=credential)
    return app


def main():
    try:
        app = create_app(os.environ.get("MOCK_MCP_TOKEN", ""))
    except ValueError as error:
        raise SystemExit(str(error)) from None
    uvicorn.run(app, host=HOST, port=PORT, access_log=False)


if __name__ == "__main__":
    main()
