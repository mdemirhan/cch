"""Tool usage chart component."""

from __future__ import annotations

from nicegui import ui

from cch.models.analytics import ToolUsageEntry
from cch.ui.theme import CHART_COLORS


def render_tool_chart(data: list[ToolUsageEntry], title: str = "Tool Usage") -> None:
    """Render a horizontal bar chart of tool usage."""
    if not data:
        ui.label("No tool data available").classes("text-sm opacity-60")
        return

    top_tools = data[:15]
    fig = {
        "data": [
            {
                "x": [t.call_count for t in top_tools],
                "y": [t.tool_name for t in top_tools],
                "type": "bar",
                "orientation": "h",
                "marker": {"color": CHART_COLORS[0]},
            }
        ],
        "layout": {
            "title": title,
            "xaxis": {"title": "Call Count"},
            "yaxis": {"autorange": "reversed"},
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "font": {"color": "#F1F5F9"},
            "margin": {"l": 120},
        },
    }
    ui.plotly(fig).classes("w-full h-96")
