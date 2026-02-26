"""Search models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """A single search result with highlighted excerpt."""

    message_uuid: str
    session_id: str
    project_name: str = ""
    provider: str = "claude"
    role: str = ""
    snippet: str = ""
    timestamp: str = ""


class SearchResults(BaseModel):
    """Paginated search results."""

    results: list[SearchResult] = Field(default_factory=list)
    total_count: int = 0
    query: str = ""
