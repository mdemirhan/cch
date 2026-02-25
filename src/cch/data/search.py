"""FTS5 search queries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cch.models.search import SearchResult, SearchResults

if TYPE_CHECKING:
    from cch.data.db import Database


class SearchEngine:
    """FTS5-based search over indexed messages."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def search(
        self,
        query: str,
        role: str = "",
        project_id: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> SearchResults:
        """Search messages using FTS5.

        Args:
            query: Full-text search query.
            role: Filter by role (user/assistant). Empty for all.
            project_id: Filter by project. Empty for all.
            limit: Maximum results to return.
            offset: Result offset for pagination.

        Returns:
            SearchResults with highlighted excerpts.
        """
        if not query.strip():
            return SearchResults(query=query)

        # Escape FTS5 special characters
        fts_query = _escape_fts_query(query)

        conditions: list[str] = []
        params: list[str | int] = [fts_query]

        if role:
            conditions.append("m.role = ?")
            params.append(role)

        if project_id:
            conditions.append("s.project_id = ?")
            params.append(project_id)

        where_clause = ""
        if conditions:
            where_clause = "AND " + " AND ".join(conditions)

        # Count total results
        count_sql = f"""
            SELECT COUNT(*) as cnt
            FROM messages_fts f
            JOIN messages m ON m.rowid = f.rowid
            JOIN sessions s ON s.session_id = m.session_id
            WHERE messages_fts MATCH ?
            {where_clause}
        """
        count_row = await self._db.fetch_one(count_sql, tuple(params))
        total_count = count_row["cnt"] if count_row else 0

        # Fetch results with snippets
        params_with_pagination = [*params, limit, offset]
        results_sql = f"""
            SELECT
                m.uuid as message_uuid,
                m.session_id,
                m.role,
                m.timestamp,
                snippet(messages_fts, 0, '<mark>', '</mark>', '...', 64) as snippet,
                p.project_name
            FROM messages_fts f
            JOIN messages m ON m.rowid = f.rowid
            JOIN sessions s ON s.session_id = m.session_id
            LEFT JOIN projects p ON p.project_id = s.project_id
            WHERE messages_fts MATCH ?
            {where_clause}
            ORDER BY rank
            LIMIT ? OFFSET ?
        """
        rows = await self._db.fetch_all(results_sql, tuple(params_with_pagination))

        results = [
            SearchResult(
                message_uuid=row["message_uuid"],
                session_id=row["session_id"],
                project_name=row["project_name"] or "",
                role=row["role"] or "",
                snippet=row["snippet"] or "",
                timestamp=row["timestamp"] or "",
            )
            for row in rows
        ]

        return SearchResults(results=results, total_count=total_count, query=query)


def _escape_fts_query(query: str) -> str:
    """Escape a raw query for FTS5 by wrapping terms in quotes."""
    terms = query.strip().split()
    if not terms:
        return '""'
    escaped = [f'"{term}"' for term in terms]
    return " ".join(escaped)
