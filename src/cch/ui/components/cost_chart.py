"""Cost chart component using Plotly."""

from __future__ import annotations

from nicegui import ui

from cch.models.analytics import CostBreakdown
from cch.ui.theme import CHART_COLORS


def render_cost_chart(data: list[CostBreakdown], title: str = "Cost Over Time") -> None:
    """Render a stacked bar chart of costs over time."""
    if not data:
        ui.label("No cost data available").classes("text-sm opacity-60")
        return

    dates = sorted(set(d.date for d in data))
    models = sorted(set(d.model for d in data))

    traces = []
    for i, model in enumerate(models):
        model_data = {d.date: d.total_cost for d in data if d.model == model}
        traces.append(
            {
                "x": dates,
                "y": [model_data.get(d, 0) for d in dates],
                "name": model,
                "type": "bar",
                "marker": {"color": CHART_COLORS[i % len(CHART_COLORS)]},
            }
        )

    fig = {
        "data": traces,
        "layout": {
            "title": title,
            "barmode": "stack",
            "xaxis": {"title": "Date"},
            "yaxis": {"title": "Cost (USD)"},
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "font": {"color": "#F1F5F9"},
            "legend": {"orientation": "h", "y": -0.2},
        },
    }
    ui.plotly(fig).classes("w-full h-96")
