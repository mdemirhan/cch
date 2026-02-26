"""CLI and entrypoint tests."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cch.cli import _do_reindex, app


def test_cli_serve_invokes_run_app(monkeypatch) -> None:
    called: dict[str, object] = {}

    def fake_run_app(config) -> None:  # type: ignore[no-untyped-def]
        called["config"] = config

    monkeypatch.setattr("cch.ui.app.run_app", fake_run_app)
    runner = CliRunner()
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "config" in called


def test_cli_reindex_invokes_asyncio_run(monkeypatch) -> None:
    called = {"count": 0}

    def fake_asyncio_run(coro) -> None:  # type: ignore[no-untyped-def]
        called["count"] += 1
        coro.close()

    monkeypatch.setattr("cch.cli.asyncio.run", fake_asyncio_run)
    runner = CliRunner()
    result = runner.invoke(app, ["reindex"])
    assert result.exit_code == 0
    assert called["count"] == 1


@pytest.mark.asyncio
async def test_do_reindex_uses_database_and_indexer(monkeypatch, tmp_path: Path) -> None:
    called: dict[str, object] = {}

    class FakeDB:
        def __init__(self, _path: Path) -> None:
            called["db_init"] = True

        async def __aenter__(self) -> FakeDB:
            called["db_enter"] = True
            return self

        async def __aexit__(self, _exc_type, _exc, _tb) -> None:  # type: ignore[no-untyped-def]
            called["db_exit"] = True

    class FakeIndexer:
        def __init__(self, _db: FakeDB, _config) -> None:  # type: ignore[no-untyped-def]
            called["indexer_init"] = True

        async def index_all(self, progress_callback=None, force=False):  # type: ignore[no-untyped-def]
            called["force"] = force
            if progress_callback:
                progress_callback(1, 1, "ok")
            return "ok"

    monkeypatch.setattr("cch.data.db.Database", FakeDB)
    monkeypatch.setattr("cch.data.indexer.Indexer", FakeIndexer)

    from cch.config import Config

    config = Config(
        claude_dir=tmp_path / ".claude",
        codex_dir=tmp_path / ".codex",
        gemini_dir=tmp_path / ".gemini",
        cache_dir=tmp_path / "cache",
    )
    await _do_reindex(config)

    assert called["db_init"] is True
    assert called["db_enter"] is True
    assert called["db_exit"] is True
    assert called["indexer_init"] is True
    assert called["force"] is True


def test_python_module_entrypoint_invokes_cli_app(monkeypatch) -> None:
    called = {"count": 0}

    def fake_app() -> None:
        called["count"] += 1

    monkeypatch.setattr("cch.cli.app", fake_app)
    runpy.run_module("cch.__main__", run_name="__main__")
    assert called["count"] == 1
