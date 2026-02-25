"""Tools analytics page."""

from __future__ import annotations

from nicegui import ui
from result import Err

from cch.ui.components.tool_chart import render_tool_chart
from cch.ui.deps import get_services
from cch.ui.layout import error_banner, page_layout
from cch.ui.theme import COLORS


def setup() -> None:
    """Register the tools page."""

    @ui.page("/tools")
    async def tools_page() -> None:
        svc = get_services()

        with page_layout("Tools"):
            ui.label("Tool Usage Analytics").classes("text-2xl font-bold mb-4")

            result = await svc.analytics_service.get_tool_usage()
            if isinstance(result, Err):
                error_banner(result.err_value)
                return

            tools = result.ok_value
            if not tools:
                ui.label("No tool usage data").classes("opacity-60")
                return

            with ui.row().classes("w-full gap-4"):
                # Bar chart
                with (
                    ui.card().classes("flex-1 p-4").style(f"background-color: {COLORS['surface']}")
                ):
                    render_tool_chart(tools, "Top Tools by Call Count")

                # Pie chart
                with (
                    ui.card().classes("flex-1 p-4").style(f"background-color: {COLORS['surface']}")
                ):
                    ui.label("Tool Distribution").classes("font-bold mb-2")
                    top_10 = tools[:10]
                    fig = {
                        "data": [
                            {
                                "labels": [t.tool_name for t in top_10],
                                "values": [t.call_count for t in top_10],
                                "type": "pie",
                                "hole": 0.4,
                            }
                        ],
                        "layout": {
                            "paper_bgcolor": "rgba(0,0,0,0)",
                            "plot_bgcolor": "rgba(0,0,0,0)",
                            "font": {"color": "#F1F5F9"},
                            "showlegend": True,
                            "legend": {"orientation": "h", "y": -0.2},
                        },
                    }
                    ui.plotly(fig).classes("w-full h-80")

            # Detailed table
            with (
                ui.card()
                .classes("w-full p-4 mt-4")
                .style(f"background-color: {COLORS['surface']}")
            ):
                ui.label("All Tools").classes("font-bold mb-2")
                rows = [
                    {
                        "tool": t.tool_name,
                        "calls": t.call_count,
                        "sessions": t.session_count,
                    }
                    for t in tools
                ]
                columns = [
                    {
                        "name": "tool",
                        "label": "Tool",
                        "field": "tool",
                        "sortable": True,
                        "align": "left",
                    },
                    {
                        "name": "calls",
                        "label": "Calls",
                        "field": "calls",
                        "sortable": True,
                    },
                    {
                        "name": "sessions",
                        "label": "Sessions",
                        "field": "sessions",
                        "sortable": True,
                    },
                ]
                ui.table(
                    columns=columns,
                    rows=rows,
                    row_key="tool",
                    pagination=25,
                ).classes("w-full")
