"""Projects page — project list with drill-down, filters, and combined view."""

from __future__ import annotations

from nicegui import ui
from result import Err

from cch.models.sessions import MessageView as MessageViewModel
from cch.models.sessions import SessionSummary
from cch.services.container import ServiceContainer
from cch.ui.components.message_view import (
    classify_message,
    render_message_with_badge,
)
from cch.ui.deps import get_services
from cch.ui.layout import error_banner, page_layout
from cch.ui.theme import (
    CHART_COLORS,
    COLORS,
    format_datetime,
    format_duration_ms,
    format_tokens,
)

_MAX_COMBINED_SESSIONS = 20


def setup() -> None:
    """Register the projects page."""

    @ui.page("/projects")
    async def projects_page() -> None:
        svc = get_services()

        with page_layout("Projects"):
            ui.label("Projects").classes("text-2xl font-bold mb-4")

            result = await svc.project_service.list_projects()
            if isinstance(result, Err):
                error_banner(result.err_value)
                return

            projects = result.ok_value
            if not projects:
                ui.label("No projects found").classes("opacity-60")
                return

            rows = [
                {
                    "project_id": p.project_id,
                    "name": p.project_name,
                    "path": p.project_path,
                    "sessions": p.session_count,
                    "last_activity": format_datetime(p.last_activity),
                }
                for p in projects
            ]

            columns = [
                {
                    "name": "name",
                    "label": "Name",
                    "field": "name",
                    "sortable": True,
                    "align": "left",
                },
                {
                    "name": "path",
                    "label": "Path",
                    "field": "path",
                    "sortable": True,
                    "align": "left",
                },
                {
                    "name": "sessions",
                    "label": "Sessions",
                    "field": "sessions",
                    "sortable": True,
                },
                {
                    "name": "last_activity",
                    "label": "Last Activity",
                    "field": "last_activity",
                    "sortable": True,
                    "align": "left",
                },
            ]

            # Sort rows by path by default
            rows.sort(key=lambda r: r["path"])

            table = ui.table(
                columns=columns,
                rows=rows,
                row_key="project_id",
                pagination=50,
            ).classes("w-full")
            table.on(
                "row-click",
                lambda e: ui.navigate.to(f"/projects/{e.args[1]['project_id']}"),
            )

    @ui.page("/projects/{project_id}")
    async def project_detail_page(project_id: str) -> None:
        svc = get_services()

        with page_layout("Project"):
            # Get project info
            proj_result = await svc.project_service.get_project(project_id)
            if isinstance(proj_result, Err):
                error_banner(proj_result.err_value)
                return

            project = proj_result.ok_value

            with ui.row().classes("items-center gap-4 mb-4"):
                ui.button(
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to("/projects"),
                ).props("flat round")
                with ui.column().classes("gap-0"):
                    ui.label(project.project_name).classes("text-2xl font-bold")
                    ui.label(project.project_path).classes("text-xs").style(
                        f"color: {COLORS['text_muted']}"
                    )

            # Fetch sessions list once (shared by both tabs)
            sessions_result = await svc.session_service.list_sessions(
                project_id=project_id, limit=200
            )
            if isinstance(sessions_result, Err):
                error_banner(sessions_result.err_value)
                return

            all_sessions, total = sessions_result.ok_value

            with ui.tabs().classes("w-full") as tabs:
                sessions_tab = ui.tab("Sessions", icon="list")
                combined_tab = ui.tab("Combined View", icon="merge_type")

            with ui.tab_panels(tabs, value=sessions_tab).classes("w-full"):
                with ui.tab_panel(sessions_tab):
                    _build_sessions_tab(svc, project_id, all_sessions, total)

                with ui.tab_panel(combined_tab):
                    _build_combined_tab(svc, all_sessions)


def _build_sessions_tab(
    svc: ServiceContainer,
    project_id: str,
    initial_sessions: list[SessionSummary],
    total: int,
) -> None:
    """Build the Sessions tab (existing table view with filters)."""
    # Filters
    with ui.row().classes("w-full gap-4 items-end mb-4"):
        search_input = (
            ui.input("Search sessions...", placeholder="Filter by summary or prompt")
            .classes("flex-1")
            .props("outlined dense clearable")
        )

        ui.button("Apply", icon="filter_alt", on_click=lambda: apply_filter()).props(
            "outline dense"
        )

    grid_container = ui.column().classes("w-full")

    def apply_filter() -> None:
        grid_container.clear()
        with grid_container:
            sessions = initial_sessions
            search_term = (search_input.value or "").strip().lower()
            if search_term:
                sessions = [
                    s
                    for s in sessions
                    if search_term in (s.summary or "").lower()
                    or search_term in (s.first_prompt or "").lower()
                ]
            _render_sessions_table(sessions, total)

    with grid_container:
        _render_sessions_table(initial_sessions, total)


