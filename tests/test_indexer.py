"""Tests for indexer."""

from __future__ import annotations

import shutil

import pytest

from cch.config import Config
from cch.data.db import Database
from cch.data.indexer import Indexer


class TestIndexer:
    @pytest.mark.asyncio
    async def test_index_all(self, test_db: Database, test_config: Config) -> None:
        indexer = Indexer(test_db, test_config)
        result = await indexer.index_all()

        assert result.files_indexed >= 1
        assert result.total_messages >= 5

    @pytest.mark.asyncio
    async def test_incremental_skip(self, test_db: Database, test_config: Config) -> None:
        indexer = Indexer(test_db, test_config)

        # First index
        result1 = await indexer.index_all()
        assert result1.files_indexed >= 1

        # Second index should skip everything
        result2 = await indexer.index_all()
        assert result2.files_skipped >= 1
        assert result2.files_indexed == 0

    @pytest.mark.asyncio
    async def test_force_reindex(self, test_db: Database, test_config: Config) -> None:
        indexer = Indexer(test_db, test_config)

        # First index
        await indexer.index_all()

        # Force re-index
        result = await indexer.index_all(force=True)
        assert result.files_indexed >= 1

    @pytest.mark.asyncio
    async def test_creates_sessions(self, test_db: Database, test_config: Config) -> None:
        indexer = Indexer(test_db, test_config)
        await indexer.index_all()

        row = await test_db.fetch_one("SELECT COUNT(*) as cnt FROM sessions")
        assert row is not None
        assert row["cnt"] >= 1

    @pytest.mark.asyncio
    async def test_creates_messages(self, test_db: Database, test_config: Config) -> None:
        indexer = Indexer(test_db, test_config)
        await indexer.index_all()

        row = await test_db.fetch_one("SELECT COUNT(*) as cnt FROM messages")
        assert row is not None
        assert row["cnt"] >= 5

    @pytest.mark.asyncio
    async def test_creates_tool_calls(self, test_db: Database, test_config: Config) -> None:
        indexer = Indexer(test_db, test_config)
        await indexer.index_all()

        row = await test_db.fetch_one("SELECT COUNT(*) as cnt FROM tool_calls")
        assert row is not None
        assert row["cnt"] >= 1

    @pytest.mark.asyncio
    async def test_creates_projects(self, test_db: Database, test_config: Config) -> None:
        indexer = Indexer(test_db, test_config)
        await indexer.index_all()

        row = await test_db.fetch_one("SELECT COUNT(*) as cnt FROM projects")
        assert row is not None
        assert row["cnt"] >= 1

    @pytest.mark.asyncio
    async def test_progress_callback(self, test_db: Database, test_config: Config) -> None:
        indexer = Indexer(test_db, test_config)
        progress_calls: list[tuple[int, int, str]] = []

        def on_progress(current: int, total: int, message: str) -> None:
            progress_calls.append((current, total, message))

        await indexer.index_all(progress_callback=on_progress)
        assert len(progress_calls) >= 1

    @pytest.mark.asyncio
    async def test_duplicate_message_uuid_across_sessions_is_preserved(
        self,
        test_db: Database,
        test_config: Config,
    ) -> None:
        """Same UUID in different sessions should not overwrite previous rows."""
        src = test_config.projects_dir / "-tmp-test-project" / "test-session-001.jsonl"
        extra_project = test_config.projects_dir / "-tmp-test-project-copy"
        extra_project.mkdir(parents=True, exist_ok=True)
        dst = extra_project / "test-session-002.jsonl"
        shutil.copy(src, dst)

        indexer = Indexer(test_db, test_config)
        await indexer.index_all(force=True)

        session_row = await test_db.fetch_one("SELECT COUNT(*) as cnt FROM sessions")
        message_row = await test_db.fetch_one("SELECT COUNT(*) as cnt FROM messages")
        assert session_row is not None and session_row["cnt"] >= 2
        assert message_row is not None and message_row["cnt"] >= 10
