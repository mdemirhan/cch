"""Project service — queries for project data."""

from __future__ import annotations

from result import Err, Ok, Result

from cch.data.repositories import ProjectRepository
from cch.models.projects import ProjectSummary
from cch.services._row_helpers import row_int, row_str


class ProjectService:
    """Service for project queries."""

    def __init__(self, repository: ProjectRepository) -> None:
        self._repo = repository

    async def list_projects(self) -> Result[list[ProjectSummary], str]:
        """List all projects sorted by last activity."""
        rows = await self._repo.list_project_rows()
        return Ok([_row_to_project_summary(row) for row in rows])

    async def get_project(self, project_id: str) -> Result[ProjectSummary, str]:
        """Get a single project by ID."""
        row = await self._repo.get_project_row(project_id)
        if row is None:
            return Err(f"Project {project_id} not found")
        return Ok(_row_to_project_summary(row))


def _row_to_project_summary(row: object) -> ProjectSummary:
    r: dict[str, object] = dict(row)  # type: ignore[arg-type]
    return ProjectSummary(
        project_id=row_str(r, "project_id"),
        provider=row_str(r, "provider", "claude"),
        project_path=row_str(r, "project_path"),
        project_name=row_str(r, "project_name"),
        session_count=row_int(r, "session_count"),
        first_activity=row_str(r, "first_activity"),
        last_activity=row_str(r, "last_activity"),
    )
