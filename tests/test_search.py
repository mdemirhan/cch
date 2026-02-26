"""Tests for search functionality."""

from __future__ import annotations

import pytest

from cch.config import Config
from cch.data.db import Database
from cch.data.indexer import Indexer
from cch.data.search import SearchEngine
from cch.models.categories import ALL_CATEGORY_KEYS


class TestSearchEngine:
    @pytest.fixture
    async def indexed_db(self, in_memory_db: Database, test_config: Config) -> Database:
        """Database with indexed test data."""
        indexer = Indexer(in_memory_db, test_config)
        await indexer.index_all()
        return in_memory_db

    @pytest.mark.asyncio
    async def test_basic_search(self, indexed_db: Database) -> None:
        engine = SearchEngine(indexed_db)
        results = await engine.search("bug")
        assert results.total_count >= 1
        assert len(results.results) >= 1

    @pytest.mark.asyncio
    async def test_search_with_role_filter(self, indexed_db: Database) -> None:
        engine = SearchEngine(indexed_db)

        user_results = await engine.search("bug", roles=["user"])
        assert user_results.total_count >= 1

        thinking_results = await engine.search("think", roles=["thinking"])
        assert thinking_results.total_count >= 1

        system_results = await engine.search("Fixed", roles=["system"])
        assert system_results.total_count >= 1

    @pytest.mark.asyncio
    async def test_empty_query(self, indexed_db: Database) -> None:
        engine = SearchEngine(indexed_db)
        results = await engine.search("")
        assert results.total_count == 0

    @pytest.mark.asyncio
    async def test_no_results(self, indexed_db: Database) -> None:
        engine = SearchEngine(indexed_db)
        results = await engine.search("xyznonexistent123")
        assert results.total_count == 0

    @pytest.mark.asyncio
    async def test_search_snippet(self, indexed_db: Database) -> None:
        engine = SearchEngine(indexed_db)
        results = await engine.search("Python")
        if results.results:
            assert results.results[0].snippet != ""

    @pytest.mark.asyncio
    async def test_query_with_quote_char(self, indexed_db: Database) -> None:
        engine = SearchEngine(indexed_db)
        results = await engine.search('bug"')
        assert results.total_count >= 0

    @pytest.mark.asyncio
    async def test_search_with_provider_filter(self, indexed_db: Database) -> None:
        engine = SearchEngine(indexed_db)
        claude_results = await engine.search("bug", providers=["claude"])
        codex_results = await engine.search("bug", providers=["codex"])
        assert claude_results.total_count >= 1
        assert codex_results.total_count == 0

    @pytest.mark.asyncio
    async def test_search_with_project_query_filter(self, indexed_db: Database) -> None:
        engine = SearchEngine(indexed_db)
        matching = await engine.search("bug", project_query="project")
        non_matching = await engine.search("bug", project_query="definitely-missing-project")
        assert matching.total_count >= 1
        assert non_matching.total_count == 0

    @pytest.mark.asyncio
    async def test_search_returns_type_counts(self, indexed_db: Database) -> None:
        engine = SearchEngine(indexed_db)
        results = await engine.search("bug")
        assert all(key in results.type_counts for key in ALL_CATEGORY_KEYS)
        assert sum(results.type_counts.values()) == results.total_count

    @pytest.mark.asyncio
    async def test_search_role_filter_does_not_hide_type_count_facets(
        self, indexed_db: Database
    ) -> None:
        engine = SearchEngine(indexed_db)
        all_results = await engine.search("bug")
        filtered = await engine.search("bug", roles=["user"])
        assert filtered.total_count <= all_results.total_count
        assert filtered.type_counts == all_results.type_counts
