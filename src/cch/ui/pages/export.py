"""Export page — bulk export sessions."""

from __future__ import annotations

from nicegui import ui
from result import Err

from cch.ui.deps import get_services
from cch.ui.layout import error_banner, page_layout
from cch.ui.theme import COLORS


def setup() -> None:
    """Register the export page."""

    @ui.page("/export")
    async def export_page() -> None:
        svc = get_services()

        with page_layout("Export"):
            ui.label("Export Sessions").classes("text-2xl font-bold mb-4")

            # Session selector
            sessions_result = await svc.session_service.list_sessions(limit=200)
            if isinstance(sessions_result, Err):
                error_banner(sessions_result.err_value)
                return

            sessions, _ = sessions_result.ok_value
            session_options = {
                s.session_id: (
                    f"{s.session_id[:8]} — {(s.summary or s.first_prompt or 'Untitled')[:50]}"
                )
                for s in sessions
            }

            session_select = ui.select(session_options, label="Select Session").classes(
                "w-full max-w-xl mb-4"
            )

            format_select = ui.select(
                {"markdown": "Markdown", "json": "JSON", "csv": "CSV"},
                value="markdown",
                label="Format",
            ).classes("min-w-32 mb-4")

            preview_container = ui.column().classes("w-full")

            async def do_export() -> None:
                sid = session_select.value
                fmt = format_select.value
                if not sid:
                    ui.notify("Select a session first", type="warning")
                    return

                match fmt:
                    case "markdown":
                        result = await svc.export_service.export_session_markdown(sid)
                        ext = "md"
                    case "json":
                        result = await svc.export_service.export_session_json(sid)
                        ext = "json"
                    case "csv":
                        result = await svc.export_service.export_session_csv(sid)
                        ext = "csv"
                    case _:
                        return

                if isinstance(result, Err):
                    ui.notify(result.err_value, type="negative")
                    return

                ui.download(result.ok_value.encode(), f"session_{sid[:8]}.{ext}")
                ui.notify(f"Exported as {fmt}", type="positive")

            async def do_preview() -> None:
                sid = session_select.value
                if not sid:
                    return

                preview_container.clear()
                with preview_container:
                    result = await svc.export_service.export_session_markdown(sid)
                    if isinstance(result, Err):
                        error_banner(result.err_value)
                    else:
                        with (
                            ui.card()
                            .classes("w-full p-4")
                            .style(f"background-color: {COLORS['surface']}")
                        ):
                            ui.label("Preview (Markdown)").classes("font-bold mb-2")
                            ui.code(result.ok_value[:5000], language="markdown").classes(
                                "w-full text-xs"
                            )

            with ui.row().classes("gap-2 mb-4"):
                ui.button("Export", icon="download", on_click=do_export).props("dense")
                ui.button("Preview", icon="visibility", on_click=do_preview).props("outline dense")
