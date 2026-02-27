"""Session service — queries for session data."""

from __future__ import annotations

from result import Err, Ok, Result

from cch.data.repositories import SessionRepository
from cch.models.sessions import MessageView, SessionDetail, SessionSummary, ToolCallView
from cch.services._row_helpers import row_int, row_str


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
        normalized_limit = max(limit, 1) if limit is not None else None

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

        summary = _row_to_summary(row)
        return Ok(SessionDetail(**summary.model_dump(), messages=messages))

    async def get_message_offset(self, session_id: str, message_uuid: str) -> int | None:
        """Return the 0-based sequence offset for a message within a session."""
        if not message_uuid:
            return None
        return await self._repo.get_message_offset(session_id, message_uuid)

    async def get_recent_sessions(self, limit: int = 10) -> Result[list[SessionSummary], str]:
        """Get most recently modified sessions."""
        rows = await self._repo.get_recent_session_rows(limit)
        return Ok([_row_to_summary(row) for row in rows])


def _row_to_summary(row: object) -> SessionSummary:
    """Convert a database row to SessionSummary."""
    r: dict[str, object] = dict(row)  # type: ignore[arg-type]
    return SessionSummary(
        session_id=row_str(r, "session_id"),
        provider=row_str(r, "provider", "claude"),
        file_path=row_str(r, "file_path"),
        project_id=row_str(r, "project_id"),
        project_name=row_str(r, "project_name"),
        first_prompt=row_str(r, "first_prompt"),
        summary=row_str(r, "summary"),
        message_count=row_int(r, "message_count"),
        user_message_count=row_int(r, "user_message_count"),
        assistant_message_count=row_int(r, "assistant_message_count"),
        tool_call_count=row_int(r, "tool_call_count"),
        total_input_tokens=row_int(r, "total_input_tokens"),
        total_output_tokens=row_int(r, "total_output_tokens"),
        total_cache_read_tokens=row_int(r, "total_cache_read_tokens"),
        total_cache_creation_tokens=row_int(r, "total_cache_creation_tokens"),
        model=row_str(r, "model"),
        models_used=row_str(r, "models_used"),
        git_branch=row_str(r, "git_branch"),
        cwd=row_str(r, "cwd"),
        created_at=row_str(r, "created_at"),
        modified_at=row_str(r, "modified_at"),
        duration_ms=row_int(r, "duration_ms"),
        is_sidechain=bool(r.get("is_sidechain", False)),
    )
