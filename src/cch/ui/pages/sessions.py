"""Sessions list page with sortable table."""

from __future__ import annotations

from nicegui import ui
from result import Err

from cch.ui.deps import get_services
from cch.ui.layout import error_banner, page_layout
from cch.ui.theme import COLORS, format_datetime, format_duration_ms, format_tokens


def setup() -> None:
    """Register the sessions page."""

    @ui.page("/sessions")
    async def sessions_page() -> None:
        svc = get_services()

        with page_layout("Sessions"):
            ui.label("Sessions").classes("text-2xl font-bold mb-2")

            with ui.row().classes("w-full gap-4 items-end mb-4"):
                # Project filter
                projects_result = await svc.project_service.list_projects()
                project_options = {"": "All Projects"}
                if not isinstance(projects_result, Err):
                    for p in projects_result.ok_value:
                        project_options[p.project_id] = p.project_name

                project_select = ui.select(project_options, value="", label="Project").classes(
                    "min-w-48"
                )

                # Model filter
                models_result = await svc.session_service.get_models_used()
                model_options = {"": "All Models"}
                if not isinstance(models_result, Err):
                    for m in models_result.ok_value:
                        model_options[m] = m

                model_select = ui.select(model_options, value="", label="Model").classes(
                    "min-w-48"
                )

                ui.button(
                    "Apply Filters", icon="filter_alt", on_click=lambda: load_sessions()
                ).props("outline")

            # Sessions table container
            grid_container = ui.column().classes("w-full")

            async def load_sessions() -> None:
                grid_container.clear()
                with grid_container:
                    result = await svc.session_service.list_sessions(
                        project_id=project_select.value or "",
                        model=model_select.value or "",
                        limit=200,
                    )
                    if isinstance(result, Err):
                        error_banner(result.err_value)
                        return

                    sessions, total = result.ok_value
                    ui.label(f"{total} sessions found").classes("text-sm").style(
                        f"color: {COLORS['text_muted']}"
                    )

                    if not sessions:
                        ui.label("No sessions found").classes("opacity-60")
                        return

                    # Sort by modified descending (most recent first)
                    sessions.sort(key=lambda s: s.modified_at or "", reverse=True)

                    rows = [
                        {
                            "session_id": s.session_id[:8],
                            "full_id": s.session_id,
                            "project": s.project_name,
                            "summary": (s.summary or s.first_prompt or "")[:100],
                            "messages": s.message_count,
                            "total_tokens": format_tokens(
                                s.total_input_tokens + s.total_output_tokens
                            ),
                            "duration": format_duration_ms(s.duration_ms),
                            "modified": format_datetime(s.modified_at),
                            "modified_raw": s.modified_at or "",
                        }
                        for s in sessions
                    ]

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
                            "name": "total_tokens",
                            "label": "Tokens",
                            "field": "total_tokens",
                            "sortable": True,
                        },
                        {
                            "name": "duration",
                            "label": "Duration",
                            "field": "duration",
                            "sortable": True,
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
                        pagination=50,
                    ).classes("w-full")
                    table.on(
                        "row-click",
                        lambda e: ui.navigate.to(f"/sessions/{e.args[1]['full_id']}"),
                    )

            await load_sessions()
