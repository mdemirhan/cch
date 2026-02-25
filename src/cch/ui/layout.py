"""Shared page layout with header and navigation drawer."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from nicegui import ui

from cch.ui.theme import COLORS

NAV_ITEMS = [
    ("Dashboard", "/", "dashboard"),
    ("Sessions", "/sessions", "chat"),
    ("Projects", "/projects", "folder"),
    ("Search", "/search", "search"),
    ("Analytics", "/analytics", "bar_chart"),
    ("Tools", "/tools", "build"),
    ("Compare", "/compare", "compare_arrows"),
    ("Export", "/export", "download"),
]


@contextmanager
def page_layout(title: str = "CCH") -> Generator[None]:
    """Shared page shell with dark theme, header, and nav drawer."""
    ui.colors(
        primary=COLORS["primary"],
        secondary=COLORS["secondary"],
        accent=COLORS["accent"],
        positive=COLORS["success"],
        warning=COLORS["warning"],
        negative=COLORS["error"],
    )

    ui.dark_mode(True)

    with (
        ui.header()
        .classes("items-center justify-between px-4 q-py-sm")
        .style(f"background-color: {COLORS['surface']}")
    ):
        with ui.row().classes("items-center gap-2"):
            ui.icon("terminal").classes("text-2xl").style(f"color: {COLORS['primary']}")
            ui.label("Claude Code History").classes("text-lg font-bold")

        with ui.row().classes("items-center gap-1"):
            for label, path, icon in NAV_ITEMS:
                ui.button(
                    label, icon=icon, on_click=lambda _e=None, p=path: ui.navigate.to(p)
                ).props("flat dense").classes("text-xs")

    with ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-4"):
        yield


def error_banner(message: str) -> None:
    """Display an error banner."""
    with (
        ui.card()
        .classes("w-full")
        .style(f"background-color: {COLORS['error']}22; border: 1px solid {COLORS['error']}")
    ):
        with ui.row().classes("items-center gap-2 p-2"):
            ui.icon("error").style(f"color: {COLORS['error']}")
            ui.label(message).style(f"color: {COLORS['error']}")


def stat_card(label: str, value: str | int, icon: str = "info") -> None:
    """Render a stat card."""
    with (
        ui.card()
        .classes("p-4")
        .style(f"background-color: {COLORS['surface']}; border: 1px solid {COLORS['border']}")
    ):
        with ui.row().classes("items-center gap-3"):
            ui.icon(icon).classes("text-3xl").style(f"color: {COLORS['primary']}")
            with ui.column().classes("gap-0"):
                ui.label(str(value)).classes("text-2xl font-bold")
                ui.label(label).classes("text-xs").style(f"color: {COLORS['text_muted']}")
