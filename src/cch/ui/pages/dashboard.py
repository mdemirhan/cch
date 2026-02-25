"""Dashboard page — stat cards, heatmap, recent sessions."""

from __future__ import annotations

from nicegui import ui
from result import Err

from cch.services.cost import estimate_cost
from cch.ui.components.heatmap import render_heatmap
from cch.ui.components.model_chart import render_model_chart
from cch.ui.components.stat_card import stat_card
from cch.ui.deps import get_services
from cch.ui.layout import error_banner, page_layout
from cch.ui.theme import COLORS


def setup() -> None:
    """Register the dashboard page."""

    @ui.page("/")
    async def dashboard_page() -> None:
        svc = get_services()

        with page_layout("Dashboard"):
            ui.label("Dashboard").classes("text-2xl font-bold mb-2")

            # Load stats
            stats_result = await svc.session_service.get_stats()
            if isinstance(stats_result, Err):
                error_banner(stats_result.err_value)
                return
            stats = stats_result.ok_value

            total_sessions = stats.get("total_sessions", 0)
            total_messages = stats.get("total_messages", 0)
            total_tool_calls = stats.get("total_tool_calls", 0)
            total_input = stats.get("total_input_tokens", 0)
            total_output = stats.get("total_output_tokens", 0)
            total_cache_read = stats.get("total_cache_read_tokens", 0)
            total_cache_creation = stats.get("total_cache_creation_tokens", 0)

            # Estimate total cost (use default pricing for aggregate)
            cost = estimate_cost(
                model="",
                input_tokens=total_input,
                output_tokens=total_output,
                cache_read_tokens=total_cache_read,
                cache_creation_tokens=total_cache_creation,
            )

            # Stat cards
            with ui.row().classes("w-full gap-4 flex-wrap"):
                stat_card("Sessions", f"{total_sessions:,}", "chat", COLORS["primary"])
                stat_card("Messages", f"{total_messages:,}", "message", COLORS["secondary"])
                stat_card("Tool Calls", f"{total_tool_calls:,}", "build", COLORS["accent"])
                stat_card(
                    "Est. Cost",
                    f"${cost['total_cost']:.2f}",
                    "attach_money",
                    COLORS["success"],
                )

            # Charts row
            with ui.row().classes("w-full gap-4"):
                # Heatmap
                with (
                    ui.card().classes("flex-1 p-4").style(f"background-color: {COLORS['surface']}")
                ):
                    ui.label("Activity Heatmap").classes("font-bold mb-2")
                    heatmap_result = await svc.analytics_service.get_heatmap_data()
                    if isinstance(heatmap_result, Err):
                        ui.label("No data").classes("opacity-60")
                    else:
                        render_heatmap(heatmap_result.ok_value)

                # Model usage pie
                with (
                    ui.card().classes("flex-1 p-4").style(f"background-color: {COLORS['surface']}")
                ):
                    ui.label("Model Usage").classes("font-bold mb-2")
                    model_result = await svc.analytics_service.get_model_usage()
                    if isinstance(model_result, Err):
                        ui.label("No data").classes("opacity-60")
                    else:
                        render_model_chart(model_result.ok_value)

            # Recent sessions
            with ui.card().classes("w-full p-4").style(f"background-color: {COLORS['surface']}"):
                ui.label("Recent Sessions").classes("font-bold mb-2")
                recent_result = await svc.session_service.get_recent_sessions(limit=10)
                if isinstance(recent_result, Err):
                    ui.label("No sessions found").classes("opacity-60")
                else:
                    sessions = recent_result.ok_value
                    if not sessions:
                        ui.label("No sessions indexed yet").classes("opacity-60")
                    else:
                        rows = []
                        for s in sessions:
                            rows.append(
                                {
                                    "session_id": s.session_id[:8],
                                    "full_id": s.session_id,
                                    "project": s.project_name,
                                    "summary": (s.summary or s.first_prompt or "")[:80],
                                    "messages": s.message_count,
                                    "tools": s.tool_call_count,
                                    "model": s.model or "",
                                    "modified": s.modified_at[:19] if s.modified_at else "",
                                }
                            )

                        columns = [
                            {
                                "name": "session_id",
                                "label": "ID",
                                "field": "session_id",
                                "sortable": True,
                                "align": "left",
                            },
                            {
                                "name": "project",
                                "label": "Project",
                                "field": "project",
                                "sortable": True,
                                "align": "left",
                            },
                            {
                                "name": "summary",
                                "label": "Summary",
                                "field": "summary",
                                "sortable": True,
                                "align": "left",
                            },
                            {
                                "name": "messages",
                                "label": "Msgs",
                                "field": "messages",
                                "sortable": True,
                            },
                            {
                                "name": "tools",
                                "label": "Tools",
                                "field": "tools",
                                "sortable": True,
                            },
                            {
                                "name": "model",
                                "label": "Model",
                                "field": "model",
                                "sortable": True,
                                "align": "left",
                            },
                            {
                                "name": "modified",
                                "label": "Modified",
                                "field": "modified",
                                "sortable": True,
                                "align": "left",
                            },
                        ]

                        table = ui.table(
                            columns=columns,
                            rows=rows,
                            row_key="full_id",
                        ).classes("w-full")
                        table.on(
                            "row-click",
                            lambda e: ui.navigate.to(f"/sessions/{e.args[1]['full_id']}"),
                        )
