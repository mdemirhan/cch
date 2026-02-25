"""Search page with FTS5 full-text search."""

from __future__ import annotations

from nicegui import ui
from result import Err

from cch.ui.components.search_result import render_search_result
from cch.ui.deps import get_services
from cch.ui.layout import error_banner, page_layout
from cch.ui.theme import COLORS


def setup() -> None:
    """Register the search page."""

    @ui.page("/search")
    async def search_page() -> None:
        svc = get_services()

        with page_layout("Search"):
            ui.label("Search").classes("text-2xl font-bold mb-4")

            results_container = ui.column().classes("w-full gap-2")

            async def do_search() -> None:
                query = search_input.value
                if not query or not query.strip():
                    return

                results_container.clear()
                with results_container:
                    ui.spinner("dots", size="lg")

                result = await svc.search_service.search(
                    query=query,
                    role=role_filter.value or "",
                    limit=50,
                )
                results_container.clear()
                with results_container:
                    if isinstance(result, Err):
                        error_banner(result.err_value)
                        return

                    search_results = result.ok_value
                    ui.label(f"{search_results.total_count} results found").classes(
                        "text-sm"
                    ).style(f"color: {COLORS['text_muted']}")

                    if not search_results.results:
                        ui.label("No results found").classes("opacity-60")
                        return

                    for sr in search_results.results:
                        render_search_result(sr)

            with ui.row().classes("w-full gap-4 items-end mb-4"):
                search_input = (
                    ui.input("Search messages...", on_change=None)
                    .classes("flex-1")
                    .props("outlined dense")
                    .on("keydown.enter", do_search)
                )

                role_filter = ui.select(
                    {"": "All Roles", "user": "User", "assistant": "Assistant"},
                    value="",
                    label="Role",
                ).classes("min-w-32")

                ui.button("Search", icon="search", on_click=do_search).props("dense")
