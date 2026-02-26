"""FTS5 search queries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cch.models.categories import (
    ALL_CATEGORY_KEYS,
    normalize_category_keys,
    normalize_message_type,
)
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
        providers: list[str] | None = None,
        project_query: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> SearchResults:
        """Search messages using FTS5.

        Args:
            query: Full-text search query.
            roles: Filter by categories. Valid values: "user", "assistant",
                   "tool_use", "thinking", "tool_result", "system".
                   None or empty means all.
            project_id: Filter by project. Empty for all.
            providers: Optional provider filter values (claude/codex/gemini).
            project_query: Optional project name/path substring filter.
            limit: Maximum results to return.
            offset: Result offset for pagination.

        Returns:
            SearchResults with highlighted excerpts.
        """
        default_type_counts = {key: 0 for key in ALL_CATEGORY_KEYS}
        if not query.strip():
            return SearchResults(query=query, type_counts=default_type_counts)

        # Escape FTS5 special characters
        fts_query = _escape_fts_query(query)

        conditions, filter_params = _build_filter_conditions(
            roles=roles,
            project_id=project_id,
            project_ids=project_ids,
            providers=providers,
            project_query=project_query,
            include_roles=True,
        )
        params: list[str | int] = [fts_query, *filter_params]

        where_clause = ""
        if conditions:
            where_clause = "AND " + " AND ".join(conditions)

        # Count total results
        count_sql = f"""
            SELECT COUNT(*) as cnt
            FROM messages_fts f
            JOIN messages m ON m.id = f.rowid
            JOIN sessions s ON s.session_id = m.session_id
            LEFT JOIN projects p ON p.project_id = s.project_id
            WHERE messages_fts MATCH ?
            {where_clause}
        """
        count_row = await self._db.fetch_one(count_sql, tuple(params))
        total_count = count_row["cnt"] if count_row else 0

        # Build message-type counts using provider/project filters, but without
        # applying active type chips so users can see available result types.
        type_conditions, type_filter_params = _build_filter_conditions(
            roles=roles,
            project_id=project_id,
            project_ids=project_ids,
            providers=providers,
            project_query=project_query,
            include_roles=False,
        )
        type_where_clause = ""
        if type_conditions:
            type_where_clause = "AND " + " AND ".join(type_conditions)
        type_counts_sql = f"""
            SELECT m.type as message_type, COUNT(*) as cnt
            FROM messages_fts f
            JOIN messages m ON m.id = f.rowid
            JOIN sessions s ON s.session_id = m.session_id
            LEFT JOIN projects p ON p.project_id = s.project_id
            WHERE messages_fts MATCH ?
            {type_where_clause}
            GROUP BY m.type
        """
        type_rows = await self._db.fetch_all(
            type_counts_sql, tuple([fts_query, *type_filter_params])
        )
        type_counts = {key: 0 for key in ALL_CATEGORY_KEYS}
        for row in type_rows:
            category_key = normalize_message_type(row["message_type"] or "")
            type_counts[category_key] += int(row["cnt"] or 0)

        # Fetch results with snippets
        params_with_pagination = [*params, limit, offset]
        results_sql = f"""
            SELECT
                m.uuid as message_uuid,
                m.session_id,
                m.type as message_type,
                m.timestamp,
                snippet(messages_fts, 0, '<mark>', '</mark>', '...', 64) as snippet,
                p.project_name,
                COALESCE(s.provider, p.provider, 'claude') as provider
            FROM messages_fts f
            JOIN messages m ON m.id = f.rowid
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
                message_type=row["message_type"] or "",
                snippet=row["snippet"] or "",
                timestamp=row["timestamp"] or "",
            )
            for row in rows
        ]

        return SearchResults(
            results=results,
            total_count=total_count,
            query=query,
            type_counts=type_counts,
        )


def _build_filter_conditions(
    *,
    roles: list[str] | None,
    project_id: str,
    project_ids: list[str] | None,
    providers: list[str] | None,
    project_query: str,
    include_roles: bool,
) -> tuple[list[str], list[str | int]]:
    """Build SQL filters and bind params for shared search queries."""
    conditions: list[str] = []
    params: list[str | int] = []

    if include_roles and roles:
        normalized_roles = normalize_category_keys(roles)
        if normalized_roles:
            placeholders = ",".join("?" for _ in normalized_roles)
            conditions.append(f"m.type IN ({placeholders})")
            params.extend(normalized_roles)

    if project_ids:
        normalized_ids = [pid for pid in project_ids if pid]
        if normalized_ids:
            placeholders = ",".join("?" for _ in normalized_ids)
            conditions.append(f"s.project_id IN ({placeholders})")
            params.extend(normalized_ids)
    elif project_id:
        conditions.append("s.project_id = ?")
        params.append(project_id)

    if providers:
        normalized_providers = sorted(
            {
                provider.strip().lower()
                for provider in providers
                if provider.strip().lower() in {"claude", "codex", "gemini"}
            }
        )
        if normalized_providers:
            placeholders = ",".join("?" for _ in normalized_providers)
            conditions.append(f"COALESCE(s.provider, 'claude') IN ({placeholders})")
            params.extend(normalized_providers)

    project_filter = project_query.strip().lower()
    if project_filter:
        like_pattern = f"%{project_filter}%"
        conditions.append("(LOWER(p.project_name) LIKE ? OR LOWER(p.project_path) LIKE ?)")
        params.extend([like_pattern, like_pattern])

    return conditions, params


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
