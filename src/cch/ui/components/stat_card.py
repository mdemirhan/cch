"""Stat card component."""

from __future__ import annotations

from nicegui import ui

from cch.ui.theme import COLORS


def stat_card(label: str, value: str | int, icon: str = "info", color: str = "") -> None:
    """Render a statistic card with icon, value, and label."""
    icon_color = color or COLORS["primary"]
    with (
        ui.card()
        .classes("p-4 flex-1 min-w-48")
        .style(f"background-color: {COLORS['surface']}; border: 1px solid {COLORS['border']}")
    ):
        with ui.row().classes("items-center gap-3"):
            ui.icon(icon).classes("text-3xl").style(f"color: {icon_color}")
            with ui.column().classes("gap-0"):
                ui.label(str(value)).classes("text-2xl font-bold")
                ui.label(label).classes("text-xs").style(f"color: {COLORS['text_muted']}")
