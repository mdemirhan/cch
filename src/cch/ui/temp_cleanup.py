"""Startup cleanup helpers for transient UI files."""

from __future__ import annotations

import logging
import shutil
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_WEBVIEW_TEMP_PREFIX = "cch-webview-"


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
    logger.debug(f"Temp dir is {root}")
    if not root.is_dir():
        return 0

    now = time.time()
    removed = 0
    for path in root.glob(f"{_WEBVIEW_TEMP_PREFIX}*"):
        if not path.is_dir():
            continue
        try:
            age_seconds = now - path.stat().st_mtime
        except OSError:
            continue
        if age_seconds < stale_after_seconds:
            continue
        try:
            shutil.rmtree(path, ignore_errors=False)
            removed += 1
            logger.info("Removed stale webview temp dir: %s", path)
        except OSError:
            logger.debug("Failed removing stale webview temp dir: %s", path, exc_info=True)
    return removed
