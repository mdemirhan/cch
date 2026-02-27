"""Unit tests for services using fakes/mocks (no filesystem, no real DB files)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from result import Err, Ok

from cch.config import Config
from cch.data.repositories import ProjectRepository, SessionRepository
from cch.services.container import ServiceContainer
from cch.services.project_service import ProjectService
from cch.services.search_service import SearchService
from cch.services.session_service import SessionService


class FakeDB:
    def __init__(self) -> None:
        self.fetch_all_result: list[dict[str, object]] = []
        self.fetch_one_result: dict[str, object] | None = None
        self.last_fetch_all_sql = ""
        self.last_fetch_all_params: tuple[object, ...] = ()
        self.last_fetch_one_sql = ""
        self.last_fetch_one_params: tuple[object, ...] = ()

    async def fetch_all(
        self, sql: str, params: tuple[object, ...] = ()
    ) -> list[dict[str, object]]:
        self.last_fetch_all_sql = sql
        self.last_fetch_all_params = params
        return self.fetch_all_result

    async def fetch_one(
        self, sql: str, params: tuple[object, ...] = ()
    ) -> dict[str, object] | None:
        self.last_fetch_one_sql = sql
        self.last_fetch_one_params = params
        return self.fetch_one_result

    async def close(self) -> None:
        return


@pytest.mark.asyncio
async def test_search_service_wraps_engine_errors() -> None:
    engine = SimpleNamespace(search=AsyncMock(side_effect=RuntimeError("boom")))
    service = SearchService(engine)  # type: ignore[arg-type]
    result = await service.search("hello")
    assert isinstance(result, Err)
    assert "boom" in result.err_value


@pytest.mark.asyncio
async def test_project_service_found_and_not_found() -> None:
    db = FakeDB()
    svc = ProjectService(ProjectRepository(db))  # type: ignore[arg-type]

    db.fetch_all_result = [
        {
            "project_id": "p1",
            "provider": "claude",
            "project_path": "/tmp/p1",
            "project_name": "p1",
            "session_count": "3",
            "first_activity": "",
            "last_activity": "",
        }
    ]
    listed = await svc.list_projects()
    assert isinstance(listed, Ok)
    assert listed.ok_value[0].session_count == 3

    db.fetch_one_result = None
    missing = await svc.get_project("missing")
    assert isinstance(missing, Err)

    db.fetch_one_result = {
        "project_id": "p2",
        "provider": "codex",
        "project_path": "/tmp/p2",
        "project_name": "p2",
        "session_count": 2.0,
        "first_activity": "",
        "last_activity": "",
    }
    found = await svc.get_project("p2")
    assert isinstance(found, Ok)
    assert found.ok_value.session_count == 2


@pytest.mark.asyncio
async def test_session_service_sort_fallback_and_offset_missing() -> None:
    db = FakeDB()
    svc = SessionService(SessionRepository(db))  # type: ignore[arg-type]

    db.fetch_one_result = {"cnt": 0}
    db.fetch_all_result = []
    result = await svc.list_sessions(sort_by="not-a-column", sort_order="invalid")
    assert isinstance(result, Ok)
    assert "order by s.modified_at desc" in db.last_fetch_all_sql.lower()

    missing = await svc.get_message_offset("s1", "")
    assert missing is None


@pytest.mark.asyncio
async def test_service_container_wiring_and_close(monkeypatch, tmp_path: Path) -> None:
    created: dict[str, object] = {}

    class FakeDatabase:
        def __init__(self, path: Path) -> None:
            created["db_path"] = path

        async def connect(self) -> None:
            created["connected"] = True

        async def close(self) -> None:
            created["closed"] = True

    class FakeIndexer:
        def __init__(self, db: object, config: object) -> None:
            created["indexer"] = (db, config)

    class FakeSearchEngine:
        def __init__(self, db: object) -> None:
            created["search_engine"] = db

    monkeypatch.setattr("cch.services.container.Database", FakeDatabase)
    monkeypatch.setattr("cch.services.container.Indexer", FakeIndexer)
    monkeypatch.setattr("cch.services.container.SearchEngine", FakeSearchEngine)

    config = Config(cache_dir=tmp_path / "cache")
    container = await ServiceContainer.create(config)
    assert created["connected"] is True
    assert created["db_path"] == config.db_path
    await container.close()
    assert created["closed"] is True
