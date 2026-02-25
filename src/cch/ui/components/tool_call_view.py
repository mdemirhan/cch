"""Tool call view component."""

from __future__ import annotations

from nicegui import ui

from cch.models.sessions import ToolCallView
from cch.ui.components.message_view import (
    _parse_tool_params,
    _render_smart_tool_content,
    _tool_icon,
)
from cch.ui.theme import COLORS


def render_tool_call(tc: ToolCallView) -> None:
    """Render a collapsible tool call with smart rendering."""
    params = _parse_tool_params(tc.input_json)
    icon = _tool_icon(tc.tool_name)

    with (
        ui.expansion(f"Tool: {tc.tool_name}", icon=icon)
        .classes("w-full")
        .style(f"background-color: {COLORS['surface_light']}; border-radius: 4px")
    ):
        _render_smart_tool_content(tc.tool_name, params)
