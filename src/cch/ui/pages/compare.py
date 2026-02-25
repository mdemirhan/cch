"""Session comparison page — side-by-side viewer."""

from __future__ import annotations

from nicegui import ui
from result import Err

from cch.ui.components.message_view import render_message
from cch.ui.deps import get_services
from cch.ui.layout import error_banner, page_layout


def setup() -> None:
    """Register the compare page."""

    @ui.page("/compare")
    async def compare_page() -> None:
        svc = get_services()

        with page_layout("Compare"):
            ui.label("Compare Sessions").classes("text-2xl font-bold mb-4")

            # Session selectors
            sessions_result = await svc.session_service.list_sessions(limit=200)
            if isinstance(sessions_result, Err):
                error_banner(sessions_result.err_value)
                return

            sessions, _ = sessions_result.ok_value
            session_options = {
                s.session_id: (
                    f"{s.session_id[:8]} — {(s.summary or s.first_prompt or 'Untitled')[:40]}"
                )
                for s in sessions
            }

            with ui.row().classes("w-full gap-4 items-end mb-4"):
                left_select = ui.select(session_options, label="Left Session").classes("flex-1")
                right_select = ui.select(session_options, label="Right Session").classes("flex-1")
                ui.button(
                    "Compare", icon="compare_arrows", on_click=lambda: load_comparison()
                ).props("dense")

            comparison_container = ui.row().classes("w-full gap-4")

            async def load_comparison() -> None:
                comparison_container.clear()
                left_id = left_select.value
                right_id = right_select.value
                if not left_id or not right_id:
                    with comparison_container:
                        ui.label("Select two sessions to compare").classes("opacity-60")
                    return

                with comparison_container:
                    with ui.splitter().classes("w-full").style("height: 70vh") as splitter:
                        with splitter.before, ui.scroll_area().classes("w-full h-full p-2"):
                            left_result = await svc.session_service.get_session_detail(left_id)
                            if isinstance(left_result, Err):
                                error_banner(left_result.err_value)
                            else:
                                detail = left_result.ok_value
                                ui.label(
                                    detail.summary or detail.first_prompt[:60] or "Session"
                                ).classes("font-bold mb-2")
                                for msg in detail.messages:
                                    render_message(msg)

                        with splitter.after, ui.scroll_area().classes("w-full h-full p-2"):
                            right_result = await svc.session_service.get_session_detail(right_id)
                            if isinstance(right_result, Err):
                                error_banner(right_result.err_value)
                            else:
                                detail = right_result.ok_value
                                ui.label(
                                    detail.summary or detail.first_prompt[:60] or "Session"
                                ).classes("font-bold mb-2")
                                for msg in detail.messages:
                                    render_message(msg)
