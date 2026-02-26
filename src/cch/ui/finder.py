"""Helpers for opening project/session paths in the OS file manager."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def show_in_file_manager(path: str, *, parent_dir: bool = False) -> bool:
    """Open a path in the system file manager.

    Args:
        path: File or directory path.
        parent_dir: If True, open the parent directory of the given path.
    """
    raw = path.strip()
    if not raw:
        return False

    target = Path(raw).expanduser()
    if parent_dir or target.is_file():
        target = target.parent

    if not target.exists():
        return False

    if sys.platform == "darwin":
        subprocess.Popen(["open", str(target)])
        return True

    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
