"""Collapsible tool call widget with smart rendering per tool type."""

from __future__ import annotations

import json
from html import escape

from cch.ui.theme import COLORS, MONO_FAMILY
from cch.ui.widgets.code_block import detect_language, highlight_code, render_file_header
from cch.ui.widgets.diff_widget import build_diff_html


def render_tool_call_html(
    tool_name: str,
    input_json: str,
    *,
    block_id: str = "",
    collapsed: bool = True,
) -> str:
    """Render a tool call as a collapsible HTML div.

    Args:
        tool_name: Name of the tool (e.g. "Write", "Bash").
        input_json: JSON string of tool input parameters.
        block_id: Unique ID for the collapsible element (required for JS toggle).
        collapsed: Whether the block starts collapsed.
    """
    params = _parse_params(input_json)

    body = _render_tool_body(tool_name, params)

    expanded_cls = "" if collapsed else " expanded"
    max_height = "" if collapsed else ' style="max-height: none;"'
    id_attr = f' id="{block_id}"' if block_id else ""
    onclick = f" onclick=\"toggleCollapsible('{block_id}')\"" if block_id else ""

    return (
        f'<div{id_attr} class="collapsible tool-call{expanded_cls}">'
        f'<div class="collapsible-header"{onclick}>'
        f'<span class="chevron">\u25b6</span> <b>{escape(tool_name)}</b>'
        f"</div>"
        f'<div class="collapsible-body"{max_height}>'
        f'<div class="collapsible-body-inner">{body}</div>'
        f"</div></div>"
    )


def _render_tool_body(name: str, params: dict[str, object]) -> str:
    """Render tool-specific content."""
    match name:
        case "Write":
            file_path = str(params.get("file_path", ""))
            content = str(params.get("content", ""))
            lang = detect_language(file_path)
            if len(content) > 5000:
                content = content[:5000] + "\n... (truncated)"
            return render_file_header(file_path) + highlight_code(content, lang)

        case "Edit":
            file_path = str(params.get("file_path", ""))
            old_string = str(params.get("old_string", ""))
            new_string = str(params.get("new_string", ""))
            max_diff = 3000
            if len(old_string) > max_diff:
                old_string = old_string[:max_diff] + "\n... (truncated)"
            if len(new_string) > max_diff:
                new_string = new_string[:max_diff] + "\n... (truncated)"
            header = render_file_header(file_path)
            replace_badge = ""
            if params.get("replace_all"):
                replace_badge = (
                    f'<span style="font-size: 10px; color: {COLORS["warning"]}; '
                    f"border: 1px solid {COLORS['warning']}; border-radius: 3px; "
                    f'padding: 1px 4px; margin-left: 4px;">replace all</span>'
                )
            return header + replace_badge + build_diff_html(old_string, new_string)

        case "Read":
            file_path = str(params.get("file_path", ""))
            extras: list[str] = []
            if params.get("offset"):
                extras.append(f"offset: {params['offset']}")
            if params.get("limit"):
                extras.append(f"limit: {params['limit']}")
            extra_text = ""
            if extras:
                extra_text = (
                    f'<span style="font-size: 11px; color: {COLORS["text_muted"]};">'
                    f"  {', '.join(extras)}</span>"
                )
            return render_file_header(file_path) + extra_text

        case "Bash":
            command = str(params.get("command", ""))
            desc = str(params.get("description", ""))
            if len(command) > 3000:
                command = command[:3000] + "\n... (truncated)"
            desc_html = ""
            if desc:
                desc_html = (
                    f'<div style="font-size: 11px; color: {COLORS["text_muted"]}; '
                    f'margin-bottom: 4px;">{escape(desc)}</div>'
                )
            return (
                f"{desc_html}"
                f'<div style="'
                f"background-color: #1A1A1A; color: #E0E0E0; "
                f"padding: 10px 14px; border-radius: 6px; "
                f"font-family: {MONO_FAMILY}; font-size: 12px; "
                f"white-space: pre-wrap; word-break: break-all; "
                f"border-left: 3px solid {COLORS['success']};"
                f'"><span style="color: {COLORS["success"]};">$ </span>'
                f"{escape(command)}</div>"
            )

        case "Grep":
            pattern = str(params.get("pattern", ""))
            path = str(params.get("path", "."))
            grep_style = f"color: {COLORS['primary']}; font-family: {MONO_FAMILY}"
            muted = f"color: {COLORS['text_muted']}"
            parts = [
                f'<span style="{grep_style}; '
                f'font-weight: bold; font-size: 12px;">'
                f"/{escape(pattern)}/</span>",
                f'<span style="{muted}; font-size: 11px;"> in {escape(path)}</span>',
            ]
            if params.get("glob"):
                glob_val = escape(str(params["glob"]))
                parts.append(
                    f'<span style="font-size: 10px; {muted}; '
                    f"border: 1px solid {COLORS['border']}; "
                    f"border-radius: 3px; padding: 1px 4px; "
                    f'margin-left: 4px;">glob: {glob_val}</span>'
                )
            return " ".join(parts)

        case "Glob":
            pattern = str(params.get("pattern", ""))
            path = str(params.get("path", "."))
            gs = f"color: {COLORS['primary']}; font-family: {MONO_FAMILY}"
            ms = f"color: {COLORS['text_muted']}"
            return (
                f'<span style="{gs}; '
                f'font-weight: bold; font-size: 12px;">'
                f"{escape(pattern)}</span>"
                f'<span style="{ms}; font-size: 11px;">'
                f" in {escape(path)}</span>"
            )

        case _:
            return _render_json_params(params)


def _render_json_params(params: dict[str, object]) -> str:
    """Render params as formatted JSON (fallback)."""
    formatted = json.dumps(params, indent=2)
    if len(formatted) > 3000:
        formatted = formatted[:3000] + "\n... (truncated)"
    return highlight_code(formatted, "json")


def _parse_params(input_json: str | object) -> dict[str, object]:
    """Parse tool input JSON into a dict."""
    try:
        parsed = json.loads(str(input_json))
        if isinstance(parsed, dict):
            return parsed  # type: ignore[return-value]
        return {}
    except (json.JSONDecodeError, TypeError):
        return {}
