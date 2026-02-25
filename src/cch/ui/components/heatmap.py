"""Activity heatmap component using ECharts."""

from __future__ import annotations

from nicegui import ui

from cch.models.analytics import HeatmapData
from cch.ui.theme import COLORS


def render_heatmap(data: HeatmapData) -> None:
    """Render an hour-of-day x day-of-week activity heatmap."""
    if not data.values:
        ui.label("No activity data available").classes("text-sm opacity-60")
        return

    # Convert to ECharts format: [[hour, day, value], ...]
    chart_data = []
    max_val = 1
    for day_idx, day_vals in enumerate(data.values):
        for hour_idx, val in enumerate(day_vals):
            chart_data.append([hour_idx, day_idx, val])
            if val > max_val:
                max_val = val

    options = {
        "tooltip": {"position": "top"},
        "grid": {"top": "10%", "left": "15%", "right": "5%", "bottom": "15%"},
        "xAxis": {
            "type": "category",
            "data": [f"{h:02d}" for h in data.hours],
            "splitArea": {"show": True},
            "axisLabel": {"color": COLORS["text_muted"]},
        },
        "yAxis": {
            "type": "category",
            "data": data.days,
            "splitArea": {"show": True},
            "axisLabel": {"color": COLORS["text_muted"]},
        },
        "visualMap": {
            "min": 0,
            "max": max_val,
            "calculable": True,
            "orient": "horizontal",
            "left": "center",
            "bottom": "0%",
            "inRange": {"color": [COLORS["surface"], "#60A5FA", COLORS["primary"]]},
            "textStyle": {"color": COLORS["text_muted"]},
        },
        "series": [
            {
                "name": "Activity",
                "type": "heatmap",
                "data": chart_data,
                "label": {"show": False},
                "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0, 0, 0, 0.5)"}},
            }
        ],
    }
    ui.echart(options).classes("w-full h-64")
