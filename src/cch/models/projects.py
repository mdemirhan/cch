"""Project-level models."""

from __future__ import annotations

from pydantic import BaseModel


class ProjectSummary(BaseModel):
    """Summary of a project for list views."""

    project_id: str
    provider: str = "claude"
    project_path: str = ""
    project_name: str = ""
    session_count: int = 0
    first_activity: str = ""
    last_activity: str = ""
