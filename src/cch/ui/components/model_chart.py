"""Model usage chart component."""

from __future__ import annotations

from nicegui import ui

from cch.ui.theme import CHART_COLORS


def render_model_chart(data: list[dict[str, object]], title: str = "Model Usage") -> None:
    """Render a pie chart of model usage by session count."""
    if not data:
        ui.label("No model data available").classes("text-sm opacity-60")
        return

    fig = {
        "data": [
            {
                "labels": [d.get("model", "unknown") for d in data],
                "values": [d.get("session_count", 0) for d in data],
                "type": "pie",
                "marker": {"colors": CHART_COLORS[: len(data)]},
                "textinfo": "label+percent",
                "hole": 0.4,
            }
        ],
        "layout": {
            "title": title,
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "font": {"color": "#F1F5F9"},
            "showlegend": True,
            "legend": {"orientation": "h", "y": -0.1},
        },
    }
    ui.plotly(fig).classes("w-full h-80")
