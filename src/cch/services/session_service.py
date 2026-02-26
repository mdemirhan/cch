"""Session service — queries for session data."""

from __future__ import annotations

from result import Err, Ok, Result

from cch.data.repositories import SessionRepository
from cch.models.sessions import MessageView, SessionDetail, SessionSummary, ToolCallView


class SessionService:
    """Service for session queries."""

    def __init__(self, repository: SessionRepository) -> None:
        self._repo = repository

    async def list_sessions(
        self,
        project_id: str = "",
        model: str = "",
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "modified_at",
        sort_order: str = "desc",
    ) -> Result[tuple[list[SessionSummary], int], str]:
        """List sessions with optional filters.

        Returns:
            Ok with (sessions, total_count) or Err with error message.
        """
        rows, total = await self._repo.list_sessions_rows(
            project_id=project_id,
            model=model,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        sessions = [_row_to_summary(row) for row in rows]
        return Ok((sessions, total))

    async def get_session_detail(
        self,
        session_id: str,
        *,
        limit: int | None = 1000,
        offset: int = 0,
    ) -> Result[SessionDetail, str]:
        """Get full session detail with messages.

        Returns:
            Ok with SessionDetail or Err if not found.
        """
        row = await self._repo.get_session_row(session_id)
        if row is None:
            return Err(f"Session {session_id} not found")

        normalized_offset = max(offset, 0)
        normalized_limit: int | None = None
        if limit is not None:
            normalized_limit = max(limit, 1)

        # Fetch only the requested message window (or everything if no limit provided).
        if normalized_limit is None:
            msg_rows = await self._repo.get_message_rows(
                session_id,
                limit=None,
                offset=normalized_offset,
            )
        else:
            msg_rows = await self._repo.get_message_rows(
                session_id,
                limit=normalized_limit,
                offset=normalized_offset,
            )

        # Fetch only tool calls for the visible messages.
        tc_rows = []
        if msg_rows:
            uuids = [str(m["uuid"]) for m in msg_rows]
            tc_rows = await self._repo.get_tool_call_rows(session_id, uuids)
        tc_by_msg: dict[str, list[ToolCallView]] = {}
        for tc in tc_rows:
            msg_uuid = tc["message_uuid"]
            if msg_uuid not in tc_by_msg:
                tc_by_msg[msg_uuid] = []
            tc_by_msg[msg_uuid].append(
                ToolCallView(
                    tool_use_id=tc["tool_use_id"],
                    tool_name=tc["tool_name"],
                    input_json=tc["input_json"] or "{}",
                    timestamp=tc["timestamp"] or "",
                )
            )

        messages = [
            MessageView(
                uuid=m["uuid"],
                model=m["model"] or "",
                type=m["type"] or "",
                content_text=m["content_text"] or "",
                content_json=m["content_json"] or "",
                input_tokens=m["input_tokens"] or 0,
                output_tokens=m["output_tokens"] or 0,
                cache_read_tokens=m["cache_read_tokens"] or 0,
                cache_creation_tokens=m["cache_creation_tokens"] or 0,
                timestamp=m["timestamp"] or "",
                is_sidechain=bool(m["is_sidechain"]),
                sequence_num=m["sequence_num"] or 0,
                tool_calls=tc_by_msg.get(m["uuid"], []),
            )
            for m in msg_rows
        ]

        return Ok(
            SessionDetail(
                session_id=row["session_id"],
                provider=row["provider"] or "claude",
                project_id=row["project_id"] or "",
                project_name=row["project_name"] or "",
                first_prompt=row["first_prompt"] or "",
                summary=row["summary"] or "",
                message_count=row["message_count"] or 0,
                user_message_count=row["user_message_count"] or 0,
                assistant_message_count=row["assistant_message_count"] or 0,
                tool_call_count=row["tool_call_count"] or 0,
                total_input_tokens=row["total_input_tokens"] or 0,
                total_output_tokens=row["total_output_tokens"] or 0,
                total_cache_read_tokens=row["total_cache_read_tokens"] or 0,
                total_cache_creation_tokens=row["total_cache_creation_tokens"] or 0,
                model=row["model"] or "",
                models_used=row["models_used"] or "",
                git_branch=row["git_branch"] or "",
                cwd=row["cwd"] or "",
                created_at=row["created_at"] or "",
                modified_at=row["modified_at"] or "",
                duration_ms=row["duration_ms"] or 0,
                is_sidechain=bool(row["is_sidechain"]),
                messages=messages,
            )
        )

    async def get_message_offset(self, session_id: str, message_uuid: str) -> int | None:
        """Return the 0-based sequence offset for a message within a session."""
        if not message_uuid:
            return None
        return await self._repo.get_message_offset(session_id, message_uuid)

    async def get_recent_sessions(self, limit: int = 10) -> Result[list[SessionSummary], str]:
        """Get most recently modified sessions."""
        rows = await self._repo.get_recent_session_rows(limit)
        return Ok([_row_to_summary(row) for row in rows])

    async def get_stats(self) -> Result[dict[str, int], str]:
        """Get aggregate session statistics."""
        row = await self._repo.get_stats_row()
        if row is None:
            return Ok({})
        return Ok(dict(row))


def _row_to_summary(row: object) -> SessionSummary:
    """Convert a database row to SessionSummary."""
    r: dict[str, object] = dict(row)  # type: ignore[arg-type]

    def _s(key: str) -> str:
        v = r.get(key, "")
        return str(v) if v else ""

    def _i(key: str) -> int:
        v = r.get(key, 0)
        return int(v) if v else 0  # type: ignore[arg-type]

    return SessionSummary(
        session_id=_s("session_id"),
        provider=_s("provider") or "claude",
        file_path=_s("file_path"),
        project_id=_s("project_id"),
        project_name=_s("project_name"),
        first_prompt=_s("first_prompt"),
        summary=_s("summary"),
        message_count=_i("message_count"),
        user_message_count=_i("user_message_count"),
        assistant_message_count=_i("assistant_message_count"),
        tool_call_count=_i("tool_call_count"),
        total_input_tokens=_i("total_input_tokens"),
        total_output_tokens=_i("total_output_tokens"),
        total_cache_read_tokens=_i("total_cache_read_tokens"),
        total_cache_creation_tokens=_i("total_cache_creation_tokens"),
        model=_s("model"),
        models_used=_s("models_used"),
        git_branch=_s("git_branch"),
        cwd=_s("cwd"),
        created_at=_s("created_at"),
        modified_at=_s("modified_at"),
        duration_ms=_i("duration_ms"),
        is_sidechain=bool(r.get("is_sidechain", False)),
    )
