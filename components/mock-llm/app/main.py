import hmac
import os
import uuid

from fastapi import FastAPI, Header, HTTPException, Response, Query
from fastapi.responses import StreamingResponse
from app.streaming import stream_mock_response

from app.models import (
    MessagesRequest,
    MessagesResponse,
    TextBlock,
    TokenUsage,
)

app = FastAPI(
    title="Local Mock LLM API",
    version="0.1.0",
    description="Mock Anthropic-compatible LLM API for Claude Code testing",
)

MOCK_TOKEN = os.environ.get("MOCK_LLM_TOKEN", "local-mock-only")


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "mock-llm",
        "version": "0.1.0",
    }


@app.post("/v1/messages")
def create_message(
    request: MessagesRequest,
    response: Response,
    authorization: str | None = Header(default=None),
    delay: float = Query(default=0.15, ge=0.0, le=10.0),
):
    expected = f"Bearer {MOCK_TOKEN}"

    if authorization is None or not hmac.compare_digest(
        authorization, expected
    ):
        raise HTTPException(
            status_code=401,
            detail={
                "type": "authentication_error",
                "message": "Invalid mock credential",
            },
        )

    if request.stream:
        return StreamingResponse(
        stream_mock_response(request.model, delay=delay),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "request-id": str(uuid.uuid4()),
        },
    )

    response.headers["request-id"] = str(uuid.uuid4())

    return MessagesResponse(
        id=f"msg_mock_{uuid.uuid4().hex[:12]}",
        model=request.model,
        delay=delay,
        content=[
            TextBlock(text="MOCK_OK — Local inference working")
        ],
        usage=TokenUsage(input_tokens=10, output_tokens=8),
    )
