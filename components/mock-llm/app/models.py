from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str | list[dict[str, Any]]


class MessagesRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = Field(min_length=1)
    max_tokens: int = Field(gt=0)
    messages: list[Message] = Field(min_length=1)
    stream: bool = False
    system: str | list[dict[str, Any]] | None = None
    tools: list[dict[str, Any]] | None = None


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class TokenUsage(BaseModel):
    input_tokens: int = 10
    output_tokens: int = 8


class MessagesResponse(BaseModel):
    id: str
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    model: str
    content: list[TextBlock]
    stop_reason: Literal["end_turn"] = "end_turn"
    stop_sequence: None = None
    usage: TokenUsage
