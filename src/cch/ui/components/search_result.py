"""Search result component."""

from __future__ import annotations

from nicegui import ui

from cch.models.search import SearchResult
from cch.ui.theme import COLORS


def render_search_result(result: SearchResult) -> None:
    """Render a single search result with highlighted excerpt."""
    with (
        ui.card()
        .classes("w-full p-3 cursor-pointer")
        .style(f"background-color: {COLORS['surface']}; border: 1px solid {COLORS['border']}")
        .on("click", lambda _e, r=result: ui.navigate.to(f"/sessions/{r.session_id}"))
    ):
        with ui.row().classes("items-center gap-2 mb-1"):
            role_icon = "person" if result.role == "user" else "smart_toy"
            role_color = COLORS["primary"] if result.role == "user" else COLORS["secondary"]
            ui.icon(role_icon).style(f"color: {role_color}")
            ui.label(result.role.capitalize()).classes("text-sm font-bold")
            if result.project_name:
                ui.badge(result.project_name).props("outline").classes("text-xs")
            if result.timestamp:
                ui.label(result.timestamp[:19]).classes("text-xs").style(
                    f"color: {COLORS['text_muted']}"
                )

        ui.html(result.snippet).classes("text-sm")
