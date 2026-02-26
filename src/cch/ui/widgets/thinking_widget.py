"""Collapsible thinking block — renders assistant thinking as HTML."""

from __future__ import annotations

from html import escape


def render_thinking_html(text: str, *, block_id: str = "", collapsed: bool = True) -> str:
    """Render a thinking block as a collapsible HTML div.

    Args:
        text: The thinking text content.
        block_id: Unique ID for the collapsible element (required for JS toggle).
        collapsed: Whether the block starts collapsed.
    """
    if len(text) > 5000:
        text = text[:5000] + "\n... (truncated)"

    escaped = escape(text).replace("\n", "<br>")
    expanded_cls = "" if collapsed else " expanded"
    max_height = "" if collapsed else ' style="max-height: none;"'
    id_attr = f' id="{block_id}"' if block_id else ""
    onclick = f" onclick=\"toggleCollapsible('{block_id}')\"" if block_id else ""

    return (
        f'<div{id_attr} class="collapsible thinking{expanded_cls}">'
        f'<div class="collapsible-header"{onclick}>'
        f'<span class="chevron">\u25b6</span> <b>Thinking</b>'
        f"</div>"
        f'<div class="collapsible-body"{max_height}>'
        f'<div class="collapsible-body-inner">{escaped}</div>'
        f"</div></div>"
    )
