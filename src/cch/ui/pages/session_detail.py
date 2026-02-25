"""Session detail page — full conversation viewer with message filtering."""

from __future__ import annotations

from nicegui import ui
from result import Err

from cch.models.sessions import MessageView as MessageViewModel
from cch.services.cost import estimate_cost
from cch.ui.components.message_view import classify_message, render_message
from cch.ui.deps import get_services
from cch.ui.layout import error_banner, page_layout
from cch.ui.theme import COLORS, format_datetime, format_duration_ms


def setup() -> None:
    """Register the session detail page."""

    @ui.page("/sessions/{session_id}")
    async def session_detail_page(session_id: str) -> None:
        svc = get_services()

        with page_layout("Session"):
            result = await svc.session_service.get_session_detail(session_id)
            if isinstance(result, Err):
                error_banner(result.err_value)
                return

            detail = result.ok_value

            # Header
            with ui.row().classes("w-full items-center gap-4 mb-4"):
                ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/sessions")).props(
                    "flat round"
                )
                with ui.column().classes("gap-0"):
                    ui.label(detail.summary or detail.first_prompt[:80] or "Session").classes(
                        "text-xl font-bold"
                    )
                    with ui.row().classes("gap-2"):
                        ui.label(f"ID: {detail.session_id[:8]}").classes("text-xs").style(
                            f"color: {COLORS['text_muted']}"
                        )
                        if detail.project_name:
                            ui.badge(detail.project_name).props("outline").classes("text-xs")
                        if detail.model:
                            ui.badge(detail.model).props("outline color=secondary").classes(
                                "text-xs"
                            )
                        if detail.git_branch:
                            ui.badge(f"branch: {detail.git_branch}").props("outline").classes(
                                "text-xs"
                            )

            # Metadata cards
            cost = estimate_cost(
                model=detail.model,
                input_tokens=detail.total_input_tokens,
                output_tokens=detail.total_output_tokens,
                cache_read_tokens=detail.total_cache_read_tokens,
                cache_creation_tokens=detail.total_cache_creation_tokens,
            )

            with ui.row().classes("w-full gap-4 flex-wrap mb-4"):
                _mini_stat("Messages", str(detail.message_count))
                _mini_stat("User", str(detail.user_message_count))
                _mini_stat("Assistant", str(detail.assistant_message_count))
                _mini_stat("Tool Calls", str(detail.tool_call_count))
                _mini_stat("Output Tokens", f"{detail.total_output_tokens:,}")
                _mini_stat("Est. Cost", f"${cost['total_cost']:.2f}")
                if detail.created_at:
                    _mini_stat("Created", format_datetime(detail.created_at))
                if detail.duration_ms:
                    _mini_stat("Duration", format_duration_ms(detail.duration_ms))

            # Export buttons
            with ui.row().classes("gap-2 mb-4"):
                ui.button(
                    "Export Markdown",
                    icon="description",
                    on_click=lambda: _export(svc, session_id, "markdown"),
                ).props("outline dense")
                ui.button(
                    "Export JSON",
                    icon="data_object",
                    on_click=lambda: _export(svc, session_id, "json"),
                ).props("outline dense")

            ui.separator()
            ui.label("Conversation").classes("text-lg font-bold mt-2 mb-2")

            # Classify all messages
            msg_categories: list[tuple[MessageViewModel, set[str]]] = [
                (msg, classify_message(msg)) for msg in detail.messages
            ]

            # Count categories
            cat_counts: dict[str, int] = {
                "user": 0,
                "assistant": 0,
                "tool_call": 0,
                "thinking": 0,
                "tool_result": 0,
                "system": 0,
            }
            for _, cats in msg_categories:
                for cat in cats:
                    if cat in cat_counts:
                        cat_counts[cat] += 1

            # Filter state — user and assistant enabled, others off by default
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

            # --- Filter bar FIRST (above messages) ---
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
                    count = cat_counts[cat_key]
                    if count == 0:
                        continue

                    def make_checkbox(key: str, lbl: str, cnt: int) -> None:
                        cb = ui.checkbox(
                            f"{lbl} ({cnt})",
                            value=filter_state[key],
                        ).classes("text-xs")

                        def on_change(e: object, k: str = key) -> None:
                            filter_state[k] = bool(getattr(e, "value", True))
                            refresh_messages()

                        cb.on_value_change(on_change)

                    make_checkbox(cat_key, label, count)

            # --- Messages container SECOND (below filters) ---
            messages_container = ui.column().classes("w-full gap-2")

            def refresh_messages() -> None:
                messages_container.clear()
                with messages_container:
                    visible = 0
                    for msg, cats in msg_categories:
                        if not cats:
                            continue
                        if any(filter_state.get(cat, False) for cat in cats):
                            render_message(msg)
                            visible += 1
                    if visible == 0:
                        ui.label("No messages match the selected filters").classes(
                            "opacity-60 py-4"
                        )

            refresh_messages()


def _mini_stat(label: str, value: str) -> None:
    """Small stat display."""
    with (
        ui.column()
        .classes("gap-0 px-3 py-1")
        .style(
            f"background-color: {COLORS['surface']}; border-radius: 6px; "
            f"border: 1px solid {COLORS['border']}"
        )
    ):
        ui.label(value).classes("text-sm font-bold")
        ui.label(label).classes("text-xs").style(f"color: {COLORS['text_muted']}")


async def _export(svc: object, session_id: str, fmt: str) -> None:
    """Trigger export download."""
    from cch.services.container import ServiceContainer

    assert isinstance(svc, ServiceContainer)
    if fmt == "markdown":
        result = await svc.export_service.export_session_markdown(session_id)
    elif fmt == "json":
        result = await svc.export_service.export_session_json(session_id)
    else:
        return

    if isinstance(result, Err):
        ui.notify(result.err_value, type="negative")
    else:
        ext = "md" if fmt == "markdown" else "json"
        ui.download(result.ok_value.encode(), f"session_{session_id[:8]}.{ext}")
