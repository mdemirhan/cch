"""Tests for search functionality."""

from __future__ import annotations

import pytest

from cch.config import Config
from cch.data.db import Database
from cch.data.indexer import Indexer
from cch.data.search import SearchEngine


class TestSearchEngine:
    @pytest.fixture
    async def indexed_db(self, test_db: Database, test_config: Config) -> Database:
        """Database with indexed test data."""
        indexer = Indexer(test_db, test_config)
        await indexer.index_all()
        return test_db

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
