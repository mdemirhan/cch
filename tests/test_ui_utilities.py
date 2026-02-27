"""Tests for UI utility modules without rendering-heavy dependencies."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cch.ui import async_bridge
from cch.ui.finder import show_in_file_manager
from cch.ui.theme import (
    COLORS,
    build_stylesheet,
    format_datetime,
    format_duration_ms,
    format_relative_time,
    format_tokens,
    provider_color,
    provider_label,
)


def test_theme_build_and_format_helpers() -> None:
    sheet = build_stylesheet()
    assert "QMainWindow" in sheet
    assert COLORS["primary"] in sheet

    now = datetime.now(tz=UTC)
    today_iso = now.isoformat()
    yesterday_iso = (now - timedelta(days=1)).isoformat()
    assert format_datetime(today_iso).startswith("Today ")
    assert format_datetime(yesterday_iso).startswith("Yesterday ")
    assert format_datetime("bad-value") == "bad-value"

    assert format_relative_time((now + timedelta(seconds=5)).isoformat()) == "just now"
    assert format_relative_time((now - timedelta(minutes=2)).isoformat()) == "2m ago"

    assert format_duration_ms(0) == ""
    assert format_duration_ms(1_500) == "1s"
    assert format_duration_ms(61_000) == "1m 1s"
    assert format_duration_ms(3_600_000) == "1h"
    assert format_duration_ms(90_000_000).startswith("1d")

    assert format_tokens(900) == "900"
    assert format_tokens(12_300) == "12.3K"
    assert format_tokens(4_500_000) == "4.5M"

    assert provider_label("codex") == "Codex"
    assert provider_label("gemini") == "Gemini"
    assert provider_label("unknown") == "Claude"
    assert provider_color("codex") == COLORS["provider_codex"]
    assert provider_color("gemini") == COLORS["provider_gemini"]
    assert provider_color("unknown") == COLORS["provider_claude"]


def test_show_in_file_manager_mac_and_non_mac(monkeypatch, tmp_path: Path) -> None:
    target_dir = tmp_path / "a"
    target_dir.mkdir()
    target_file = target_dir / "f.txt"
    target_file.write_text("x", encoding="utf-8")

    popen_calls: list[list[str]] = []
    monkeypatch.setattr("cch.ui.finder.sys.platform", "darwin")
    monkeypatch.setattr("cch.ui.finder.subprocess.Popen", lambda args: popen_calls.append(args))
    assert show_in_file_manager(str(target_dir)) is True
    assert popen_calls and popen_calls[0][0] == "open"

    desktop_calls: list[str] = []
    monkeypatch.setattr("cch.ui.finder.sys.platform", "linux")
    monkeypatch.setattr(
        "cch.ui.finder.QDesktopServices.openUrl",
        lambda url: desktop_calls.append(url.toString()) or True,
    )
    assert show_in_file_manager(str(target_file), parent_dir=True) is True
    assert desktop_calls
    assert show_in_file_manager(str(tmp_path / "missing")) is False


def test_async_bridge_create_event_loop(monkeypatch) -> None:
    created: dict[str, object] = {}

    class FakeLoop:
        pass

    def fake_qeventloop(app) -> FakeLoop:  # type: ignore[no-untyped-def]
        created["app"] = app
        return FakeLoop()

    monkeypatch.setattr("cch.ui.async_bridge.QEventLoop", fake_qeventloop)
    monkeypatch.setattr(
        "cch.ui.async_bridge.asyncio.set_event_loop", lambda loop: created.setdefault("loop", loop)
    )
    loop = async_bridge.create_event_loop(object())  # type: ignore[arg-type]
    assert isinstance(loop, FakeLoop)
    assert created["loop"] is loop


@pytest.mark.asyncio
async def test_async_bridge_schedule_and_cancel() -> None:
    async def sleeper() -> int:
        await asyncio.sleep(0.5)
        return 1

    task = async_bridge.schedule(sleeper())
    assert task in async_bridge._SCHEDULED_TASKS
    async_bridge.cancel_all_tasks()
    await asyncio.sleep(0)
    assert task.cancelled() or task.done()


@pytest.mark.asyncio
async def test_async_slot_decorator_runs_coroutine() -> None:
    called = {"value": 0}

    @async_bridge.async_slot
    async def _slot() -> None:
        called["value"] = 1

    _slot()
    await asyncio.sleep(0)
    assert called["value"] == 1
