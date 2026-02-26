"""Tests for startup cleanup of stale webview temp directories."""

from __future__ import annotations

import time

from cch.ui.temp_cleanup import cleanup_stale_webview_temp_dirs


def test_cleanup_removes_only_stale_temp_dirs(tmp_path) -> None:
    stale_dir = tmp_path / "cch-webview-stale"
    fresh_dir = tmp_path / "cch-webview-fresh"
    other_dir = tmp_path / "not-cch-webview"

    stale_dir.mkdir()
    fresh_dir.mkdir()
    other_dir.mkdir()

    old = time.time() - 7200
    fresh = time.time() - 10
    stale_dir.touch()
    fresh_dir.touch()
    other_dir.touch()
    stale_dir_html = stale_dir / "conversation-1.html"
    stale_dir_html.write_text("x", encoding="utf-8")
    stale_dir.touch()
    stale_dir_html.touch()

    # Set directory mtimes explicitly.
    import os

    os.utime(stale_dir, (old, old))
    os.utime(fresh_dir, (fresh, fresh))

    removed = cleanup_stale_webview_temp_dirs(
        stale_after_seconds=300,
        temp_root=tmp_path,
    )

    assert removed == 1
    assert not stale_dir.exists()
    assert fresh_dir.exists()
    assert other_dir.exists()
