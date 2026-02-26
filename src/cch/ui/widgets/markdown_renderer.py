"""Markdown → HTML conversion for QTextBrowser."""

from __future__ import annotations

import markdown

from cch.ui.theme import COLORS, MONO_FAMILY

_MD = markdown.Markdown(extensions=["fenced_code", "tables", "nl2br"])


def render_markdown(text: str) -> str:
    """Convert markdown text to styled HTML for QTextBrowser."""
    _MD.reset()
    body = _MD.convert(text)
    return _wrap_html(body)


def _wrap_html(body: str) -> str:
    """Wrap HTML body with a styled document."""
    return f"""<!DOCTYPE html>
<html><head><style>
body {{
    font-family: -apple-system, 'SF Pro Text', 'Helvetica Neue', sans-serif;
    font-size: 13px;
    color: {COLORS["text"]};
    line-height: 1.5;
    margin: 0;
    padding: 0;
}}
p {{ margin: 0 0 8px 0; }}
code {{
    font-family: {MONO_FAMILY};
    font-size: 12px;
    background-color: #F5F5F5;
    padding: 1px 4px;
    border-radius: 3px;
}}
pre {{
    background-color: #F5F5F5;
    padding: 10px;
    border-radius: 6px;
    overflow-x: auto;
    font-family: {MONO_FAMILY};
    font-size: 12px;
    line-height: 1.4;
}}
pre code {{
    background-color: transparent;
    padding: 0;
}}
blockquote {{
    border-left: 3px solid {COLORS["border"]};
    margin: 8px 0;
    padding: 4px 12px;
    color: {COLORS["text_muted"]};
}}
table {{
    border-collapse: collapse;
    margin: 8px 0;
}}
th, td {{
    border: 1px solid {COLORS["border"]};
    padding: 4px 8px;
    text-align: left;
}}
th {{
    background-color: {COLORS["panel_bg"]};
    font-weight: 600;
}}
a {{
    color: {COLORS["primary"]};
    text-decoration: none;
}}
h1, h2, h3, h4, h5, h6 {{
    margin: 12px 0 4px 0;
    font-weight: 600;
}}
h1 {{ font-size: 18px; }}
h2 {{ font-size: 16px; }}
h3 {{ font-size: 14px; }}
ul, ol {{ margin: 4px 0; padding-left: 24px; }}
li {{ margin: 2px 0; }}
hr {{
    border: none;
    border-top: 1px solid {COLORS["border"]};
    margin: 12px 0;
}}
</style></head><body>{body}</body></html>"""