def _render_sessions_table(sessions: list[SessionSummary], total: int) -> None:
    """Render the sessions data table."""
    ui.label(f"{len(sessions)} of {total} sessions").classes("text-sm mb-2").style(
        f"color: {COLORS['text_muted']}"
    )

    if not sessions:
        ui.label("No sessions match the filters").classes("opacity-60")
        return

    # Sort by modified descending (most recent first)
    sessions = sorted(sessions, key=lambda s: s.modified_at or "", reverse=True)

    rows = [
        {
            "session_id": s.session_id[:8],
            "full_id": s.session_id,
            "summary": (s.summary or s.first_prompt or "")[:100],
            "messages": s.message_count,
            "total_tokens": format_tokens(s.total_input_tokens + s.total_output_tokens),
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


def _build_combined_tab(
    svc: ServiceContainer,
    sessions: list[SessionSummary],
) -> None:
    """Build the Combined View tab with session selector and merged messages."""
    if not sessions:
        ui.label("No sessions in this project").classes("opacity-60")
        return

    # Session selection state: {session_id: checked}
    checked: dict[str, bool] = {s.session_id: True for s in sessions}
    checkboxes: dict[str, ui.checkbox] = {}

    # Session selector panel
    with (
        ui.card()
        .classes("w-full p-4 mb-4")
        .style(f"background-color: {COLORS['surface']}; border: 1px solid {COLORS['border']}")
    ):
        with ui.row().classes("items-center gap-2 mb-3"):
            ui.icon("checklist").style(f"color: {COLORS['primary']}")
            ui.label("Select Sessions").classes("font-bold text-sm")
            ui.label(f"({len(sessions)} available)").classes("text-xs").style(
                f"color: {COLORS['text_muted']}"
            )

        with ui.row().classes("gap-2 mb-3"):

            def select_all() -> None:
                for sid in checked:
                    checked[sid] = True
                for cb in checkboxes.values():
                    cb.set_value(True)

            def deselect_all() -> None:
                for sid in checked:
                    checked[sid] = False
                for cb in checkboxes.values():
                    cb.set_value(False)

            ui.button("Select All", on_click=select_all).props("outline dense size=sm")
            ui.button("Deselect All", on_click=deselect_all).props("outline dense size=sm")

        with ui.row().classes("w-full gap-2 flex-wrap"):
            for idx, s in enumerate(sessions):
                color = CHART_COLORS[idx % len(CHART_COLORS)]
                label = f"{s.session_id[:8]} — {(s.summary or s.first_prompt or 'untitled')[:40]}"

                def make_cb(sid: str, lbl: str, clr: str) -> None:
                    cb = ui.checkbox(lbl, value=True).classes("text-xs")
                    cb.style(f"--q-primary: {clr}")
                    checkboxes[sid] = cb

                    def on_change(e: object, session_id: str = sid) -> None:
                        checked[session_id] = bool(getattr(e, "value", True))

                    cb.on_value_change(on_change)

                make_cb(s.session_id, label, color)

    # Message type filter state
    filter_state: dict[str, bool] = {
        "user": True,
        "assistant": True,
        "tool_call": False,
        "thinking": False,
        "tool_result": False,
        "system": False,
    }

    filter_defs: list[tuple[str, str, str]] = [
        ("user", "person", "User"),
        ("assistant", "smart_toy", "Assistant"),
        ("tool_call", "build", "Tool Calls"),
        ("thinking", "psychology", "Thinking"),
        ("tool_result", "output", "Tool Results"),
        ("system", "settings", "System"),
    ]

    # Filter bar
    filter_bar_container = ui.column().classes("w-full")
    messages_container = ui.column().classes("w-full gap-2")

    # State holders for loaded data
    loaded_messages: list[tuple[MessageViewModel, str, str]] = []  # (msg, label, color)
    loaded_categories: list[tuple[MessageViewModel, set[str], str, str]] = []

    def _refresh_messages() -> None:
        messages_container.clear()
        with messages_container:
            visible = 0
            for msg, cats, label, color in loaded_categories:
                if not cats:
                    continue
                if any(filter_state.get(cat, False) for cat in cats):
                    render_message_with_badge(msg, label, color)
                    visible += 1
            if visible == 0:
                ui.label("No messages match the selected filters").classes("opacity-60 py-4")

    def _build_filter_bar(
        cat_counts: dict[str, int],
    ) -> None:
        filter_bar_container.clear()
        with filter_bar_container:
            with (
                ui.row()
                .classes("w-full gap-3 flex-wrap items-center mb-3 px-3 py-2")
                .style(
                    f"background-color: {COLORS['surface']}; "
                    f"border: 1px solid {COLORS['border']}; border-radius: 8px"
                )
            ):
                ui.icon("filter_list").classes("text-lg").style(f"color: {COLORS['text_muted']}")
                for cat_key, _icon, label in filter_defs:
                    count = cat_counts.get(cat_key, 0)
                    if count == 0:
                        continue

                    def make_filter_cb(key: str, lbl: str, cnt: int) -> None:
                        cb = ui.checkbox(
                            f"{lbl} ({cnt})",
                            value=filter_state[key],
                        ).classes("text-xs")

                        def on_change(e: object, k: str = key) -> None:
                            filter_state[k] = bool(getattr(e, "value", True))
                            _refresh_messages()

                        cb.on_value_change(on_change)

                    make_filter_cb(cat_key, label, count)

    async def load_combined() -> None:
        selected_ids = [sid for sid, is_checked in checked.items() if is_checked]
        if not selected_ids:
            messages_container.clear()
            with messages_container:
                ui.label("No sessions selected").classes("opacity-60 py-4")
            return

        if len(selected_ids) > _MAX_COMBINED_SESSIONS:
            messages_container.clear()
            with messages_container:
                ui.label(
                    f"Too many sessions selected ({len(selected_ids)}). "
                    f"Please select at most {_MAX_COMBINED_SESSIONS}."
                ).classes("text-sm").style(f"color: {COLORS['warning']}")
            return

        # Build session_id -> (label, color) mapping
        session_meta: dict[str, tuple[str, str]] = {}
        for idx, s in enumerate(sessions):
            if s.session_id in selected_ids:
                color = CHART_COLORS[idx % len(CHART_COLORS)]
                label = s.session_id[:8]
                session_meta[s.session_id] = (label, color)

        # Show spinner while loading
        messages_container.clear()
        with messages_container:
            spinner = ui.spinner("dots", size="lg")

        # Load session details
        all_msgs: list[tuple[MessageViewModel, str, str]] = []
        for sid in selected_ids:
            detail_result = await svc.session_service.get_session_detail(sid)
            if isinstance(detail_result, Err):
                continue
            detail = detail_result.ok_value
            label, color = session_meta.get(sid, (sid[:8], CHART_COLORS[0]))
            for msg in detail.messages:
                all_msgs.append((msg, label, color))

        # Sort by timestamp
        all_msgs.sort(key=lambda x: x[0].timestamp or "")

        # Classify and store
        loaded_messages.clear()
        loaded_messages.extend(all_msgs)
        loaded_categories.clear()
        cat_counts: dict[str, int] = {
            "user": 0,
            "assistant": 0,
            "tool_call": 0,
            "thinking": 0,
            "tool_result": 0,
            "system": 0,
        }
        for msg, label, color in all_msgs:
            cats = classify_message(msg)
            loaded_categories.append((msg, cats, label, color))
            for cat in cats:
                if cat in cat_counts:
                    cat_counts[cat] += 1

        # Remove spinner
        spinner.delete()

        _build_filter_bar(cat_counts)
        _refresh_messages()

    # Load button
    with ui.row().classes("gap-2 mb-4"):
        ui.button("Load Combined View", icon="merge_type", on_click=load_combined).props(
            "color=primary"
        )
        selected_count = sum(1 for v in checked.values() if v)
        ui.label(f"{selected_count} sessions selected").classes("text-xs self-center").style(
            f"color: {COLORS['text_muted']}"
        )
