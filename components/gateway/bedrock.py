"""Bounded offline-testable Converse adapter behind the gateway HTTP relay."""

import asyncio
import concurrent.futures
import json
import logging
import math
import re
import threading
import uuid

import httpx

from gateway import strict_json as read_object

LIMIT = 1024 * 1024
REQUIRED_CAPABILITIES = {"text_input", "text_output", "converse", "converse_stream"}
PARAMETERS = {"max_tokens": "maxTokens", "temperature": "temperature",
              "top_p": "topP", "stop_sequences": "stopSequences"}
STOP = {"end_turn": "end_turn", "max_tokens": "max_tokens", "stop_sequence": "stop_sequence"}
LOG = logging.getLogger("uvicorn.error")


class AdapterError(Exception):
    def __init__(self, status):
        self.status = status


def load_routes(path):
    return validate_routes(read_object(path.read_bytes()))


def validate_routes(routes):
    if not isinstance(routes, dict) or len(routes) != 1:
        raise ValueError("The initial Bedrock lab requires one route")
    alias, route = next(iter(routes.items()))
    expected = {"region", "model_id", "resource_arns", "capabilities", "max_output_tokens",
                "allowed_parameters", "route_version"}
    if (not isinstance(alias, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", alias)
            or not isinstance(route, dict) or not expected <= set(route)
            or set(route) - expected - {"additional_model_request_fields"}):
        raise ValueError("Invalid Bedrock route")
    if ("additional_model_request_fields" in route
            and route["additional_model_request_fields"] != {"thinking": {"type": "disabled"}}):
        raise ValueError("Only disabled provider thinking is supported")
    if (not isinstance(route["region"], str) or not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-[0-9]+", route["region"])
            or not isinstance(route["model_id"], str) or not route["model_id"]
            or len(route["model_id"]) > 2048 or any(c.isspace() for c in route["model_id"])
            or "<" in route["model_id"] or "://" in route["model_id"]
            or not isinstance(route["resource_arns"], list) or not route["resource_arns"]
            or any(not isinstance(arn, str) or not arn.startswith("arn:aws") or "*" in arn
                   for arn in route["resource_arns"])
            or not isinstance(route["capabilities"], list)
            or any(not isinstance(c, str) for c in route["capabilities"])
            or set(route["capabilities"]) != REQUIRED_CAPABILITIES
            or len(route["capabilities"]) != 4
            or type(route["max_output_tokens"]) is not int or not 1 <= route["max_output_tokens"] <= 128
            or not isinstance(route["allowed_parameters"], list)
            or any(not isinstance(p, str) or p not in PARAMETERS for p in route["allowed_parameters"])
            or len(set(route["allowed_parameters"])) != len(route["allowed_parameters"])
            or "max_tokens" not in route["allowed_parameters"]
            or not isinstance(route["route_version"], str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", route["route_version"])):
        raise ValueError("Invalid Bedrock route")
    return json.loads(json.dumps(routes))


def text_blocks(value):
    if isinstance(value, str) and value:
        return [{"text": value}]
    if (isinstance(value, list) and value and all(isinstance(block, dict)
            and set(block) == {"type", "text"} and block["type"] == "text"
            and isinstance(block["text"], str) and block["text"] for block in value)):
        return [{"text": block["text"]} for block in value]
    raise AdapterError(400)


def text_profile(data):
    """Validate and remove only inert CLI fields and bounded attribution metadata."""
    normalized = dict(data)
    defaults = {"tools": [], "thinking": {"type": "disabled"},
                "context_management": {"edits": []}, "output_config": {}}
    for name, disabled in defaults.items():
        if name in normalized:
            value = normalized.pop(name)
            if type(value) is not type(disabled) or value != disabled:
                raise AdapterError(400)
    if "metadata" in normalized:
        metadata = normalized.pop("metadata")
        if (not isinstance(metadata, dict) or set(metadata) - {"user_id"}
                or ("user_id" in metadata and (
                    not isinstance(metadata["user_id"], str) or len(metadata["user_id"]) > 4096))):
            raise AdapterError(400)
    return normalized


def prepare(body, routes):
    data = text_profile(read_object(body))
    if (set(data) - ({"model", "messages", "system", "stream"} | PARAMETERS.keys())
            or type(data.get("stream", False)) is not bool):
        raise AdapterError(400)
    alias = data.get("model")
    if not isinstance(alias, str) or alias not in routes:
        raise AdapterError(400)
    route = routes[alias]
    if (any(p not in route["allowed_parameters"] for p in PARAMETERS if p in data)
            or type(data.get("max_tokens")) is not int
            or not 1 <= data["max_tokens"] <= route["max_output_tokens"]):
        raise AdapterError(400)
    for field in ("temperature", "top_p"):
        if field in data and (type(data[field]) not in (int, float)
                              or not math.isfinite(data[field]) or not 0 <= data[field] <= 1):
            raise AdapterError(400)
    if "stop_sequences" in data and (
        not isinstance(data["stop_sequences"], list) or len(data["stop_sequences"]) > 4
        or any(not isinstance(s, str) or not 1 <= len(s) <= 256 for s in data["stop_sequences"])
    ):
        raise AdapterError(400)
    # A route opts into one of the two sampling controls to avoid unsupported combinations.
    if "temperature" in data and "top_p" in data:
        raise AdapterError(400)
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        raise AdapterError(400)
    converted = []
    for message in messages:
        if (not isinstance(message, dict) or set(message) != {"role", "content"}
                or message["role"] not in ("user", "assistant")):
            raise AdapterError(400)
        converted.append({"role": message["role"], "content": text_blocks(message["content"])})
    args = {"modelId": route["model_id"], "messages": converted,
            "inferenceConfig": {PARAMETERS[p]: data[p] for p in PARAMETERS if p in data}}
    if "additional_model_request_fields" in route:
        args["additionalModelRequestFields"] = json.loads(json.dumps(route["additional_model_request_fields"]))
    if "system" in data:
        args["system"] = text_blocks(data["system"])
    return alias, args, data.get("stream", False)


def usage(value):
    if (not isinstance(value, dict) or any(type(value.get(name)) is not int or value[name] < 0
                                          for name in ("inputTokens", "outputTokens"))):
        raise AdapterError(502)
    return {"input_tokens": value["inputTokens"], "output_tokens": value["outputTokens"]}


def output_blocks(value):
    if not isinstance(value, list) or not value:
        raise AdapterError(502)
    blocks = []
    for block in value:
        if not isinstance(block, dict) or set(block) != {"text"} or not isinstance(block["text"], str):
            raise AdapterError(502)
        blocks.append({"type": "text", "text": block["text"]})
    return blocks


def packed(value):
    data = json.dumps(value, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    if len(data) > LIMIT:
        raise AdapterError(502)
    return data


def sse(event, **fields):
    return b"event: " + event.encode() + b"\ndata: " + packed({"type": event, **fields}) + b"\n\n"


def message(alias, identity, content, stop, tokens):
    if stop not in STOP:
        raise AdapterError(502)
    return {"id": identity, "type": "message", "role": "assistant", "model": alias,
            "content": content, "stop_reason": STOP[stop], "stop_sequence": None, "usage": tokens}


def stream_events(events, alias, identity):
    started = stopped = metadata = False
    active = None
    next_index = 0
    reason = None
    for event in events:
        if not isinstance(event, dict) or len(event) != 1:
            raise AdapterError(502)
        kind, value = next(iter(event.items()))
        if kind.endswith("Exception"):
            raise AdapterError(429 if kind == "throttlingException" else 502)
        if not isinstance(value, dict):
            raise AdapterError(502)
        if kind == "messageStart" and not started:
            if value.get("role") != "assistant":
                raise AdapterError(502)
            started = True
            initial = message(alias, identity, [], "end_turn", {"input_tokens": 0, "output_tokens": 0})
            initial["stop_reason"] = None
            yield sse("message_start", message=initial)
        elif kind == "contentBlockStart" and started and not stopped and active is None:
            # Text blocks can start implicitly at the first delta. Tool starts are unsupported.
            if value.get("start") != {} or value.get("contentBlockIndex") != next_index:
                raise AdapterError(502)
            active = next_index
            yield sse("content_block_start", index=active, content_block={"type": "text", "text": ""})
        elif kind == "contentBlockDelta" and started and not stopped:
            index, delta = value.get("contentBlockIndex"), value.get("delta")
            if type(index) is not int or not isinstance(delta, dict) or set(delta) != {"text"} or not isinstance(delta["text"], str):
                raise AdapterError(502)
            if active is None:
                if index != next_index:
                    raise AdapterError(502)
                active = index
                yield sse("content_block_start", index=index, content_block={"type": "text", "text": ""})
            if index != active:
                raise AdapterError(502)
            yield sse("content_block_delta", index=index, delta={"type": "text_delta", "text": delta["text"]})
        elif kind == "contentBlockStop" and active is not None and not stopped:
            if value.get("contentBlockIndex") != active:
                raise AdapterError(502)
            yield sse("content_block_stop", index=active)
            active = None
            next_index += 1
        elif kind == "messageStop" and started and not stopped and active is None and next_index:
            reason = value.get("stopReason")
            if reason not in STOP:
                raise AdapterError(502)
            stopped = True
        elif kind == "metadata" and stopped and not metadata:
            tokens = usage(value.get("usage"))
            metadata = True
            # Update input usage after Bedrock supplies its trailing metadata.
            yield sse("message_delta", delta={"stop_reason": reason, "stop_sequence": None}, usage=tokens)
        else:
            raise AdapterError(502)
    if not (started and stopped and metadata):
        raise AdapterError(502)
    yield sse("message_stop")


def sdk_error(error):
    response = getattr(error, "response", {})
    code = response.get("Error", {}).get("Code", "") if isinstance(response, dict) else ""
    categories = {"ClientError", "ParamValidationError", "NoCredentialsError", "PartialCredentialsError",
                  "CredentialRetrievalError", "ReadTimeoutError", "ConnectTimeoutError",
                  "EndpointConnectionError", "SSLError"}
    codes = {"ThrottlingException", "ServiceQuotaExceededException", "AccessDeniedException",
             "UnrecognizedClientException", "ExpiredTokenException", "ResourceNotFoundException",
             "ServiceUnavailableException", "ModelTimeoutException", "ValidationException",
             "ModelErrorException", "InternalServerException"}
    LOG.warning("bedrock event=sdk_error category=%s code=%s",
                type(error).__name__ if type(error).__name__ in categories else "UnexpectedError",
                code if isinstance(code, str) and code in codes else "Unclassified")
    if code in ("ThrottlingException", "ServiceQuotaExceededException"):
        return AdapterError(429)
    if code in ("AccessDeniedException", "UnrecognizedClientException", "ExpiredTokenException",
                "ResourceNotFoundException", "ServiceUnavailableException"):
        return AdapterError(503)
    if code == "ModelTimeoutException" or type(error).__name__ in ("ReadTimeoutError", "ConnectTimeoutError"):
        return AdapterError(504)
    if type(error).__name__ in ("NoCredentialsError", "PartialCredentialsError", "CredentialRetrievalError"):
        return AdapterError(503)
    return AdapterError(502)


def workload_client(region):
    """Only invoked on the AWS host in the separately reviewed live stage."""
    import boto3
    from botocore.config import Config
    import botocore.session
    from botocore.credentials import CredentialResolver, InstanceMetadataProvider
    from botocore.utils import InstanceMetadataFetcher

    provider = InstanceMetadataProvider(
        iam_role_fetcher=InstanceMetadataFetcher(timeout=2, num_attempts=1,
                                                 config={"ec2_metadata_v1_disabled": True})
    )
    core = botocore.session.get_session()
    core.register_component("credential_provider", CredentialResolver([provider]))
    session = boto3.Session(botocore_session=core, region_name=region)
    return session.client("bedrock-runtime", config=Config(
        connect_timeout=2, read_timeout=15, retries={"total_max_attempts": 1, "mode": "standard"},
        max_pool_connections=1, proxies={}, ignore_configured_endpoint_urls=True,
    ))


class WorkerStream(httpx.AsyncByteStream):
    def __init__(self, queue, stop, first):
        self.queue, self.stop, self.first = queue, stop, first

    async def __aiter__(self):
        item = self.first
        while item is not None:
            if isinstance(item, AdapterError):
                raise httpx.RemoteProtocolError("Bedrock stream failed")
            yield item
            item = await self.queue.get()

    async def aclose(self):
        self.stop.set()


class BedrockTransport(httpx.AsyncBaseTransport):
    def __init__(self, routes, client_factory=workload_client):
        self.routes = validate_routes(routes)
        self.client_factory = client_factory
        self.capacity = threading.Lock()

    async def handle_async_request(self, request):
        try:
            body = await request.aread()
            if len(body) > LIMIT:
                raise AdapterError(413)
            alias, args, streamed = prepare(body, self.routes)
        except (ValueError, TypeError, KeyError):
            return httpx.Response(400, json={"error": "Invalid inference request"})
        except AdapterError as error:
            return httpx.Response(error.status, json={"error": "Invalid inference request"})
        if not self.capacity.acquire(blocking=False):
            return httpx.Response(429, json={"error": "Inference capacity unavailable"})
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue(maxsize=2)
        stopped = threading.Event()
        route = self.routes[alias]
        identity = "msg_" + uuid.uuid4().hex
        gateway_id = request.headers.get("x-gateway-request-id", "")

        def emit(value):
            if stopped.is_set() or loop.is_closed():
                return False
            operation = queue.put(value)
            try:
                pending = asyncio.run_coroutine_threadsafe(operation, loop)
            except RuntimeError:
                operation.close()
                return False
            while True:
                try:
                    pending.result(timeout=0.1)
                    return True
                except concurrent.futures.TimeoutError:
                    if stopped.is_set():
                        pending.cancel()
                        return False

        def worker():
            client = events = None
            try:
                client = self.client_factory(route["region"])
                result = (client.converse_stream if streamed else client.converse)(**args)
                request_id = result.get("ResponseMetadata", {}).get("RequestId", "")
                if re.fullmatch(r"[A-Za-z0-9-]{1,128}", request_id) and re.fullmatch(r"[0-9a-f]{32}", gateway_id):
                    LOG.info("bedrock event=response route=%s revision=%s gateway_request_id=%s aws_request_id=%s",
                             alias, route["route_version"], gateway_id, request_id)
                if streamed:
                    events = result["stream"]
                    chunks = stream_events(events, alias, identity)
                else:
                    output = result["output"]["message"]
                    if output["role"] != "assistant":
                        raise AdapterError(502)
                    chunks = [packed(message(alias, identity, output_blocks(output["content"]),
                                              result["stopReason"], usage(result["usage"])))]
                size = 0
                for chunk in chunks:
                    size += len(chunk)
                    if size > LIMIT:
                        raise AdapterError(502)
                    if not emit(chunk):
                        break
            except Exception as error:
                emit(error if isinstance(error, AdapterError) else sdk_error(error))
            finally:
                try:
                    for resource in (events, client):
                        if resource is not None:
                            try:
                                resource.close()
                            except Exception:
                                LOG.warning("bedrock event=cleanup_failed")
                finally:
                    self.capacity.release()
                    emit(None)

        threading.Thread(target=worker, name="bedrock-inference", daemon=True).start()
        try:
            first = await queue.get()
            if isinstance(first, AdapterError):
                stopped.set()
                return httpx.Response(first.status, json={"error": "Inference dependency failed"})
            if first is None:
                stopped.set()
                return httpx.Response(502)
            return httpx.Response(200, stream=WorkerStream(queue, stopped, first),
                                  headers={"content-type": "text/event-stream" if streamed else "application/json"})
        except BaseException:
            stopped.set()
            raise
