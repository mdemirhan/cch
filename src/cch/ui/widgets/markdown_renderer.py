"""Markdown → HTML conversion for QTextBrowser."""

from __future__ import annotations

import markdown

_PARSER = markdown.Markdown(extensions=["fenced_code", "tables", "nl2br"])


def _sanitize_markdown_input(text: str) -> str:
    """Escape raw HTML tag starts while keeping markdown syntax intact."""
    return text.replace("<", "&lt;")


def render_markdown_body(text: str) -> str:
    """Convert markdown text to inner HTML only (no <!DOCTYPE> wrapper)."""
    _PARSER.reset()
    return _PARSER.convert(_sanitize_markdown_input(text))
