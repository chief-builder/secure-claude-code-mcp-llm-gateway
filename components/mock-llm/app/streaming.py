import json
import uuid
from collections.abc import AsyncIterator

import asyncio


MOCK_RESPONSE = "MOCK_OK — Local inference working"


def sse_event(event_type: str, data: dict) -> str:
    """Encode one Anthropic-compatible SSE event."""
    return (
        f"event: {event_type}\n"
        f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    )



async def stream_mock_response(
    model: str,
    delay: float = 0.15,
) -> AsyncIterator[str]:
    """Generate a deterministic Anthropic Messages SSE stream."""
    message_id = f"msg_mock_{uuid.uuid4().hex[:12]}"

    yield sse_event(
        "message_start",
        {
            "type": "message_start",
            "message": {
                "id": message_id,
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 0,
                },
            },
        },
    )

    yield sse_event(
        "content_block_start",
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "text", "text": ""},
        },
    )

    for fragment in ["MOCK_OK — ", "Local inference working"]:
        await asyncio.sleep(delay)

        yield sse_event(
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {
                    "type": "text_delta",
                    "text": fragment,
                },
            },
        )

    yield sse_event(
        "content_block_stop",
        {"type": "content_block_stop", "index": 0},
    )

    yield sse_event(
        "message_delta",
        {
            "type": "message_delta",
            "delta": {
                "stop_reason": "end_turn",
                "stop_sequence": None,
            },
            "usage": {"output_tokens": 8},
        },
    )

    yield sse_event(
        "message_stop",
        {"type": "message_stop"},
    )
