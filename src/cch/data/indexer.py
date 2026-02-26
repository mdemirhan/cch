"""Incremental async indexer for session data into SQLite."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from cch.data.discovery import DiscoveredSession, discover_sessions
from cch.data.parser import parse_session_file
from cch.models.categories import category_mask_for_message
from cch.models.indexing import IndexResult

if TYPE_CHECKING:
    from collections.abc import Callable

    from cch.config import Config
    from cch.data.db import Database

logger = logging.getLogger(__name__)

type ProgressCallback = Callable[[int, int, str], None]
_BATCH_SIZE = 300


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

        # Discover and index sessions
        sessions = discover_sessions(self._config)
        for project_id, provider, project_path, project_name in _projects_from_sessions(sessions):
            await self._upsert_project(project_id, provider, project_path, project_name)

        total = len(sessions)
        indexed_files = await self._load_indexed_files() if not force else {}

        for i, session in enumerate(sessions):
            if not force and not self._needs_reindex_cached(session, indexed_files):
                result.files_skipped += 1
                continue

            if progress_callback:
                progress_callback(i, total, f"Indexing {session.session_id[:8]}...")

            try:
                msg_count = await self._index_session(session, savepoint_id=i)
                result.files_indexed += 1
                result.total_messages += msg_count
                indexed_files[str(session.file_path)] = (session.mtime_ms, session.file_size)
            except Exception:
                logger.exception("Failed to index %s", session.file_path)
                result.files_failed += 1

        # Update project session counts
        await self._update_project_stats()
        await self._db.commit()

        if progress_callback:
            progress_callback(total, total, "Indexing complete")

        return result

    async def needs_reindex(self, file_path: str, mtime_ms: int, size: int) -> bool:
        """Check if a session file needs re-indexing."""
        row = await self._db.fetch_one(
            "SELECT file_mtime_ms, file_size FROM indexed_files WHERE file_path = ?",
            (file_path,),
        )
        if row is None:
            return True
        return row["file_mtime_ms"] != mtime_ms or row["file_size"] != size

    async def _load_indexed_files(self) -> dict[str, tuple[int, int]]:
        """Load indexed file metadata once for fast incremental checks."""
        rows = await self._db.fetch_all(
            "SELECT file_path, file_mtime_ms, file_size FROM indexed_files"
        )
        return {
            row["file_path"]: (int(row["file_mtime_ms"]), int(row["file_size"]))
            for row in rows
        }

    @staticmethod
    def _needs_reindex_cached(
        session: DiscoveredSession,
        indexed_files: dict[str, tuple[int, int]],
    ) -> bool:
        """Check if a session needs reindexing using cached indexed-file metadata."""
        current = indexed_files.get(str(session.file_path))
        if current is None:
            return True
        return current != (session.mtime_ms, session.file_size)

    async def _index_session(self, session: DiscoveredSession, savepoint_id: int) -> int:
        """Parse and index a single session file. Returns message count."""
        savepoint = f"session_{savepoint_id}"
        await self._db.execute(f"SAVEPOINT {savepoint}")
        try:
            # Clean previous rows. CASCADE handles messages/tool_calls.
            existing_for_path = await self._db.fetch_all(
                "SELECT session_id FROM sessions WHERE file_path = ?",
                (str(session.file_path),),
            )
            old_session_ids = {str(row["session_id"]) for row in existing_for_path}
            old_session_ids.add(session.session_id)
            for old_session_id in old_session_ids:
                await self._db.execute(
                    "DELETE FROM sessions WHERE session_id = ?",
                    (old_session_id,),
                )

            message_count = 0
            user_count = 0
            assistant_count = 0
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
            message_rows: list[tuple[object, ...]] = []
            tool_call_rows: list[tuple[object, ...]] = []

            created_at = session.created or ""
            modified_at = session.modified or created_at
            if not created_at:
                created_at = datetime.fromtimestamp(
                    session.mtime_ms / 1000,
                    tz=UTC,
                ).isoformat()
            if not modified_at:
                modified_at = created_at

            # Insert shell session first so child message rows can stream in.
            await self._db.execute(
                """INSERT INTO sessions
                (session_id, project_id, provider, file_path, first_prompt, summary,
                 message_count, user_message_count, assistant_message_count, tool_call_count,
                 total_input_tokens, total_output_tokens,
                 total_cache_read_tokens, total_cache_creation_tokens,
                 model, models_used, git_branch, cwd,
                 created_at, modified_at, duration_ms, is_sidechain)
                VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, '', '', ?, '', ?, ?, 0, ?)""",
                (
                    session.session_id,
                    session.project_id,
                    session.provider,
                    str(session.file_path),
                    first_prompt,
                    summary,
                    session.git_branch,
                    created_at,
                    modified_at,
                    1 if session.is_sidechain else 0,
                ),
            )

            for msg in parse_session_file(
                session.file_path,
                provider=session.provider,
                session_id=session.session_id,
            ):
                message_count += 1

                if msg.type == "user" and msg.role == "user":
                    user_count += 1
                if msg.role == "assistant":
                    assistant_count += 1

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

                if (
                    not first_prompt
                    and msg.type == "user"
                    and msg.role == "user"
                    and msg.content_text
                ):
                    first_prompt = msg.content_text[:500]

                content_json = json.dumps(
                    [b.model_dump() for b in msg.content_blocks],
                    default=str,
                )
                category_mask = category_mask_for_message(
                    msg_type=msg.type,
                    role=msg.role,
                    content_blocks=msg.content_blocks,
                    content_text=msg.content_text,
                    has_tool_calls=False,
                )
                message_rows.append(
                    (
                        session.session_id,
                        msg.uuid,
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
                        category_mask,
                    )
                )

                for block_idx, block in enumerate(msg.content_blocks):
                    if block.type == "tool_use" and block.tool_use:
                        tool_use_id = block.tool_use.tool_use_id or (
                            f"{session.session_id}:{msg.sequence_num}:{block_idx}"
                        )
                        tool_call_count += 1
                        tool_call_rows.append(
                            (
                                session.session_id,
                                msg.uuid,
                                tool_use_id,
                                block.tool_use.name,
                                block.tool_use.input_json,
                                msg.timestamp,
                            )
                        )
                if len(message_rows) >= _BATCH_SIZE:
                    await self._flush_message_rows(message_rows)
                    message_rows.clear()
                if len(tool_call_rows) >= _BATCH_SIZE:
                    if message_rows:
                        await self._flush_message_rows(message_rows)
                        message_rows.clear()
                    await self._flush_tool_call_rows(tool_call_rows)
                    tool_call_rows.clear()

            # Calculate duration
            duration_ms = 0
            if first_timestamp and last_timestamp:
                try:
                    first_dt = datetime.fromisoformat(first_timestamp.replace("Z", "+00:00"))
                    last_dt = datetime.fromisoformat(last_timestamp.replace("Z", "+00:00"))
                    duration_ms = int((last_dt - first_dt).total_seconds() * 1000)
                except ValueError:
                    pass

            created_at = session.created or first_timestamp or created_at
            modified_at = session.modified or last_timestamp or modified_at

            if message_rows:
                await self._flush_message_rows(message_rows)
            if tool_call_rows:
                await self._flush_tool_call_rows(tool_call_rows)

            # Finalize session aggregate counters.
            await self._db.execute(
                """UPDATE sessions
                   SET first_prompt = ?, summary = ?,
                       message_count = ?, user_message_count = ?,
                       assistant_message_count = ?, tool_call_count = ?,
                       total_input_tokens = ?, total_output_tokens = ?,
                       total_cache_read_tokens = ?, total_cache_creation_tokens = ?,
                       model = ?, models_used = ?, git_branch = ?,
                       created_at = ?, modified_at = ?, duration_ms = ?, is_sidechain = ?
                   WHERE session_id = ?""",
                (
                    first_prompt,
                    summary,
                    message_count,
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
                    created_at,
                    modified_at,
                    duration_ms,
                    1 if session.is_sidechain else 0,
                    session.session_id,
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
            await self._db.execute(f"RELEASE {savepoint}")
            return message_count
        except Exception:
            await self._db.execute(f"ROLLBACK TO {savepoint}")
            await self._db.execute(f"RELEASE {savepoint}")
            raise

    async def _flush_message_rows(self, rows: list[tuple[object, ...]]) -> None:
        await self._db.execute_many(
            """INSERT OR REPLACE INTO messages
            (session_id, uuid, parent_uuid, type, role, model,
             content_text, content_json,
             input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens,
             timestamp, is_sidechain, sequence_num, category_mask)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )

    async def _flush_tool_call_rows(self, rows: list[tuple[object, ...]]) -> None:
        await self._db.execute_many(
            """INSERT OR REPLACE INTO tool_calls
            (session_id, message_uuid, tool_use_id, tool_name, input_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)""",
            rows,
        )

    async def _upsert_project(
        self,
        project_id: str,
        provider: str,
        project_path: str,
        project_name: str,
    ) -> None:
        """Insert or update a project."""
        await self._db.execute(
            """INSERT OR REPLACE INTO projects (project_id, provider, project_path, project_name)
            VALUES (?, ?, ?, ?)""",
            (project_id, provider, project_path, project_name),
        )

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


def _projects_from_sessions(
    sessions: list[DiscoveredSession],
) -> list[tuple[str, str, str, str]]:
    """Collect unique projects as tuples for upserts."""
    unique: dict[str, tuple[str, str, str, str]] = {}
    for session in sessions:
        unique[session.project_id] = (
            session.project_id,
            session.provider,
            session.project_path,
            session.project_name,
        )
    return list(unique.values())
