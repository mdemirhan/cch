"""Tests for services."""

from __future__ import annotations

import pytest
from result import Err, Ok

from cch.config import Config
from cch.data.db import Database
from cch.data.indexer import Indexer
from cch.data.search import SearchEngine
from cch.services.analytics_service import AnalyticsService
from cch.services.cost import estimate_cost
from cch.services.project_service import ProjectService
from cch.services.search_service import SearchService
from cch.services.session_service import SessionService


@pytest.fixture
async def indexed_db(test_db: Database, test_config: Config) -> Database:
    """Database with indexed test data."""
    indexer = Indexer(test_db, test_config)
    await indexer.index_all()
    return test_db


class TestSessionService:
    @pytest.mark.asyncio
    async def test_list_sessions(self, indexed_db: Database) -> None:
        svc = SessionService(indexed_db)
        result = await svc.list_sessions()
        assert isinstance(result, Ok)
        sessions, total = result.ok_value
        assert total >= 1
        assert len(sessions) >= 1
        assert sessions[0].session_id == "test-session-001"

    @pytest.mark.asyncio
    async def test_get_session_detail(self, indexed_db: Database) -> None:
        svc = SessionService(indexed_db)
        result = await svc.get_session_detail("test-session-001")
        assert isinstance(result, Ok)
        detail = result.ok_value
        assert detail.session_id == "test-session-001"
        assert len(detail.messages) >= 5

    @pytest.mark.asyncio
    async def test_get_session_detail_paged(self, indexed_db: Database) -> None:
        svc = SessionService(indexed_db)
        result = await svc.get_session_detail("test-session-001", limit=2, offset=1)
        assert isinstance(result, Ok)
        detail = result.ok_value
        assert detail.message_count >= 5
        assert len(detail.messages) == 2

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, indexed_db: Database) -> None:
        svc = SessionService(indexed_db)
        result = await svc.get_session_detail("nonexistent")
        assert isinstance(result, Err)

    @pytest.mark.asyncio
    async def test_get_stats(self, indexed_db: Database) -> None:
        svc = SessionService(indexed_db)
        result = await svc.get_stats()
        assert isinstance(result, Ok)
        stats = result.ok_value
        assert stats["total_sessions"] >= 1

    @pytest.mark.asyncio
    async def test_get_recent(self, indexed_db: Database) -> None:
        svc = SessionService(indexed_db)
        result = await svc.get_recent_sessions(limit=5)
        assert isinstance(result, Ok)
        assert len(result.ok_value) >= 1


class TestProjectService:
    @pytest.mark.asyncio
    async def test_list_projects(self, indexed_db: Database) -> None:
        svc = ProjectService(indexed_db)
        result = await svc.list_projects()
        assert isinstance(result, Ok)
        assert len(result.ok_value) >= 1

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, indexed_db: Database) -> None:
        svc = ProjectService(indexed_db)
        result = await svc.get_project("nonexistent")
        assert isinstance(result, Err)


class TestAnalyticsService:
    @pytest.mark.asyncio
    async def test_get_tool_usage(self, indexed_db: Database) -> None:
        svc = AnalyticsService(indexed_db)
        result = await svc.get_tool_usage()
        assert isinstance(result, Ok)
        tools = result.ok_value
        assert len(tools) >= 1
        assert tools[0].tool_name == "Edit"

    @pytest.mark.asyncio
    async def test_get_heatmap(self, indexed_db: Database) -> None:
        svc = AnalyticsService(indexed_db)
        result = await svc.get_heatmap_data()
        assert isinstance(result, Ok)
        heatmap = result.ok_value
        assert len(heatmap.values) == 7
        assert len(heatmap.values[0]) == 24


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


class TestCostEstimation:
    def test_opus_cost(self) -> None:
        cost = estimate_cost(
            model="claude-opus-4-6",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        assert cost["input_cost"] == 15.0
        assert cost["output_cost"] == 75.0
        assert cost["total_cost"] == 90.0

    def test_unknown_model(self) -> None:
        cost = estimate_cost(
            model="unknown-model",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        # Should use default (Sonnet-level) pricing
        assert cost["input_cost"] == 3.0
        assert cost["output_cost"] == 15.0

    def test_zero_tokens(self) -> None:
        cost = estimate_cost(model="claude-opus-4-6")
        assert cost["total_cost"] == 0.0
