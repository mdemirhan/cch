"""WebEngine-based message view — renders full session as a web page."""

from __future__ import annotations

import importlib.resources
import tempfile
from html import escape
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from cch.models.sessions import SessionDetail
from cch.ui.theme import (
    format_cost,
    format_datetime,
    format_duration_ms,
    format_tokens,
    provider_label,
)
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
_VALID_FILTERS = set(_ALL_FILTER_NAMES)
_DEFAULT_ACTIVE_FILTERS = ["user", "assistant"]
_PERSISTED_ACTIVE_FILTERS: list[str] = list(_DEFAULT_ACTIVE_FILTERS)
_INLINE_CONTENT_LIMIT_BYTES = 1_500_000


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
    if detail.provider:
        meta_parts.append(escape(provider_label(detail.provider)))
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


def _build_filter_chips(active_filters: set[str]) -> str:
    """Build the HTML for filter chip buttons."""
    chips: list[str] = []
    for name, label, color in _FILTERS:
        classes = "filter-chip"
        if name not in active_filters:
            classes += " inactive"
        chips.append(
            f'<button class="{classes}" data-filter="{name}" '
            f'style="background-color: {color};" '
            f"onclick=\"toggleFilter('{name}')\">{escape(label)}</button>"
        )
    return "\n".join(chips)


def _normalize_filters(raw: object) -> list[str] | None:
    """Normalize a raw JS list of filter names into known ordered names."""
    if not isinstance(raw, list):
        return None
    selected = {item for item in raw if isinstance(item, str) and item in _VALID_FILTERS}
    return [name for name in _ALL_FILTER_NAMES if name in selected]


def _filters_js_array(filters: list[str]) -> str:
    """Serialize a list of filter names as a JS array literal."""
    if not filters:
        return "[]"
    return "[" + ", ".join(f"'{name}'" for name in filters) + "]"


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
        self._pending_detail: SessionDetail | None = None
        self._pending_focus_message_uuid: str = ""
        self._current_focus_message_uuid: str = ""
        self._render_generation = 0
        self._rendered_generation = -1
        self._capture_generation = 0
        self._capture_timeout = QTimer(self)
        self._capture_timeout.setSingleShot(True)
        self._capture_timeout.timeout.connect(self._on_capture_timeout)
        self._temp_dir = tempfile.TemporaryDirectory(prefix="cch-webview-")
        self._temp_files: list[Path] = []
        self._webview.loadFinished.connect(self._on_load_finished)

    def show_session(self, detail: SessionDetail, *, focus_message_uuid: str = "") -> None:
        """Render the full session (header + filters + messages)."""
        self._pending_detail = detail
        self._pending_focus_message_uuid = focus_message_uuid
        self._render_generation += 1
        generation = self._render_generation
        self._capture_filters_and_render(generation)

    def _capture_filters_and_render(self, generation: int) -> None:
        """Capture persisted filters from the current page before replacing HTML."""
        self._capture_generation = generation
        self._capture_timeout.start(120)
        script = (
            "(function(){"
            "try {"
            "  if (!window.name) return null;"
            "  var state = JSON.parse(window.name);"
            "  if (!state || typeof state !== 'object') return null;"
            "  var payload = state['cch_state_v1'];"
            "  if (!payload || typeof payload !== 'object') return null;"
            "  if (!Array.isArray(payload.active_filters)) return null;"
            "  return payload.active_filters.slice();"
            "} catch (_e) { return null; }"
            "})()"
        )

        def _on_filters(raw: object) -> None:
            global _PERSISTED_ACTIVE_FILTERS  # noqa: PLW0603
            if generation != self._render_generation:
                return
            normalized = _normalize_filters(raw)
            if normalized is not None:
                _PERSISTED_ACTIVE_FILTERS = normalized
            if self._capture_timeout.isActive():
                self._capture_timeout.stop()
            self._render_pending(generation)

        self._webview.page().runJavaScript(script, _on_filters)

    def _on_capture_timeout(self) -> None:
        """Render even if JS callback doesn't return (e.g., stalled page)."""
        generation = self._capture_generation
        if generation != self._render_generation:
            return
        self._render_pending(generation)

    def _render_pending(self, generation: int) -> None:
        """Render the latest pending session request."""
        if generation != self._render_generation:
            return
        if generation == self._rendered_generation:
            return
        detail = self._pending_detail
        if detail is None:
            return
        self._current_focus_message_uuid = self._pending_focus_message_uuid

        # Build header
        header_html = _build_session_header(detail)

        # Build filter chips
        active_filters = set(_PERSISTED_ACTIVE_FILTERS)
        chips_html = _build_filter_chips(active_filters)

        # Build messages
        parts: list[str] = []
        for msg in detail.messages:
            html = render_message_html(msg)
            if html:
                parts.append(html)
        body = "\n".join(parts) if parts else _empty_state()

        # Build initial filter state JS array
        initial_filters = _filters_js_array(_PERSISTED_ACTIVE_FILTERS)

        # Assemble the page
        template = _get_template()
        document = (
            template.replace("{session_header}", header_html)
            .replace("{filter_chips}", chips_html)
            .replace("{message_body}", body)
            .replace("{initial_filters}", initial_filters)
        )
        self._rendered_generation = generation
        self._load_document(document)

    def _load_document(self, document: str) -> None:
        """Load HTML using the safest transport for the payload size."""
        content = document.encode("utf-8")
        if len(content) <= _INLINE_CONTENT_LIMIT_BYTES:
            self._webview.setContent(content, "text/html;charset=UTF-8")
            return

        # Large pages can exceed QtWebEngine's data URL limits; load from file.
        target = Path(self._temp_dir.name) / f"conversation-{self._render_generation}.html"
        target.write_bytes(content)
        self._temp_files.append(target)
        if len(self._temp_files) > 6:
            old = self._temp_files.pop(0)
            old.unlink(missing_ok=True)
        self._webview.load(QUrl.fromLocalFile(str(target)))

    def _on_load_finished(self, ok: bool) -> None:
        """Apply pending message focus after the page is loaded."""
        if not ok or not self._current_focus_message_uuid:
            return
        target = self._current_focus_message_uuid
        self._current_focus_message_uuid = ""
        script = (
            f"(function(target){{"
            "if (!target) return;"
            "var tries = 0;"
            "var maxTries = 24;"
            "var delayMs = 50;"
            "function attempt(){"
            "  tries += 1;"
            "  if (typeof focusMessageByUuid !== 'function') {"
            "    if (tries < maxTries) { setTimeout(attempt, delayMs); }"
            "    return;"
            "  }"
            "  var focused = false;"
            "  try { focused = !!focusMessageByUuid(target); } catch (_e) { focused = false; }"
            "  if (!focused && tries < maxTries) {"
            "    setTimeout(attempt, delayMs);"
            "  }"
            "}"
            "attempt();"
            f"}})({repr(target)})"
        )
        self._webview.page().runJavaScript(script)

    def scroll_to_top(self) -> None:
        """Scroll to the top of the conversation."""
        self._webview.page().runJavaScript("scrollToTop()")

    def scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the conversation."""
        self._webview.page().runJavaScript("scrollToBottom()")
