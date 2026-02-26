"""Analytics service — cost, token, tool, heatmap queries."""

from __future__ import annotations

from result import Ok, Result

from cch.data.repositories import AnalyticsRepository
from cch.models.analytics import CostBreakdown, HeatmapData, ToolUsageEntry
from cch.services.cost import estimate_cost


class AnalyticsService:
    """Service for analytics queries."""

    def __init__(self, repository: AnalyticsRepository) -> None:
        self._repo = repository

    async def get_cost_breakdown(self, period: str = "daily") -> Result[list[CostBreakdown], str]:
        """Get cost breakdown by time period.

        Args:
            period: 'daily', 'weekly', or 'monthly'.
        """
        rows = await self._repo.get_cost_rows(period)

        result: list[CostBreakdown] = []
        for row in rows:
            model = row["model"] or ""
            costs = estimate_cost(
                model=model,
                input_tokens=row["input_tokens"] or 0,
                output_tokens=row["output_tokens"] or 0,
                cache_read_tokens=row["cache_read_tokens"] or 0,
                cache_creation_tokens=row["cache_creation_tokens"] or 0,
            )
            result.append(
                CostBreakdown(
                    date=row["period_date"] or "",
                    model=model,
                    input_cost=costs["input_cost"],
                    output_cost=costs["output_cost"],
                    cache_read_cost=costs["cache_read_cost"],
                    cache_creation_cost=costs["cache_creation_cost"],
                    total_cost=costs["total_cost"],
                )
            )
        return Ok(result)

    async def get_tool_usage(self) -> Result[list[ToolUsageEntry], str]:
        """Get aggregate tool usage statistics."""
        rows = await self._repo.get_tool_usage_rows()
        return Ok(
            [
                ToolUsageEntry(
                    tool_name=row["tool_name"],
                    call_count=row["call_count"],
                    session_count=row["session_count"],
                )
                for row in rows
            ]
        )

    async def get_heatmap_data(self) -> Result[HeatmapData, str]:
        """Get hour-of-day x day-of-week activity data."""
        rows = await self._repo.get_heatmap_rows()

        # Initialize 7x24 grid
        values = [[0] * 24 for _ in range(7)]
        for row in rows:
            dow = row["dow"] or 0  # 0=Sunday in SQLite
            hour = row["hour"] or 0
            # Convert Sunday=0 to Monday=0
            adjusted_dow = (dow - 1) % 7
            if 0 <= adjusted_dow < 7 and 0 <= hour < 24:
                values[adjusted_dow][hour] = row["count"] or 0

        return Ok(HeatmapData(values=values))

    async def get_model_usage(self) -> Result[list[dict[str, object]], str]:
        """Get aggregate model usage statistics."""
        return Ok(await self._repo.get_model_usage_rows())
