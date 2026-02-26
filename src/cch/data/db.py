"""Async SQLite connection manager using aiosqlite."""

from __future__ import annotations

import logging
from pathlib import Path
from types import TracebackType
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 4

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL DEFAULT 'claude',
    project_path TEXT NOT NULL,
    project_name TEXT NOT NULL,
    session_count INTEGER DEFAULT 0,
    first_activity TEXT,
    last_activity TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    provider TEXT NOT NULL DEFAULT 'claude',
    file_path TEXT NOT NULL UNIQUE,
    first_prompt TEXT,
    summary TEXT,
    message_count INTEGER DEFAULT 0,
    user_message_count INTEGER DEFAULT 0,
    assistant_message_count INTEGER DEFAULT 0,
    tool_call_count INTEGER DEFAULT 0,
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    total_cache_read_tokens INTEGER DEFAULT 0,
    total_cache_creation_tokens INTEGER DEFAULT 0,
    model TEXT,
    models_used TEXT,
    git_branch TEXT,
    cwd TEXT,
    created_at TEXT NOT NULL,
    modified_at TEXT NOT NULL,
    duration_ms INTEGER,
    is_sidechain INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    uuid TEXT NOT NULL,
    parent_uuid TEXT,
    type TEXT NOT NULL CHECK (
        type IN ('user', 'assistant', 'tool_use', 'tool_result', 'thinking', 'system')
    ),
    model TEXT,
    content_text TEXT,
    content_json TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cache_read_tokens INTEGER DEFAULT 0,
    cache_creation_tokens INTEGER DEFAULT 0,
    timestamp TEXT NOT NULL,
    is_sidechain INTEGER DEFAULT 0,
    sequence_num INTEGER NOT NULL,
    UNIQUE(session_id, uuid)
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_use_id TEXT NOT NULL,
    message_uuid TEXT NOT NULL,
    session_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    input_json TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY(session_id, message_uuid) REFERENCES messages(session_id, uuid) ON DELETE CASCADE,
    UNIQUE(session_id, tool_use_id)
);

CREATE TABLE IF NOT EXISTS indexed_files (
    file_path TEXT PRIMARY KEY,
    file_mtime_ms INTEGER NOT NULL,
    file_size INTEGER NOT NULL,
    indexed_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content_text,
    content='messages',
    content_rowid='id',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content_text) VALUES (new.id, new.content_text);
END;

CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content_text)
        VALUES('delete', old.id, old.content_text);
END;

CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content_text)
        VALUES('delete', old.id, old.content_text);
    INSERT INTO messages_fts(rowid, content_text)
        VALUES (new.id, new.content_text);
END;

CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_projects_provider ON projects(provider);
CREATE INDEX IF NOT EXISTS idx_sessions_provider ON sessions(provider);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_modified ON sessions(modified_at);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_session_seq ON messages(session_id, sequence_num);
CREATE INDEX IF NOT EXISTS idx_messages_type ON messages(type);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls(session_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_name ON tool_calls(tool_name);
"""


class Database:
    """Async SQLite connection manager using aiosqlite."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None
        self.requires_full_reindex = False

    async def __aenter__(self) -> Database:
        await self.connect()
        return self

    async def connect(self) -> Database:
        """Connect to SQLite and ensure schema."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self._db_path))
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._ensure_schema()
        await self._conn.commit()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the SQLite connection."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            msg = "Database not connected. Use 'async with Database(path) as db:'"
            raise RuntimeError(msg)
        return self._conn

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> aiosqlite.Cursor:
        """Execute a SQL statement."""
        return await self.conn.execute(sql, params)

    async def execute_many(self, sql: str, params_seq: list[tuple[Any, ...]]) -> None:
        """Execute a SQL statement with many parameter sets."""
        await self.conn.executemany(sql, params_seq)

    async def fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[aiosqlite.Row]:
        """Fetch all rows from a query."""
        cursor = await self.conn.execute(sql, params)
        return await cursor.fetchall()  # type: ignore[return-value]

    async def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> aiosqlite.Row | None:
        """Fetch a single row from a query."""
        cursor = await self.conn.execute(sql, params)
        return await cursor.fetchone()  # type: ignore[return-value]

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self.conn.commit()

    async def _ensure_schema(self) -> None:
        """Rebuild schema when version changes; otherwise ensure all objects exist."""
        self.requires_full_reindex = False
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        row = await self.fetch_one("SELECT value FROM app_meta WHERE key = 'schema_version'")
        current_version = int(row["value"]) if row and str(row["value"]).isdigit() else 0
        if current_version == SCHEMA_VERSION:
            await self.conn.executescript(SCHEMA_SQL)
            return

        self.requires_full_reindex = True
        logger.info("Rebuilding DB schema from version %s to %s", current_version, SCHEMA_VERSION)
        await self.conn.execute("PRAGMA foreign_keys=OFF")
        await self.conn.executescript("""
            DROP TRIGGER IF EXISTS messages_ai;
            DROP TRIGGER IF EXISTS messages_ad;
            DROP TRIGGER IF EXISTS messages_au;
            DROP TABLE IF EXISTS messages_fts;
            DROP TABLE IF EXISTS tool_calls;
            DROP TABLE IF EXISTS messages;
            DROP TABLE IF EXISTS sessions;
            DROP TABLE IF EXISTS projects;
            DROP TABLE IF EXISTS indexed_files;
        """)
        await self.conn.execute("PRAGMA foreign_keys=ON")
        await self.conn.executescript(SCHEMA_SQL)
        await self.conn.execute(
            "INSERT OR REPLACE INTO app_meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
