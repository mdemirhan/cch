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
        return Ok(
            [
                ProjectSummary(
                    project_id=row["project_id"],
                    project_path=row["project_path"] or "",
                    project_name=row["project_name"] or "",
                    session_count=row["session_count"] or 0,
                    first_activity=row["first_activity"] or "",
                    last_activity=row["last_activity"] or "",
                )
                for row in rows
            ]
        )

    async def get_project(self, project_id: str) -> Result[ProjectSummary, str]:
        """Get a single project by ID."""
        row = await self._db.fetch_one(
            "SELECT * FROM projects WHERE project_id = ?", (project_id,)
        )
        if row is None:
            return Err(f"Project {project_id} not found")
        return Ok(
            ProjectSummary(
                project_id=row["project_id"],
                project_path=row["project_path"] or "",
                project_name=row["project_name"] or "",
                session_count=row["session_count"] or 0,
                first_activity=row["first_activity"] or "",
                last_activity=row["last_activity"] or "",
            )
        )
