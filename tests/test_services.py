"""Tests for services."""

from __future__ import annotations

import pytest
from result import Err, Ok

from cch.config import Config
from cch.data.db import Database
from cch.data.indexer import Indexer
from cch.data.repositories import ProjectRepository, SessionRepository
from cch.data.search import SearchEngine
from cch.services.project_service import ProjectService
from cch.services.search_service import SearchService
from cch.services.session_service import SessionService


@pytest.fixture
async def indexed_db(in_memory_db: Database, test_config: Config) -> Database:
    """Database with indexed test data."""
    indexer = Indexer(in_memory_db, test_config)
    await indexer.index_all()
    return in_memory_db


class TestSessionService:
    @pytest.mark.asyncio
    async def test_list_sessions(self, indexed_db: Database) -> None:
        svc = SessionService(SessionRepository(indexed_db))
        result = await svc.list_sessions()
        assert isinstance(result, Ok)
        sessions, total = result.ok_value
        assert total >= 1
        assert len(sessions) >= 1
        assert sessions[0].session_id == "test-session-001"

    @pytest.mark.asyncio
    async def test_get_session_detail(self, indexed_db: Database) -> None:
        svc = SessionService(SessionRepository(indexed_db))
        result = await svc.get_session_detail("test-session-001")
        assert isinstance(result, Ok)
        detail = result.ok_value
        assert detail.session_id == "test-session-001"
        assert len(detail.messages) >= 5

    @pytest.mark.asyncio
    async def test_get_session_detail_paged(self, indexed_db: Database) -> None:
        svc = SessionService(SessionRepository(indexed_db))
        result = await svc.get_session_detail("test-session-001", limit=2, offset=1)
        assert isinstance(result, Ok)
        detail = result.ok_value
        assert detail.message_count >= 5
        assert len(detail.messages) == 2

    @pytest.mark.asyncio
    async def test_get_message_offset(self, indexed_db: Database) -> None:
        svc = SessionService(SessionRepository(indexed_db))
        detail_result = await svc.get_session_detail("test-session-001", limit=1, offset=0)
        assert isinstance(detail_result, Ok)
        first_uuid = detail_result.ok_value.messages[0].uuid
        offset = await svc.get_message_offset("test-session-001", first_uuid)
        assert offset == 0

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, indexed_db: Database) -> None:
        svc = SessionService(SessionRepository(indexed_db))
        result = await svc.get_session_detail("nonexistent")
        assert isinstance(result, Err)

    @pytest.mark.asyncio
    async def test_get_recent(self, indexed_db: Database) -> None:
        svc = SessionService(SessionRepository(indexed_db))
        result = await svc.get_recent_sessions(limit=5)
        assert isinstance(result, Ok)
        assert len(result.ok_value) >= 1


class TestProjectService:
    @pytest.mark.asyncio
    async def test_list_projects(self, indexed_db: Database) -> None:
        svc = ProjectService(ProjectRepository(indexed_db))
        result = await svc.list_projects()
        assert isinstance(result, Ok)
        assert len(result.ok_value) >= 1

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, indexed_db: Database) -> None:
        svc = ProjectService(ProjectRepository(indexed_db))
        result = await svc.get_project("nonexistent")
        assert isinstance(result, Err)


class TestSearchService:
    @pytest.mark.asyncio
    async def test_search(self, indexed_db: Database) -> None:
        engine = SearchEngine(indexed_db)
        svc = SearchService(engine)
        result = await svc.search("bug")
        assert isinstance(result, Ok)
        assert result.ok_value.total_count >= 1

    @pytest.mark.asyncio
    async def test_empty_search(self, indexed_db: Database) -> None:
        engine = SearchEngine(indexed_db)
        svc = SearchService(engine)
        result = await svc.search("")
        assert isinstance(result, Err)
