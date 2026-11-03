
import asyncio

from app.streaming import stream_mock_response


def test_stream_generator_cancellation():
    """Verify a streaming task stops when cancelled."""

    async def exercise_cancellation():
        generator = stream_mock_response(
            "claude-sonnet-4-6",
            delay=10.0,
        )

        async def consume():
            async for _ in generator:
                pass

        task = asyncio.create_task(consume())

        # Let the generator begin emitting initial events.
        await asyncio.sleep(0.1)

        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError(
                "Streaming task did not stop after cancellation"
            )

        assert task.cancelled()

    asyncio.run(exercise_cancellation())
