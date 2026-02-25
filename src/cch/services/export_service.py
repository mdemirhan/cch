"""Export service — Markdown/JSON/CSV export."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from result import Err, Ok, Result

if TYPE_CHECKING:
    from cch.services.session_service import SessionService


class ExportService:
    """Service for exporting session data."""

    def __init__(self, session_service: SessionService) -> None:
        self._sessions = session_service

    async def export_session_markdown(self, session_id: str) -> Result[str, str]:
        """Export a session as Markdown."""
        detail_result = await self._sessions.get_session_detail(session_id)
        if isinstance(detail_result, Err):
            return detail_result

        detail = detail_result.ok_value
        lines: list[str] = []
        lines.append(f"# Session: {detail.session_id}")
        lines.append("")
        if detail.summary:
            lines.append(f"**Summary:** {detail.summary}")
        lines.append(f"**Project:** {detail.project_name}")
        lines.append(f"**Model:** {detail.model}")
        lines.append(f"**Created:** {detail.created_at}")
        lines.append(f"**Messages:** {detail.message_count}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for msg in detail.messages:
            if msg.role == "user" and msg.type == "user":
                # Only show user messages that have text content (not tool results)
                if msg.content_text:
                    lines.append("## User")
                    lines.append("")
                    lines.append(msg.content_text)
                    lines.append("")
            elif msg.role == "assistant":
                if msg.content_text:
                    lines.append(f"## Assistant ({msg.model})")
                    lines.append("")
                    lines.append(msg.content_text)
                    lines.append("")
                for tc in msg.tool_calls:
                    lines.append(f"### Tool: {tc.tool_name}")
                    lines.append("")
                    lines.append(f"```json\n{tc.input_json}\n```")
                    lines.append("")

        return Ok("\n".join(lines))

    async def export_session_json(self, session_id: str) -> Result[str, str]:
        """Export a session as JSON."""
        detail_result = await self._sessions.get_session_detail(session_id)
        if isinstance(detail_result, Err):
            return detail_result

        detail = detail_result.ok_value
        return Ok(json.dumps(detail.model_dump(), indent=2, default=str))

    async def export_session_csv(self, session_id: str) -> Result[str, str]:
        """Export session messages as CSV."""
        detail_result = await self._sessions.get_session_detail(session_id)
        if isinstance(detail_result, Err):
            return detail_result

        detail = detail_result.ok_value
        lines = ["uuid,role,type,model,timestamp,input_tokens,output_tokens,content_preview"]
        for msg in detail.messages:
            preview = msg.content_text[:100].replace('"', '""').replace("\n", " ")
            lines.append(
                f'"{msg.uuid}","{msg.role}","{msg.type}","{msg.model}",'
                f'"{msg.timestamp}",{msg.input_tokens},{msg.output_tokens},"{preview}"'
            )
        return Ok("\n".join(lines))
