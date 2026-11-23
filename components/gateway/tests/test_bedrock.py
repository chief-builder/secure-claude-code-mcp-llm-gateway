import asyncio
import json
import logging
import threading

import httpx
import pytest

import bedrock
import gateway
from lab_invoke import GATEWAY, ProofClient
from test_gateway import lab, dpop_headers, setup_gateway_dpop


def routes():
    return {"lab-claude-text": {
        "region": "us-east-1", "model_id": "synthetic.claude",
        "resource_arns": ["arn:aws:bedrock:us-east-1::foundation-model/synthetic.claude"],
        "capabilities": sorted(bedrock.REQUIRED_CAPABILITIES), "max_output_tokens": 128,
        "allowed_parameters": ["max_tokens", "stop_sequences", "temperature", "top_p"],
        "route_version": "lab-route-1",
    }}


def payload(**overrides):
    return {"model": "lab-claude-text", "max_tokens": 32,
            "messages": [{"role": "user", "content": "prompt-canary"}], **overrides}


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


def test_mapping():
    alias, args, streamed = bedrock.prepare(json.dumps(payload(
        system=[{"type": "text", "text": "synthetic"}], temperature=0.5,
        stop_sequences=["stop"], stream=True)).encode(), routes())
    assert alias == "lab-claude-text" and streamed
    assert args == {"modelId": "synthetic.claude",
                    "messages": [{"role": "user", "content": [{"text": "prompt-canary"}]}],
                    "system": [{"text": "synthetic"}],
                    "inferenceConfig": {"maxTokens": 32, "temperature": 0.5, "stopSequences": ["stop"]},
                    "additionalModelResponseFieldPaths": ["/stop_sequence"]}
    assert "additionalModelResponseFieldPaths" not in bedrock.prepare(
        json.dumps(payload()).encode(), routes())[1]


@pytest.mark.parametrize(("extra", "expected"), [
    ({"stop_sequence": "stop"}, "stop"), ({"stop_sequence": "unrequested"}, None),
    ({"stop_sequence": ["stop"]}, None), ({}, None), (None, None),
])
def test_matched_stop_sequence(extra, expected):
    stop = {"stopReason": "stop_sequence", "additionalModelResponseFields": extra}
    chunks = b"".join(bedrock.stream_events(events()[:-2] + [{"messageStop": stop}, events()[-1]],
                                            "alias", "id", ["stop"]))
    delta = json.loads(chunks.split(b"event: message_delta\ndata: ")[1].split(b"\n")[0])
    assert delta["delta"] == {"stop_reason": "stop_sequence", "stop_sequence": expected}
    assert bedrock.matched_stop("stop_sequence", extra, ["stop"]) == expected
    assert bedrock.matched_stop("end_turn", extra, ["stop"]) is None


@pytest.mark.parametrize("streamed", [False, True])
def test_server_disabled_thinking_reaches_sdk(streamed):
    config = routes()
    config["lab-claude-text"]["additional_model_request_fields"] = {"thinking": {"type": "disabled"}}
    sdk = Client()

    async def check():
        async with httpx.AsyncClient(transport=bedrock.BedrockTransport(config, lambda _: sdk)) as client:
            response = await client.post("http://fixture", json=payload(stream=streamed))
            assert response.status_code == 200
        while not sdk.closed:
            await asyncio.sleep(0.001)
    asyncio.run(check())
    assert len(sdk.calls) == 1
    assert sdk.calls[0]["additionalModelRequestFields"] == {"thinking": {"type": "disabled"}}


@pytest.mark.parametrize("value", [None, {}, {"thinking": {"type": "adaptive"}},
    {"thinking": {"type": "disabled", "budget_tokens": 1024}},
    {"thinking": {"type": "disabled"}, "other": True}])
def test_rejects_unsupported_provider_route_fields(value):
    config = routes()
    config["lab-claude-text"]["additional_model_request_fields"] = value
    with pytest.raises(ValueError):
        bedrock.BedrockTransport(config, lambda _: pytest.fail("SDK must not be constructed"))


@pytest.mark.parametrize("field", ["additional_model_request_fields", "additionalModelRequestFields"])
def test_client_cannot_supply_provider_fields(field):
    config = routes()
    config["lab-claude-text"]["additional_model_request_fields"] = {"thinking": {"type": "disabled"}}
    with pytest.raises(bedrock.AdapterError) as error:
        bedrock.prepare(json.dumps(payload(**{field: {"thinking": {"type": "adaptive"}}})).encode(), config)
    assert error.value.status == 400


