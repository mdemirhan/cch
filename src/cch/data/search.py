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
        roles: list[str] | None = None,
        project_id: str = "",
        project_ids: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> SearchResults:
        """Search messages using FTS5.

        Args:
            query: Full-text search query.
            roles: Filter by categories. Valid values: "user", "assistant",
                   "tool_call", "thinking", "tool_result", "system".
                   None or empty means all.
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

        if roles:
            role_clauses: list[str] = []
            for r in roles:
                if r == "user":
                    role_clauses.append(
                        "m.role = 'user' AND m.type = 'user' AND "
                        "TRIM(COALESCE(m.content_text, '')) != '' AND "
                        "EXISTS ("
                        "  SELECT 1 FROM json_each(m.content_json) j "
                        "  WHERE json_extract(j.value, '$.type') = 'text'"
                        ")"
                    )
                elif r == "assistant":
                    role_clauses.append(
                        "m.role = 'assistant' AND EXISTS ("
                        "  SELECT 1 FROM json_each(m.content_json) j "
                        "  WHERE json_extract(j.value, '$.type') = 'text' "
                        "    AND TRIM(COALESCE(json_extract(j.value, '$.text'), '')) != ''"
                        ")"
                    )
                elif r == "tool_call":
                    role_clauses.append(
                        "m.role = 'assistant' AND ("
                        "EXISTS ("
                        "  SELECT 1 FROM json_each(m.content_json) j "
                        "  WHERE json_extract(j.value, '$.type') = 'tool_use'"
                        ") OR "
                        "EXISTS (SELECT 1 FROM tool_calls tc WHERE tc.message_uuid = m.uuid)"
                        ")"
                    )
                elif r == "thinking":
                    role_clauses.append(
                        "m.role = 'assistant' AND EXISTS ("
                        "  SELECT 1 FROM json_each(m.content_json) j "
                        "  WHERE json_extract(j.value, '$.type') = 'thinking' "
                        "    AND TRIM(COALESCE(json_extract(j.value, '$.text'), '')) != ''"
                        ")"
                    )
                elif r == "tool_result":
                    role_clauses.append(
                        "m.role = 'user' AND m.type = 'user' AND "
                        "EXISTS ("
                        "  SELECT 1 FROM json_each(m.content_json) j "
                        "  WHERE json_extract(j.value, '$.type') = 'tool_result'"
                        ")"
                    )
                elif r == "system":
                    role_clauses.append("m.type IN ('system', 'summary')")
            if role_clauses:
                conditions.append("(" + " OR ".join(role_clauses) + ")")

        if project_ids:
            normalized_ids = [pid for pid in project_ids if pid]
            if normalized_ids:
                placeholders = ",".join("?" for _ in normalized_ids)
                conditions.append(f"s.project_id IN ({placeholders})")
                params.extend(normalized_ids)
        elif project_id:
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
                p.project_name,
                COALESCE(s.provider, p.provider, 'claude') as provider
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
                provider=row["provider"] or "claude",
                role=row["role"] or "",
                snippet=row["snippet"] or "",
                timestamp=row["timestamp"] or "",
            )
            for row in rows
        ]

        return SearchResults(results=results, total_count=total_count, query=query)


def _escape_fts_query(query: str) -> str:
    """Escape a raw query for FTS5 by quoting terms safely."""
    terms = query.strip().split()
    if not terms:
        return '""'
    escaped: list[str] = []
    for term in terms:
        if not term:
            continue
        safe_term = term.replace('"', '""')
        escaped.append(f'"{safe_term}"')
    return " ".join(escaped)
