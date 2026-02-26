"""Syntax-highlighted code block widget using Pygments."""

from __future__ import annotations

import os

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer

from cch.ui.theme import COLORS, MONO_FAMILY

# File extension to Pygments lexer name
_EXT_LANG_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".json": "json",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "css",
    ".sql": "sql",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".xml": "xml",
    ".svg": "xml",
    ".r": "r",
    ".lua": "lua",
    ".swift": "swift",
    ".dart": "dart",
}

_FORMATTER = HtmlFormatter(
    style="default",
    noclasses=True,
    nowrap=False,
)


def detect_language(file_path: str) -> str:
    """Detect syntax highlighting language from file extension."""
    _, ext = os.path.splitext(file_path)
    return _EXT_LANG_MAP.get(ext.lower(), "text")


def highlight_code(code: str, language: str = "text") -> str:
    """Return HTML with syntax-highlighted code."""
    try:
        lexer = get_lexer_by_name(language, stripall=True)
    except Exception:
        try:
            lexer = guess_lexer(code)
        except Exception:
            lexer = get_lexer_by_name("text", stripall=True)

    highlighted = highlight(code, lexer, _FORMATTER)

    return f"""<div style="
        background-color: #F5F5F5;
        padding: 10px;
        border-radius: 6px;
        overflow-x: auto;
        font-family: {MONO_FAMILY};
        font-size: 12px;
        line-height: 1.4;
    ">{highlighted}</div>"""


def render_file_header(file_path: str) -> str:
    """Render an HTML file path header badge."""
    return (
        f'<div style="margin-bottom: 4px;">'
        f'<span style="'
        f"font-family: {MONO_FAMILY}; font-size: 11px; "
        f"color: {COLORS['primary']}; "
        f"background-color: {COLORS['primary']}15; "
        f'padding: 2px 8px; border-radius: 4px;">'
        f"{file_path}</span></div>"
    )
