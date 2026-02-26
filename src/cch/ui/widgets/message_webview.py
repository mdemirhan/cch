"""WebEngine-based message view — renders full session as a web page."""

from __future__ import annotations

import importlib.resources
from html import escape

from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from cch.models.sessions import SessionDetail
from cch.ui.theme import format_cost, format_datetime, format_duration_ms, format_tokens
from cch.ui.widgets.message_widget import render_message_html

# Filter definitions: (name, label, color)
_FILTERS = [
    ("user", "User", "#E67E22"),
    ("assistant", "Assistant", "#27AE60"),
    ("tool_call", "Tool Calls", "#8E44AD"),
    ("thinking", "Thinking", "#9B59B6"),
    ("tool_result", "Results", "#999999"),
    ("system", "System", "#F39C12"),
]

_ALL_FILTER_NAMES = [name for name, _, _ in _FILTERS]


def _load_template() -> str:
    """Load the conversation.html template from the templates package."""
    files = importlib.resources.files("cch.ui.templates")
    return (files / "conversation.html").read_text(encoding="utf-8")


_TEMPLATE: str | None = None


def _get_template() -> str:
    global _TEMPLATE  # noqa: PLW0603
    if _TEMPLATE is None:
        _TEMPLATE = _load_template()
    return _TEMPLATE


def _empty_state() -> str:
    return '<div class="empty-state">Select a session to view the conversation</div>'


def _build_session_header(detail: SessionDetail) -> str:
    """Build the HTML for the session header (title, meta, stats)."""
    from cch.services.cost import estimate_cost

    title = detail.summary or detail.first_prompt or detail.session_id[:20]
    title = " ".join(title.split())  # collapse whitespace

    cost = estimate_cost(
        detail.model,
        detail.total_input_tokens,
        detail.total_output_tokens,
        detail.total_cache_read_tokens,
        detail.total_cache_creation_tokens,
    )

    meta_parts: list[str] = []
    if detail.project_name:
        meta_parts.append(escape(detail.project_name))
    if detail.model:
        meta_parts.append(escape(detail.model))
    if detail.git_branch:
        meta_parts.append(escape(detail.git_branch))
    if detail.created_at:
        meta_parts.append(escape(format_datetime(detail.created_at)))
    meta_html = " &middot; ".join(meta_parts)

    stats: list[str] = [
        f"{detail.message_count} messages",
        f"{format_tokens(detail.total_input_tokens)} in",
        f"{format_tokens(detail.total_output_tokens)} out",
        format_cost(cost["total_cost"]),
    ]
    if detail.duration_ms:
        stats.append(format_duration_ms(detail.duration_ms))
    badges = "".join(f'<span class="stat-badge">{escape(s)}</span>' for s in stats if s)

    return (
        f'<div class="session-header">'
        f'<div class="session-title">{escape(title)}</div>'
        f'<div class="session-meta">{meta_html}</div>'
        f'<div class="session-stats">{badges}</div>'
        f"</div>"
    )


def _build_filter_chips() -> str:
    """Build the HTML for filter chip buttons."""
    chips: list[str] = []
    for name, label, color in _FILTERS:
        chips.append(
            f'<button class="filter-chip" data-filter="{name}" '
            f'style="background-color: {color};" '
            f"onclick=\"toggleFilter('{name}')\">{escape(label)}</button>"
        )
    return "\n".join(chips)


class MessageWebView(QWidget):
    """Full session view powered by QWebEngineView.

    Renders session header, search, filter chips, and messages
    all inside a single web page.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._webview = QWebEngineView()
        layout.addWidget(self._webview)

    def show_session(self, detail: SessionDetail) -> None:
        """Render the full session (header + filters + messages)."""
        # Build header
        header_html = _build_session_header(detail)

        # Build filter chips
        chips_html = _build_filter_chips()

        # Build messages
        parts: list[str] = []
        for msg in detail.messages:
            html = render_message_html(msg)
            if html:
                parts.append(html)
        body = "\n".join(parts) if parts else _empty_state()

        # Build initial filter state JS array
        initial_filters = "[" + ", ".join(f"'{n}'" for n in _ALL_FILTER_NAMES) + "]"

        # Assemble the page
        template = _get_template()
        document = (
            template.replace("{session_header}", header_html)
            .replace("{filter_chips}", chips_html)
            .replace("{message_body}", body)
            .replace("{initial_filters}", initial_filters)
        )
        self._webview.setHtml(document)

    def scroll_to_top(self) -> None:
        """Scroll to the top of the conversation."""
        self._webview.page().runJavaScript("scrollToTop()")

    def scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the conversation."""
        self._webview.page().runJavaScript("scrollToBottom()")
