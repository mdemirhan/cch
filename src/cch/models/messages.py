"""Message-level models for parsed JSONL data."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    """Token usage from a single API call."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


class ToolUseBlock(BaseModel):
    """A tool_use content block from an assistant message."""

    tool_use_id: str
    name: str
    input_json: str = "{}"


class ContentBlock(BaseModel):
    """A single content block (text, tool_use, tool_result, thinking)."""

    type: str
    text: str = ""
    tool_use: ToolUseBlock | None = None


class ParsedMessage(BaseModel):
    """A parsed message from a JSONL session file."""

    uuid: str = ""
    parent_uuid: str | None = None
    type: str  # user, assistant, tool_use, tool_result, thinking, system
    model: str = ""
    content_blocks: list[ContentBlock] = Field(default_factory=list)
    content_text: str = ""
    usage: TokenUsage = Field(default_factory=TokenUsage)
    timestamp: str = ""
    is_sidechain: bool = False
    sequence_num: int = 0
