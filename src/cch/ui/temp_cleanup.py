"""Startup cleanup helpers for transient UI files."""

from __future__ import annotations

import logging
import shutil
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_WEBVIEW_TEMP_PREFIX = "cch-webview-"
WEBVIEW_TEMP_MARKER_FILENAME = ".cch-webview-tempdir"


def _resolved(path: Path) -> Path | None:
    try:
        return path.resolve()
    except OSError:
        return None


def _is_safe_temp_root(root: Path) -> bool:
    """Return True only for roots under the system temp directory."""
    resolved_root = _resolved(root)
    system_temp = _resolved(Path(tempfile.gettempdir()))
    if resolved_root is None or system_temp is None:
        return False
    if resolved_root == Path(resolved_root.anchor):
        return False
    return resolved_root == system_temp or system_temp in resolved_root.parents


def _looks_like_webview_temp_dir(path: Path) -> bool:
    """Return True only for directories that match our expected temp structure."""
    if not path.is_dir() or path.is_symlink():
        return False
    if not path.name.startswith(_WEBVIEW_TEMP_PREFIX):
        return False
    marker = path / WEBVIEW_TEMP_MARKER_FILENAME
    if marker.is_file():
        return True
    try:
        entries = list(path.iterdir())
    except OSError:
        return False
    for entry in entries:
        if entry.is_dir():
            return False
        if entry.name == WEBVIEW_TEMP_MARKER_FILENAME:
            continue
        if entry.name.startswith("conversation-") and entry.name.endswith(".html"):
            continue
        return False
    return True


def cleanup_stale_webview_temp_dirs(
    *,
    stale_after_seconds: int = 300,
    temp_root: Path | None = None,
) -> int:
    """Remove stale webview temp directories from previous runs.

    Args:
        stale_after_seconds: Minimum age required before deleting a directory.
        temp_root: Optional temp root override (for tests).

    Returns:
        Count of directories removed.
    """
    root = temp_root or Path(tempfile.gettempdir())
    if not root.is_dir():
        return 0
    if not _is_safe_temp_root(root):
        logger.warning("Skipping webview temp cleanup for unsafe root: %s", root)
        return 0

    now = time.time()
    min_age_seconds = max(stale_after_seconds, 0)
    removed = 0
    for path in root.glob(f"{_WEBVIEW_TEMP_PREFIX}*"):
        if not _looks_like_webview_temp_dir(path):
            continue
        try:
            age_seconds = now - path.stat().st_mtime
        except OSError:
            continue
        if age_seconds < min_age_seconds:
            continue
        try:
            shutil.rmtree(path, ignore_errors=False)
            removed += 1
            logger.info("Removed stale webview temp dir: %s", path)
        except OSError:
            logger.info("Failed removing stale webview temp dir: %s", path, exc_info=True)
    return removed
