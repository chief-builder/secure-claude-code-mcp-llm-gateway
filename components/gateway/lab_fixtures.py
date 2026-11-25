"""Synthetic responses shared by the gateway tests and the offline Claude Code check."""

import json

import httpx

import bedrock

MOCK_SECRET = "synthetic_mock_secret_canary"


class Bytes(httpx.AsyncByteStream):
    def __init__(self, *chunks):
        self.chunks = chunks
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk

    async def aclose(self):
        self.closed = True


def reply(data):
    return httpx.Response(200, stream=Bytes(json.dumps(data).encode()),
                          headers={"content-type": "application/json"})


def routes():
    return {"lab-claude-text": {
        "region": "us-east-1", "model_id": "synthetic.claude",
        "resource_arns": ["arn:aws:bedrock:us-east-1::foundation-model/synthetic.claude"],
        "capabilities": sorted(bedrock.REQUIRED_CAPABILITIES), "max_output_tokens": 128,
        "allowed_parameters": ["max_tokens", "stop_sequences", "temperature", "top_p"],
        "route_version": "lab-route-1",
    }}


def events():
    return [
        {"messageStart": {"role": "assistant"}},
        {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "MOCK"}}},
        {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "_OK"}}},
        {"contentBlockStop": {"contentBlockIndex": 0}},
        {"messageStop": {"stopReason": "end_turn"}},
        {"metadata": {"usage": {"inputTokens": 10, "outputTokens": 8}}},
    ]


class Stream:
    def __init__(self, values):
        self.values = values
        self.closed = False

    def __iter__(self):
        yield from self.values

    def close(self):
        self.closed = True


class Client:
    def __init__(self, values=None, failure=None):
        self.calls = []
        self.closed = False
        self.events = Stream(events() if values is None else values)
        self.failure = failure

    def converse(self, **args):
        self.calls.append(args)
        if self.failure:
            raise self.failure
        return {"output": {"message": {"role": "assistant", "content": [{"text": "MOCK_OK"}]}},
                "stopReason": "end_turn", "usage": {"inputTokens": 10, "outputTokens": 8},
                "ResponseMetadata": {"RequestId": "synthetic-aws-id"}}

    def converse_stream(self, **args):
        self.calls.append(args)
        if self.failure:
            raise self.failure
        return {"stream": self.events, "ResponseMetadata": {"RequestId": "synthetic-aws-id"}}

    def close(self):
        self.closed = True
