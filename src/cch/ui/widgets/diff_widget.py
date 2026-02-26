"""Unified diff view — renders old_string → new_string as colored HTML."""

from __future__ import annotations

import difflib
from html import escape

from cch.ui.theme import COLORS, MONO_FAMILY


def build_diff_html(old_string: str, new_string: str) -> str:
    """Build HTML for an inline unified diff view."""
    old_lines = old_string.splitlines(keepends=True)
    new_lines = new_string.splitlines(keepends=True)

    diff = difflib.unified_diff(old_lines, new_lines, lineterm="")

    lines_html: list[str] = []
    for line in diff:
        escaped = escape(line.rstrip("\n"))
        if line.startswith("@@") or line.startswith("---") or line.startswith("+++"):
            lines_html.append(f'<div style="{_HEADER_STYLE}">{escaped}</div>')
        elif line.startswith("+"):
            lines_html.append(f'<div style="{_ADDED_STYLE}">{escaped}</div>')
        elif line.startswith("-"):
            lines_html.append(f'<div style="{_REMOVED_STYLE}">{escaped}</div>')
        else:
            lines_html.append(f'<div style="{_CONTEXT_STYLE}">{escaped}</div>')

    if not lines_html:
        return (
            f'<div style="{_CONTAINER_STYLE}">'
            f'<div style="{_CONTEXT_STYLE}">(no changes)</div></div>'
        )

    return f'<div style="{_CONTAINER_STYLE}">' + "\n".join(lines_html) + "</div>"


# ── Inline styles ──

_CONTAINER_STYLE = (
    f"font-family: {MONO_FAMILY}; font-size: 12px; "
    f"line-height: 1.5; border-radius: 6px; overflow-x: auto; "
    f"background-color: #F5F5F5; padding: 8px 0"
)
_LINE_STYLE = "padding: 1px 12px; white-space: pre-wrap; word-break: break-all"
_ADDED_STYLE = f"{_LINE_STYLE}; background-color: rgba(39,174,96,0.15); color: #1B7A3D"
_REMOVED_STYLE = f"{_LINE_STYLE}; background-color: rgba(231,76,60,0.15); color: #C0392B"
_CONTEXT_STYLE = f"{_LINE_STYLE}; color: {COLORS['text_muted']}"
_HEADER_STYLE = (
    f"padding: 2px 12px; white-space: pre-wrap; word-break: break-all; "
    f"color: {COLORS['primary']}; font-weight: bold"
)
