"""Incremental async indexer for session data into SQLite."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from cch.data.discovery import DiscoveredSession, discover_projects, discover_sessions
from cch.data.parser import parse_session_file
from cch.data.protocols import IndexResult

if TYPE_CHECKING:
    from collections.abc import Callable

    from cch.config import Config
    from cch.data.db import Database

logger = logging.getLogger(__name__)

type ProgressCallback = Callable[[int, int, str], None]


class Indexer:
    """Incremental async indexer for session data."""

    def __init__(self, db: Database, config: Config) -> None:
        self._db = db
        self._config = config

    async def index_all(
        self,
        progress_callback: ProgressCallback | None = None,
        force: bool = False,
    ) -> IndexResult:
        """Index all discovered sessions into the database.

        Args:
            progress_callback: Optional callback for progress updates.
            force: If True, re-index all files regardless of mtime/size.

        Returns:
            IndexResult with counts of indexed/skipped/failed files.
        """
        result = IndexResult()

        # Index projects first
        projects = discover_projects(self._config)
        for project in projects:
            await self._upsert_project(
                project.project_id, project.project_path, project.project_name
            )

        # Discover and index sessions
        sessions = discover_sessions(self._config)
        total = len(sessions)

        for i, session in enumerate(sessions):
            if not force and not await self._needs_reindex(session):
                result.files_skipped += 1
                continue

            if progress_callback:
                progress_callback(i, total, f"Indexing {session.session_id[:8]}...")

            try:
                msg_count = await self._index_session(session)
                result.files_indexed += 1
                result.total_messages += msg_count
            except Exception:
                logger.exception("Failed to index %s", session.file_path)
                result.files_failed += 1

        # Update project session counts
        await self._update_project_stats()

        if progress_callback:
            progress_callback(total, total, "Indexing complete")

        return result

    async def _needs_reindex(self, session: DiscoveredSession) -> bool:
        """Check if a session file needs re-indexing."""
        row = await self._db.fetch_one(
            "SELECT file_mtime_ms, file_size FROM indexed_files WHERE file_path = ?",
            (str(session.file_path),),
        )
        if row is None:
            return True
        return row["file_mtime_ms"] != session.mtime_ms or row["file_size"] != session.file_size

    async def _index_session(self, session: DiscoveredSession) -> int:
        """Parse and index a single session file. Returns message count."""
        # Delete old data for this session
        await self._db.execute(
            "DELETE FROM tool_calls WHERE session_id = ?", (session.session_id,)
        )
        await self._db.execute("DELETE FROM messages WHERE session_id = ?", (session.session_id,))
        await self._db.execute("DELETE FROM sessions WHERE session_id = ?", (session.session_id,))

        messages = list(parse_session_file(session.file_path))

        user_count = sum(1 for m in messages if m.role == "user" and m.type == "user")
        assistant_count = sum(1 for m in messages if m.role == "assistant")
        tool_call_count = 0
        total_input = 0
        total_output = 0
        total_cache_read = 0
        total_cache_creation = 0
        models_used: set[str] = set()
        primary_model = ""
        first_timestamp = ""
        last_timestamp = ""
        first_prompt = session.first_prompt
        summary = session.summary

        for msg in messages:
            total_input += msg.usage.input_tokens
            total_output += msg.usage.output_tokens
            total_cache_read += msg.usage.cache_read_tokens
            total_cache_creation += msg.usage.cache_creation_tokens

            if msg.model:
                models_used.add(msg.model)
                if not primary_model:
                    primary_model = msg.model

            if msg.timestamp:
                if not first_timestamp:
                    first_timestamp = msg.timestamp
                last_timestamp = msg.timestamp

            # Count tool calls and extract them
            for block in msg.content_blocks:
                if block.type == "tool_use" and block.tool_use:
                    tool_call_count += 1

            # Get first user prompt if not from index
            if not first_prompt and msg.type == "user" and msg.role == "user" and msg.content_text:
                first_prompt = msg.content_text[:500]

        # Calculate duration
        duration_ms = 0
        if first_timestamp and last_timestamp:
            try:
                first_dt = datetime.fromisoformat(first_timestamp.replace("Z", "+00:00"))
                last_dt = datetime.fromisoformat(last_timestamp.replace("Z", "+00:00"))
                duration_ms = int((last_dt - first_dt).total_seconds() * 1000)
            except ValueError:
                pass

        created_at = session.created or first_timestamp or ""
        modified_at = session.modified or last_timestamp or ""

        # Insert session
        await self._db.execute(
            """INSERT OR REPLACE INTO sessions
            (session_id, project_id, file_path, first_prompt, summary,
             message_count, user_message_count, assistant_message_count, tool_call_count,
             total_input_tokens, total_output_tokens,
             total_cache_read_tokens, total_cache_creation_tokens,
             model, models_used, git_branch, cwd,
             created_at, modified_at, duration_ms, is_sidechain)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session.session_id,
                session.project_id,
                str(session.file_path),
                first_prompt,
                summary,
                len(messages),
                user_count,
                assistant_count,
                tool_call_count,
                total_input,
                total_output,
                total_cache_read,
                total_cache_creation,
                primary_model,
                ",".join(sorted(models_used)),
                session.git_branch,
                "",
                created_at,
                modified_at,
                duration_ms,
                1 if session.is_sidechain else 0,
            ),
        )

        # Insert messages and tool calls
        for msg in messages:
            content_json = json.dumps(
                [b.model_dump() for b in msg.content_blocks],
                default=str,
            )
            await self._db.execute(
                """INSERT OR REPLACE INTO messages
                (uuid, session_id, parent_uuid, type, role, model,
                 content_text, content_json,
                 input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens,
                 timestamp, is_sidechain, sequence_num)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    msg.uuid,
                    session.session_id,
                    msg.parent_uuid,
                    msg.type,
                    msg.role,
                    msg.model,
                    msg.content_text,
                    content_json,
                    msg.usage.input_tokens,
                    msg.usage.output_tokens,
                    msg.usage.cache_read_tokens,
                    msg.usage.cache_creation_tokens,
                    msg.timestamp,
                    1 if msg.is_sidechain else 0,
                    msg.sequence_num,
                ),
            )

            # Extract and insert tool calls
            for block in msg.content_blocks:
                if block.type == "tool_use" and block.tool_use:
                    await self._db.execute(
                        """INSERT OR REPLACE INTO tool_calls
                        (tool_use_id, message_uuid, session_id, tool_name, input_json, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            block.tool_use.tool_use_id,
                            msg.uuid,
                            session.session_id,
                            block.tool_use.name,
                            block.tool_use.input_json,
                            msg.timestamp,
                        ),
                    )

        # Record indexed file
        now = datetime.now(UTC).isoformat()
        await self._db.execute(
            """INSERT OR REPLACE INTO indexed_files
            (file_path, file_mtime_ms, file_size, indexed_at)
            VALUES (?, ?, ?, ?)""",
            (str(session.file_path), session.mtime_ms, session.file_size, now),
        )

        await self._db.commit()
        return len(messages)

    async def _upsert_project(self, project_id: str, project_path: str, project_name: str) -> None:
        """Insert or update a project."""
        await self._db.execute(
            """INSERT OR REPLACE INTO projects (project_id, project_path, project_name)
            VALUES (?, ?, ?)""",
            (project_id, project_path, project_name),
        )
        await self._db.commit()

    async def _update_project_stats(self) -> None:
        """Update project session counts and activity dates."""
        await self._db.execute("""
            UPDATE projects SET
                session_count = (
                    SELECT COUNT(*) FROM sessions WHERE sessions.project_id = projects.project_id
                ),
                first_activity = (
                    SELECT MIN(created_at) FROM sessions
                    WHERE sessions.project_id = projects.project_id
                ),
                last_activity = (
                    SELECT MAX(modified_at) FROM sessions
                    WHERE sessions.project_id = projects.project_id
                )
        """)
        await self._db.commit()
