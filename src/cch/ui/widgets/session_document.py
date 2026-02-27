"""Pure session-to-HTML document builder for the conversation webview."""

from __future__ import annotations

import importlib.resources
from html import escape

from cch.models.categories import CATEGORY_FILTERS
from cch.models.sessions import SessionDetail
from cch.ui.theme import (
    format_datetime,
    format_duration_ms,
    format_tokens,
    provider_label,
)
from cch.ui.widgets.message_widget import render_message_html, reset_block_counter

_TEMPLATE: str | None = None


def _load_template() -> str:
    files = importlib.resources.files("cch.ui.templates")
    return (files / "conversation.html").read_text(encoding="utf-8")


def _get_template() -> str:
    global _TEMPLATE  # noqa: PLW0603
    if _TEMPLATE is None:
        _TEMPLATE = _load_template()
    return _TEMPLATE


def _empty_state() -> str:
    return '<div class="empty-state">Select a session to view the conversation</div>'


def _render_error_message(msg_uuid: str) -> str:
    safe_uuid = escape(msg_uuid)
    return (
        f'<div class="message system" data-categories="system" '
        f'data-message-uuid="{safe_uuid}" id="msg-{safe_uuid}">'
        '<div class="msg-header"><span class="role-badge system">System</span></div>'
        '<p style="color:#9AA3AA;font-size:12px;font-style:italic;margin:0;">'
        "(message could not be rendered)</p></div>"
    )


def _build_session_header(detail: SessionDetail) -> str:
    title = detail.summary or detail.first_prompt or detail.session_id[:20]
    title = " ".join(title.split())

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
    chips: list[str] = []
    for spec in CATEGORY_FILTERS:
        classes = "filter-chip"
        if spec.key not in active_filters:
            classes += " inactive"
        chips.append(
            f'<button class="{classes}" data-filter="{spec.key}" '
            f'data-label="{escape(spec.label)}" '
            f'style="background-color: {spec.color};" '
            f"onclick=\"toggleFilter('{spec.key}')\">{escape(spec.label)}</button>"
        )
    return "\n".join(chips)


def _filters_js_array(filters: list[str]) -> str:
    if not filters:
        return "[]"
    return "[" + ", ".join(f"'{name}'" for name in filters) + "]"


def build_session_document(detail: SessionDetail, active_filters: list[str]) -> str:
    """Return full conversation HTML for a session."""
    header_html = _build_session_header(detail)
    chips_html = _build_filter_chips(set(active_filters))

    body_parts: list[str] = []
    reset_block_counter()
    for msg in detail.messages:
        try:
            html = render_message_html(msg)
        except Exception:
            html = _render_error_message(msg.uuid)
        if html:
            body_parts.append(html)
    body = "\n".join(body_parts) if body_parts else _empty_state()

    template = _get_template()
    return (
        template.replace("{session_header}", header_html)
        .replace("{filter_chips}", chips_html)
        .replace("{message_body}", body)
        .replace("{initial_filters}", _filters_js_array(active_filters))
    )