@pytest.mark.parametrize("override", [
    {"model": "arn:aws:bedrock:other"}, {"model": ["bad"]}, {"max_tokens": 129},
    {"max_tokens": True}, {"tools": [{"name": "unsupported"}]}, {"thinking": {}}, {"endpoint_url": "https://else"},
    {"messages": [{"role": "system", "content": "unsupported"}]},
    {"messages": [{"role": "user", "content": [{"type": "image", "data": "bad"}]}]},
    {"temperature": float("nan")}, {"temperature": 0.5, "top_p": 0.5},
    {"stop_sequences": [""]},
])
def test_rejects_before_sdk(override):
    called = []
    adapter = bedrock.BedrockTransport(routes(), lambda region: called.append(region))

    async def check_raw():
        async with httpx.AsyncClient(transport=adapter) as client:
            reply = await client.post("http://fixture", content=json.dumps(payload(**override)))
            assert reply.status_code == 400
    asyncio.run(check_raw())
    assert not called


def test_json_and_incremental_sse(caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    clients = []

    def factory(region):
        assert region == "us-east-1"
        client = Client()
        clients.append(client)
        return client

    async def check():
        async with httpx.AsyncClient(transport=bedrock.BedrockTransport(routes(), factory)) as client:
            response = await client.post("http://fixture", json=payload(),
                                         headers={"x-gateway-request-id": "a" * 32})
            assert response.status_code == 200
            assert response.json()["model"] == "lab-claude-text"
            assert response.json()["usage"] == {"input_tokens": 10, "output_tokens": 8}
            # Capacity remains occupied until cleanup, so wait for worker completion.
            while not clients[0].closed:
                await asyncio.sleep(0.001)
            async with client.stream("POST", "http://fixture", json=payload(stream=True)) as response:
                lines = [line async for line in response.aiter_lines() if line.startswith("data: ")]
                decoded = [json.loads(line[6:]) for line in lines]
                assert decoded[0]["message"]["model"] == "lab-claude-text"
                assert decoded[-1]["type"] == "message_stop"
                assert decoded[-2]["usage"] == {"input_tokens": 10, "output_tokens": 8}
                assert [item["delta"]["text"] for item in decoded if item["type"] == "content_block_delta"] == ["MOCK", "_OK"]
            while not clients[-1].closed:
                await asyncio.sleep(0.001)
    asyncio.run(check())
    assert "aws_request_id=synthetic-aws-id" in caplog.text
    assert "prompt-canary" not in caplog.text
    assert all(len(c.calls) == 1 and c.closed for c in clients)
    assert clients[-1].events.closed


@pytest.mark.parametrize("bad_events", [
    events()[:-1], events()[:-2], [{"messageStart": {"role": "user"}}],
    events()[:2] + [{"contentBlockDelta": {"contentBlockIndex": 2, "delta": {"text": "wrong"}}}],
    events()[:-2] + [{"messageStop": {"stopReason": "tool_use"}}],
    events()[:2] + [{"internalServerException": {"message": "provider-secret-canary"}}],
])
def test_invalid_stream_has_no_success_terminal(bad_events):
    emitted = []
    with pytest.raises(bedrock.AdapterError):
        for chunk in bedrock.stream_events(bad_events, "alias", "id"):
            emitted.append(chunk)
    assert b"event: message_stop" not in b"".join(emitted)


class SDKFailure(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code, "Message": "secret-canary"}}


def test_sdk_error_audit_excludes_untrusted_details(caplog):
    caplog.set_level(logging.WARNING, logger="uvicorn.error")
    assert bedrock.sdk_error(SDKFailure("ValidationException")).status == 502
    assert "code=ValidationException" in caplog.text
    assert "secret-canary" not in caplog.text
    caplog.clear()
    bedrock.sdk_error(SDKFailure("untrusted-code-canary"))
    assert "code=Unclassified" in caplog.text
    assert "untrusted-code-canary" not in caplog.text


