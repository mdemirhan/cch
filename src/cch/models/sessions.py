"""Session-level models."""

from __future__ import annotations

from pydantic import BaseModel, Field
from PySide6.QtCore import Qt


class SessionRoles:
    """Named Qt UserRole offsets for SessionSummary data in list models."""

    ID = Qt.ItemDataRole.UserRole
    MODEL = Qt.ItemDataRole.UserRole + 1
    INPUT_TOKENS = Qt.ItemDataRole.UserRole + 2
    OUTPUT_TOKENS = Qt.ItemDataRole.UserRole + 3
    MODIFIED_AT = Qt.ItemDataRole.UserRole + 4
    MESSAGE_COUNT = Qt.ItemDataRole.UserRole + 5
    PROVIDER = Qt.ItemDataRole.UserRole + 6
    FILE_PATH = Qt.ItemDataRole.UserRole + 7


class SessionSummary(BaseModel):
    """Summary of a session for list views."""

    session_id: str
    provider: str = "claude"
    file_path: str = ""
    project_id: str = ""
    project_name: str = ""
    first_prompt: str = ""
    summary: str = ""
    message_count: int = 0
    user_message_count: int = 0
    assistant_message_count: int = 0
    tool_call_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cache_creation_tokens: int = 0
    model: str = ""
    models_used: str = ""
    git_branch: str = ""
    cwd: str = ""
    created_at: str = ""
    modified_at: str = ""
    duration_ms: int = 0
    is_sidechain: bool = False


class ToolCallView(BaseModel):
    """A tool call for display in the session viewer."""

    tool_use_id: str
    tool_name: str
    input_json: str = "{}"
    timestamp: str = ""


class MessageView(BaseModel):
    """A message for display in the session viewer."""

    uuid: str
    model: str = ""
    type: str = ""
    content_text: str = ""
    content_json: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    timestamp: str = ""
    is_sidechain: bool = False
    sequence_num: int = 0
    tool_calls: list[ToolCallView] = Field(default_factory=list)


class SessionDetail(SessionSummary):
    """Full session detail including messages."""

    messages: list[MessageView] = Field(default_factory=list)
