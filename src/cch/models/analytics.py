"""Analytics models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CostBreakdown(BaseModel):
    """Cost breakdown by model/time period."""

    date: str
    model: str = ""
    input_cost: float = 0.0
    output_cost: float = 0.0
    cache_read_cost: float = 0.0
    cache_creation_cost: float = 0.0
    total_cost: float = 0.0


class ToolUsageEntry(BaseModel):
    """Aggregate tool usage data."""

    tool_name: str
    call_count: int = 0
    session_count: int = 0


class HeatmapData(BaseModel):
    """Hour-of-day x day-of-week activity data."""

    hours: list[int] = Field(default_factory=lambda: list(range(24)))
    days: list[str] = Field(
        default_factory=lambda: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    )
    values: list[list[int]] = Field(default_factory=list)
