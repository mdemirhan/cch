"""Search service wrapping FTS5 search."""

from __future__ import annotations

from typing import TYPE_CHECKING

from result import Err, Ok, Result

from cch.models.search import SearchResults

if TYPE_CHECKING:
    from cch.data.search import SearchEngine


class SearchService:
    """Service for full-text search."""

    def __init__(self, search_engine: SearchEngine) -> None:
        self._engine = search_engine

    async def search(
        self,
        query: str,
        role: str = "",
        project_id: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> Result[SearchResults, str]:
        """Search messages with FTS5."""
        if not query.strip():
            return Err("Search query cannot be empty")
        try:
            results = await self._engine.search(
                query=query, role=role, project_id=project_id, limit=limit, offset=offset
            )
            return Ok(results)
        except Exception as exc:
            return Err(f"Search failed: {exc}")
