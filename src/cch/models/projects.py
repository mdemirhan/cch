"""Project-level models."""

from __future__ import annotations

from pydantic import BaseModel
from PySide6.QtCore import Qt


class ProjectRoles:
    """Named Qt UserRole offsets for ProjectSummary data in list models."""

    ID = Qt.ItemDataRole.UserRole
    PATH = Qt.ItemDataRole.UserRole + 1
    SESSION_COUNT = Qt.ItemDataRole.UserRole + 2
    LAST_ACTIVITY = Qt.ItemDataRole.UserRole + 3
    PROVIDER = Qt.ItemDataRole.UserRole + 4


class ProjectSummary(BaseModel):
    """Summary of a project for list views."""

    project_id: str
    provider: str = "claude"
    project_path: str = ""
    project_name: str = ""
    session_count: int = 0
    first_activity: str = ""
    last_activity: str = ""
