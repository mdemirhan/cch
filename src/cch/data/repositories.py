"""Repository layer for SQL persistence and query access."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aiosqlite import Row

    from cch.data.db import Database


class SessionRepository:
    """SQL query repository for session and message data."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def list_sessions_rows(
        self,
        *,
        project_id: str,
        model: str,
        limit: int,
        offset: int,
        sort_by: str,
        sort_order: str,
    ) -> tuple[list[Row], int]:
        allowed_sorts = {
            "created_at",
            "modified_at",
            "message_count",
            "tool_call_count",
            "total_output_tokens",
        }
        normalized_sort = sort_by if sort_by in allowed_sorts else "modified_at"
        normalized_order = sort_order if sort_order in {"asc", "desc"} else "desc"

        conditions: list[str] = []
        params: list[str | int] = []

        if project_id:
            conditions.append("s.project_id = ?")
            params.append(project_id)
        if model:
            conditions.append("(s.model = ? OR s.models_used LIKE ?)")
            params.extend([model, f"%{model}%"])

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        count_row = await self._db.fetch_one(
            f"SELECT COUNT(*) as cnt FROM sessions s {where}",
            tuple(params),
        )
        total = int(count_row["cnt"]) if count_row else 0
        params_page: list[str | int] = [*params, limit, offset]
        rows = await self._db.fetch_all(
            f"""SELECT s.*, p.project_name, COALESCE(s.provider, p.provider, 'claude') as provider
                FROM sessions s
                LEFT JOIN projects p ON p.project_id = s.project_id
                {where}
                ORDER BY s.{normalized_sort} {normalized_order}
                LIMIT ? OFFSET ?""",
            tuple(params_page),
        )
        return rows, total

    async def get_session_row(self, session_id: str) -> Row | None:
        return await self._db.fetch_one(
            """SELECT s.*, p.project_name, COALESCE(s.provider, p.provider, 'claude') as provider
               FROM sessions s
               LEFT JOIN projects p ON p.project_id = s.project_id
               WHERE s.session_id = ?""",
            (session_id,),
        )

    async def get_message_rows(
        self,
        session_id: str,
        *,
        limit: int | None,
        offset: int,
    ) -> list[Row]:
        if limit is None:
            return await self._db.fetch_all(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY sequence_num",
                (session_id,),
            )
        return await self._db.fetch_all(
            """SELECT * FROM messages
               WHERE session_id = ?
               ORDER BY sequence_num
               LIMIT ? OFFSET ?""",
            (session_id, limit, offset),
        )

    async def get_tool_call_rows(self, session_id: str, message_uuids: list[str]) -> list[Row]:
        if not message_uuids:
            return []
        placeholders = ",".join("?" for _ in message_uuids)
        return await self._db.fetch_all(
            f"""SELECT * FROM tool_calls
                WHERE session_id = ? AND message_uuid IN ({placeholders})
                ORDER BY timestamp""",
            (session_id, *message_uuids),
        )

    async def get_message_offset(self, session_id: str, message_uuid: str) -> int | None:
        row = await self._db.fetch_one(
            """SELECT sequence_num
               FROM messages
               WHERE session_id = ? AND uuid = ?
               ORDER BY sequence_num
               LIMIT 1""",
            (session_id, message_uuid),
        )
        if row is None:
            return None
        return int(row["sequence_num"] or 0)

    async def get_recent_session_rows(self, limit: int) -> list[Row]:
        return await self._db.fetch_all(
            """SELECT s.*, p.project_name, COALESCE(s.provider, p.provider, 'claude') as provider
               FROM sessions s
               LEFT JOIN projects p ON p.project_id = s.project_id
               ORDER BY s.modified_at DESC LIMIT ?""",
            (limit,),
        )

    async def get_stats_row(self) -> Row | None:
        return await self._db.fetch_one("""
            SELECT
                COUNT(*) as total_sessions,
                COALESCE(SUM(message_count), 0) as total_messages,
                COALESCE(SUM(tool_call_count), 0) as total_tool_calls,
                COALESCE(SUM(total_input_tokens), 0) as total_input_tokens,
                COALESCE(SUM(total_output_tokens), 0) as total_output_tokens,
                COALESCE(SUM(total_cache_read_tokens), 0) as total_cache_read_tokens,
                COALESCE(SUM(total_cache_creation_tokens), 0) as total_cache_creation_tokens
            FROM sessions
        """)


class ProjectRepository:
    """SQL query repository for project data."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def list_project_rows(self) -> list[Row]:
        return await self._db.fetch_all("SELECT * FROM projects ORDER BY last_activity DESC")

    async def get_project_row(self, project_id: str) -> Row | None:
        return await self._db.fetch_one(
            "SELECT * FROM projects WHERE project_id = ?",
            (project_id,),
        )


class AnalyticsRepository:
    """SQL query repository for analytics projections."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def get_cost_rows(self, period: str) -> list[Row]:
        match period:
            case "weekly":
                date_expr = "strftime('%Y-W%W', created_at)"
            case "monthly":
                date_expr = "strftime('%Y-%m', created_at)"
            case _:
                date_expr = "DATE(created_at)"
        return await self._db.fetch_all(f"""
            SELECT
                {date_expr} as period_date,
                model,
                SUM(total_input_tokens) as input_tokens,
                SUM(total_output_tokens) as output_tokens,
                SUM(total_cache_read_tokens) as cache_read_tokens,
                SUM(total_cache_creation_tokens) as cache_creation_tokens
            FROM sessions
            WHERE model != ''
            GROUP BY period_date, model
            ORDER BY period_date
        """)

    async def get_tool_usage_rows(self) -> list[Row]:
        return await self._db.fetch_all("""
            SELECT
                tool_name,
                COUNT(*) as call_count,
                COUNT(DISTINCT session_id) as session_count
            FROM tool_calls
            GROUP BY tool_name
            ORDER BY call_count DESC
        """)

    async def get_heatmap_rows(self) -> list[Row]:
        return await self._db.fetch_all("""
            SELECT
                CAST(strftime('%w', timestamp) AS INTEGER) as dow,
                CAST(strftime('%H', timestamp) AS INTEGER) as hour,
                COUNT(*) as count
            FROM messages
            WHERE timestamp != ''
            GROUP BY dow, hour
        """)

    async def get_model_usage_rows(self) -> list[dict[str, Any]]:
        rows = await self._db.fetch_all("""
            SELECT
                model,
                COUNT(*) as session_count,
                SUM(total_output_tokens) as total_output_tokens
            FROM sessions
            WHERE model != ''
            GROUP BY model
            ORDER BY session_count DESC
        """)
        return [dict(row) for row in rows]