@pytest.mark.parametrize("code,status", [
    ("ThrottlingException", 429), ("AccessDeniedException", 503),
    ("ResourceNotFoundException", 503), ("ModelTimeoutException", 504),
    ("UnknownException", 502),
])
def test_errors_and_single_attempt(code, status):
    sdk = Client(failure=SDKFailure(code))

    async def check():
        async with httpx.AsyncClient(transport=bedrock.BedrockTransport(routes(), lambda _: sdk)) as client:
            response = await client.post("http://fixture", json=payload())
            assert response.status_code == status
            assert "secret-canary" not in response.text
        while not sdk.closed:
            await asyncio.sleep(0.001)
    asyncio.run(check())
    assert len(sdk.calls) == 1 and sdk.closed


def test_cancel_keeps_capacity_until_worker_finishes():
    release = threading.Event()
    entered = threading.Event()
    sdk = Client()

    def stalled(**kwargs):
        entered.set()
        release.wait(timeout=5)
        return {"stream": sdk.events}

    sdk.converse_stream = stalled
    adapter = bedrock.BedrockTransport(routes(), lambda _: sdk)

    async def check():
        async with httpx.AsyncClient(transport=adapter) as client:
            task = asyncio.create_task(client.post("http://fixture", json=payload(stream=True)))
            try:
                async with asyncio.timeout(2):
                    while not entered.is_set():
                        await asyncio.sleep(0.001)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert (await client.post("http://fixture", json=payload())).status_code == 429
            finally:
                release.set()
            async with asyncio.timeout(2):
                while adapter.capacity.locked():
                    await asyncio.sleep(0.001)
            assert sdk.closed and sdk.events.closed
    asyncio.run(check())


def test_gateway_authentication_before_bedrock(lab, tmp_path):
    setup_gateway_dpop(lab, tmp_path)
    sdk = Client()
    app = gateway.create_app(
        __import__("certifi").where(), "", dpop_nonce_key=tmp_path / "nonce.key",
        dpop_replay_dir=tmp_path, trust_transport=httpx.MockTransport(lab.trust),
        bedrock_routes=routes(), bedrock_client_factory=lambda _: sdk,
    )
    signer = ProofClient()
    token = lab.token(cnf={"jkt": signer.jkt})

    async def check():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                         base_url="https://127.0.0.1:8082") as client:
                denied = await client.post("/v1/messages", json=payload())
                assert denied.status_code == 401 and not sdk.calls
                challenge = await client.post("/v1/messages", json=payload(),
                                               headers=dpop_headers(token, signer.sign(GATEWAY, token)))
                signer.remember_nonce(GATEWAY, challenge)
                rejected = await client.post("/v1/messages", json=payload(model="unknown"),
                                              headers=dpop_headers(token, signer.sign(GATEWAY, token)))
                assert rejected.status_code == 400 and not sdk.calls
                valid = await client.post("/v1/messages", json=payload(),
                                           headers=dpop_headers(token, signer.sign(GATEWAY, token)))
                assert valid.status_code == 200 and valid.json()["model"] == "lab-claude-text"
                streamed = await client.post("/v1/messages", json=payload(stream=True),
                                              headers=dpop_headers(token, signer.sign(GATEWAY, token)))
                assert streamed.status_code == 200
                assert "event: message_stop" in streamed.text
    asyncio.run(check())
    assert len(sdk.calls) == 2


def test_real_sdk_stubber_contract_and_no_network():
    boto3 = pytest.importorskip("boto3")
    from botocore.config import Config
    from botocore.stub import Stubber

    sdk = boto3.client("bedrock-runtime", region_name="us-east-1",
                       aws_access_key_id="synthetic-offline",
                       aws_secret_access_key="synthetic-offline",
                       config=Config(retries={"total_max_attempts": 1}))
    _, args, _ = bedrock.prepare(json.dumps(payload()).encode(), routes())
    with Stubber(sdk) as stub:
        stub.add_response("converse", {
            "output": {"message": {"role": "assistant", "content": [{"text": "synthetic"}]}},
            "stopReason": "end_turn", "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
            "metrics": {"latencyMs": 1},
        }, args)

        async def check():
            adapter = bedrock.BedrockTransport(routes(), lambda _: sdk)
            async with httpx.AsyncClient(transport=adapter) as client:
                response = await client.post("http://fixture", json=payload())
                assert response.status_code == 200
                assert response.json()["content"][0]["text"] == "synthetic"
                async with asyncio.timeout(2):
                    while adapter.capacity.locked():
                        await asyncio.sleep(0.001)
        asyncio.run(check())
        stub.assert_no_pending_responses()


