# Mock LLM

## What it is

A stand-in for a model. It speaks enough of the Anthropic Messages API for Claude
Code to talk to it and always answers `MOCK_OK — Local inference working`, as JSON
or as a server-sent event stream. It lets the whole security path be exercised
without calling a real model. This is Component 1 of the build.

## Run it

Run `uv sync` once at the repository root. The mock refuses to start without a
credential, so give it any throwaway value:

```sh
MOCK_LLM_TOKEN=local-mock-only \
  uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --no-access-log
```

In another terminal:

```sh
token=local-mock-only
curl --silent http://127.0.0.1:8765/health && echo
curl --silent http://127.0.0.1:8765/v1/messages \
  -H "authorization: Bearer $token" -H 'content-type: application/json' \
  -d '{"model":"any","max_tokens":16,"messages":[{"role":"user","content":"hi"}]}' && echo
```

The second command returns a Messages response whose text is the `MOCK_OK` line. Add
`"stream":true` to the body to get the same text as events.

To point Claude Code straight at the mock, with no gateway in between:

```sh
ANTHROPIC_BASE_URL=http://127.0.0.1:8765 ANTHROPIC_AUTH_TOKEN=local-mock-only \
  claude --print "hello"
```

In the full lab the gateway sits in front of the mock; see the
[quickstart](../../docs/quickstart.md).

## Test it

```sh
uv run python -m pytest -q
```

Expect 8 passed. All tests run offline.

## How it works

- [`app/main.py`](app/main.py) — the `/health` and `/v1/messages` routes and the
  credential check.
- [`app/streaming.py`](app/streaming.py) — the event stream, with a `delay` query
  parameter (0 to 10 seconds) between text fragments for testing slow responses and
  cancellation.
- [`app/models.py`](app/models.py) — the request and response shapes.
- [Design spec](../../docs/component-01/design-spec.md) and
  [acceptance report](../../docs/component-01/acceptance-report.md).

## Limits

- Text only. Tool calls are accepted in a request but never produced.
- The reply and the token counts are fixed; nothing is inferred from the prompt.
- It listens on plain HTTP and is meant for loopback only.
