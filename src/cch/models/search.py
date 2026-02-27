"""Search models."""

from __future__ import annotations

from pydantic import BaseModel, Field
from PySide6.QtCore import Qt


class SearchResultRoles:
    """Named Qt UserRole offsets for SearchResult data in list models."""

    SESSION_ID = Qt.ItemDataRole.UserRole
    MESSAGE_TYPE = Qt.ItemDataRole.UserRole + 1
    PROJECT_NAME = Qt.ItemDataRole.UserRole + 2
    TIMESTAMP = Qt.ItemDataRole.UserRole + 3
    PROVIDER = Qt.ItemDataRole.UserRole + 4


class SearchResult(BaseModel):
    """A single search result with highlighted excerpt."""

    message_uuid: str
    session_id: str
    project_name: str = ""
    provider: str = "claude"
    message_type: str = ""
    snippet: str = ""
    timestamp: str = ""


class SearchResults(BaseModel):
    """Paginated search results."""

    results: list[SearchResult] = Field(default_factory=list)
    total_count: int = 0
    query: str = ""
    type_counts: dict[str, int] = Field(default_factory=dict)
