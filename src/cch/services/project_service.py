"""Project service — queries for project data."""

from __future__ import annotations

from typing import TYPE_CHECKING

from result import Err, Ok, Result

from cch.models.projects import ProjectSummary

if TYPE_CHECKING:
    from cch.data.db import Database


class ProjectService:
    """Service for project queries."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def list_projects(self) -> Result[list[ProjectSummary], str]:
        """List all projects sorted by last activity."""
        rows = await self._db.fetch_all("""SELECT * FROM projects ORDER BY last_activity DESC""")
        return Ok([_row_to_project_summary(row) for row in rows])

    async def get_project(self, project_id: str) -> Result[ProjectSummary, str]:
        """Get a single project by ID."""
        row = await self._db.fetch_one(
            "SELECT * FROM projects WHERE project_id = ?", (project_id,)
        )
        if row is None:
            return Err(f"Project {project_id} not found")
        return Ok(_row_to_project_summary(row))


def _row_to_project_summary(row: object) -> ProjectSummary:
    r: dict[str, object] = dict(row)  # type: ignore[arg-type]

    def _to_int(key: str) -> int:
        value = r.get(key, 0)
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return 0
        return 0

    return ProjectSummary(
        project_id=str(r.get("project_id", "") or ""),
        provider=str(r.get("provider", "") or "claude"),
        project_path=str(r.get("project_path", "") or ""),
        project_name=str(r.get("project_name", "") or ""),
        session_count=_to_int("session_count"),
        first_activity=str(r.get("first_activity", "") or ""),
        last_activity=str(r.get("last_activity", "") or ""),
    )
