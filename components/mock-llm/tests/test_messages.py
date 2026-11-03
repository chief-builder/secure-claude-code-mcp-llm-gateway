from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

VALID_REQUEST = {
    "model": "claude-sonnet-4-6",
    "max_tokens": 100,
    "messages": [
        {"role": "user", "content": "Hello"}
    ],
    "stream": False,
}

HEADERS = {
    "Authorization": "Bearer local-mock-only"
}


def test_valid_message():
    response = client.post(
        "/v1/messages",
        json=VALID_REQUEST,
        headers=HEADERS,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["type"] == "message"
    assert body["role"] == "assistant"
    assert body["model"] == "claude-sonnet-4-6"
    assert body["content"][0]["text"] == (
        "MOCK_OK — Local inference working"
    )
    assert body["stop_reason"] == "end_turn"
    assert "request-id" in response.headers


def test_missing_token():
    response = client.post(
        "/v1/messages",
        json=VALID_REQUEST,
    )

    assert response.status_code == 401


def test_invalid_token():
    response = client.post(
        "/v1/messages",
        json=VALID_REQUEST,
        headers={
            "Authorization": "Bearer incorrect-token"
        },
    )

    assert response.status_code == 401


def test_missing_model():
    payload = VALID_REQUEST.copy()
    payload.pop("model")

    response = client.post(
        "/v1/messages",
        json=payload,
        headers=HEADERS,
    )

    assert response.status_code == 422


def test_streaming_message():
    payload = {
        **VALID_REQUEST,
        "stream": True,
    }

    response = client.post(
        "/v1/messages",
        json=payload,
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "text/event-stream"
    )
    assert "request-id" in response.headers

    body = response.text

    assert "event: message_start" in body
    assert "event: content_block_delta" in body
    assert "event: message_delta" in body
    assert "event: message_stop" in body
    assert "MOCK_OK" in body