@pytest.mark.parametrize("error_name,status", [
    ("NoCredentialsError", 503), ("PartialCredentialsError", 503),
    ("ReadTimeoutError", 504), ("ConnectTimeoutError", 504),
])
def test_dependency_error_types(error_name, status):
    error = type(error_name, (Exception,), {})()
    assert bedrock.sdk_error(error).status == status


def test_slow_consumer_bounds_provider_reads():
    read = []
    sdk = Client()

    def many_events():
        yield {"messageStart": {"role": "assistant"}}
        for index in range(100):
            read.append(index)
            yield {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "x"}}}
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield {"metadata": {"usage": {"inputTokens": 1, "outputTokens": 100}}}

    sdk.events = Stream(many_events())
    adapter = bedrock.BedrockTransport(routes(), lambda _: sdk)

    async def check():
        async with httpx.AsyncClient(transport=adapter) as client:
            async with client.stream("POST", "http://fixture", json=payload(stream=True)) as response:
                assert response.status_code == 200
                await asyncio.sleep(0.05)
                assert len(read) <= 3
            async with asyncio.timeout(2):
                while adapter.capacity.locked():
                    await asyncio.sleep(0.001)
        assert sdk.events.closed
    asyncio.run(check())


def test_workload_factory_selects_only_instance_role_and_disables_retries(monkeypatch):
    boto3 = pytest.importorskip("boto3")
    captured = {}

    class Session:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def client(self, service, config):
            captured["service"], captured["config"] = service, config
            return "fixture-client"

    monkeypatch.setattr(boto3, "Session", Session)
    assert bedrock.workload_client("us-east-1") == "fixture-client"
    providers = captured["botocore_session"].get_component("credential_provider").providers
    assert [provider.METHOD for provider in providers] == ["iam-role"]
    assert captured["config"].retries["total_max_attempts"] == 1
    assert captured["config"].proxies == {}
    assert captured["config"].read_timeout == 15
    assert captured["config"].ignore_configured_endpoint_urls is True


@pytest.mark.parametrize("route_change", [
    {"max_output_tokens": 129}, {"capabilities": ["text_input"]},
    {"model_id": "<unselected>"}, {"resource_arns": ["arn:aws:bedrock:*"]},
    {"allowed_parameters": ["unknown"]},
])
def test_bad_routes_fail_configuration(route_change):
    configured = routes()
    configured["lab-claude-text"].update(route_change)
    with pytest.raises(ValueError):
        bedrock.BedrockTransport(configured, lambda _: pytest.fail("Configuration contacted AWS"))


def test_large_and_nontext_responses_rejected():
    for response in (
        {"role": "assistant", "content": [{"toolUse": {}}]},
        {"role": "assistant", "content": [{"text": "x" * (bedrock.LIMIT + 1)}]},
    ):
        sdk = Client()
        standard = sdk.converse

        def converse(**args):
            result = standard(**args)
            result["output"]["message"] = response
            return result

        sdk.converse = converse

        async def check():
            async with httpx.AsyncClient(transport=bedrock.BedrockTransport(routes(), lambda _: sdk)) as client:
                reply = await client.post("http://fixture", json=payload())
                assert reply.status_code == 502
        asyncio.run(check())


def test_inert_cli_fields_and_metadata_are_removed_from_sdk_request():
    data = payload(tools=[], thinking={"type": "disabled"},
                   context_management={"edits": []}, output_config={},
                   metadata={"user_id": "synthetic-user-canary"})
    _, args, _ = bedrock.prepare(json.dumps(data).encode(), routes())
    assert set(args) == {"modelId", "messages", "inferenceConfig"}
    assert "synthetic-user-canary" not in json.dumps(args)


@pytest.mark.parametrize("field,value", [
    ("tools", None), ("tools", [{"name": "unsupported"}]),
    ("thinking", {"type": "enabled", "budget_tokens": 1024}),
    ("thinking", {"type": "adaptive"}), ("context_management", {"edits": [{}]}),
    ("output_config", {"effort": "low"}), ("output_config", {"format": {"type": "json_schema"}}),
    ("metadata", {"other": "unapproved"}), ("metadata", {"user_id": "x" * 4097}),
    ("metadata", {"user_id": 123}),
])
def test_active_or_malformed_cli_fields_remain_rejected(field, value):
    with pytest.raises(bedrock.AdapterError) as rejected:
        bedrock.prepare(json.dumps(payload(**{field: value})).encode(), routes())
    assert rejected.value.status == 400
