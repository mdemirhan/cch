"""Protocol definitions for services."""

from __future__ import annotations

from typing import Protocol

from result import Result

from cch.models.analytics import CostBreakdown, HeatmapData, ToolUsageEntry
from cch.models.projects import ProjectSummary
from cch.models.search import SearchResults
from cch.models.sessions import SessionDetail, SessionSummary


class SessionServiceProtocol(Protocol):
    """Interface for session operations."""

    async def list_sessions(
        self,
        project_id: str = "",
        model: str = "",
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "modified_at",
        sort_order: str = "desc",
    ) -> Result[tuple[list[SessionSummary], int], str]: ...

    async def get_session_detail(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> Result[SessionDetail, str]: ...


class ProjectServiceProtocol(Protocol):
    """Interface for project operations."""

    async def list_projects(self) -> Result[list[ProjectSummary], str]: ...

    async def get_project(self, project_id: str) -> Result[ProjectSummary, str]: ...


class AnalyticsServiceProtocol(Protocol):
    """Interface for analytics operations."""

    async def get_cost_breakdown(
        self, period: str = "daily"
    ) -> Result[list[CostBreakdown], str]: ...

    async def get_tool_usage(self) -> Result[list[ToolUsageEntry], str]: ...

    async def get_heatmap_data(self) -> Result[HeatmapData, str]: ...


class SearchServiceProtocol(Protocol):
    """Interface for search operations."""

    async def search(
        self,
        query: str,
        roles: list[str] | None = None,
        project_id: str = "",
        project_ids: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Result[SearchResults, str]: ...
