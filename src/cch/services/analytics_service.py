"""Analytics service — cost, token, tool, heatmap queries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from result import Ok, Result

from cch.models.analytics import CostBreakdown, HeatmapData, ToolUsageEntry
from cch.services.cost import estimate_cost

if TYPE_CHECKING:
    from cch.data.db import Database


class AnalyticsService:
    """Service for analytics queries."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def get_cost_breakdown(self, period: str = "daily") -> Result[list[CostBreakdown], str]:
        """Get cost breakdown by time period.

        Args:
            period: 'daily', 'weekly', or 'monthly'.
        """
        match period:
            case "weekly":
                date_expr = "strftime('%Y-W%W', created_at)"
            case "monthly":
                date_expr = "strftime('%Y-%m', created_at)"
            case _:
                date_expr = "DATE(created_at)"

        rows = await self._db.fetch_all(f"""
            SELECT
                {date_expr} as period_date,
                model,
                SUM(total_input_tokens) as input_tokens,
                SUM(total_output_tokens) as output_tokens,
                SUM(total_cache_read_tokens) as cache_read_tokens,
                SUM(total_cache_creation_tokens) as cache_creation_tokens
            FROM sessions
            WHERE model != ''
            GROUP BY period_date, model
            ORDER BY period_date
        """)

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
        rows = await self._db.fetch_all("""
            SELECT
                tool_name,
                COUNT(*) as call_count,
                COUNT(DISTINCT session_id) as session_count
            FROM tool_calls
            GROUP BY tool_name
            ORDER BY call_count DESC
        """)
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
        rows = await self._db.fetch_all("""
            SELECT
                CAST(strftime('%w', timestamp) AS INTEGER) as dow,
                CAST(strftime('%H', timestamp) AS INTEGER) as hour,
                COUNT(*) as count
            FROM messages
            WHERE timestamp != ''
            GROUP BY dow, hour
        """)

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
        rows = await self._db.fetch_all("""
            SELECT
                model,
                COUNT(*) as session_count,
                SUM(total_output_tokens) as total_output_tokens
            FROM sessions
            WHERE model != ''
            GROUP BY model
            ORDER BY session_count DESC
        """)
        return Ok([dict(row) for row in rows])
