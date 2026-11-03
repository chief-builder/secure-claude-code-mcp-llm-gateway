import asyncio
import json

from app.streaming import stream_mock_response


def test_stream_event_sequence():
    async def collect():
        return [
            event
            async for event in stream_mock_response(
                "claude-sonnet-4-6"
            )
        ]

    events = asyncio.run(collect())

    parsed = []

    for event in events:
        lines = event.strip().splitlines()

        event_type = lines[0].removeprefix("event: ")
        data = json.loads(
            lines[1].removeprefix("data: ")
        )

        assert event_type == data["type"]
        parsed.append((event_type, data))

    assert [event_type for event_type, _ in parsed] == [
        "message_start",
        "content_block_start",
        "content_block_delta",
        "content_block_delta",
        "content_block_stop",
        "message_delta",
        "message_stop",
    ]

    text = "".join(
        data["delta"]["text"]
        for event_type, data in parsed
        if event_type == "content_block_delta"
    )

    assert text == "MOCK_OK — Local inference working"

    assert parsed[-1][0] == "message_stop"
