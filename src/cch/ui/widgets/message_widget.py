"""Single message renderer — builds HTML for one conversation message."""

from __future__ import annotations

import json
from html import escape

from cch.models.categories import normalize_message_type
from cch.models.sessions import MessageView
from cch.ui.theme import MONO_FAMILY, format_tokens
from cch.ui.widgets.markdown_renderer import render_markdown
from cch.ui.widgets.thinking_widget import render_thinking_html
from cch.ui.widgets.tool_call_widget import render_tool_call_html

# Global counter for generating unique block IDs within a render pass
_block_counter: int = 0


def reset_block_counter() -> None:
    """Reset internal render counter before each document render pass."""
    global _block_counter  # noqa: PLW0603
    _block_counter = 0


def _next_block_id(prefix: str = "block") -> str:
    """Return a unique block ID for collapsible elements."""
    global _block_counter  # noqa: PLW0603
    _block_counter += 1
    return f"{prefix}_{_block_counter}"


def classify_message(
    msg: MessageView,
) -> set[str]:
    """Return the set of content categories present in a message."""
    return {normalize_message_type(msg.type)}


def render_message_html(msg: MessageView) -> str:
    """Render a single message as an HTML fragment with data-categories."""
    content_blocks = _parse_content_json(msg.content_json)
    categories = classify_message(msg)
    message_type = normalize_message_type(msg.type)

    if message_type == "system":
        return _render_system(msg, categories)

    if message_type == "user":
        return _render_user(msg, categories)

    if message_type == "assistant":
        return _render_assistant(msg, categories, content_blocks)

    if message_type == "thinking":
        return _render_thinking_message(msg, categories, content_blocks)

    if message_type == "tool_use":
        return _render_tool_use_message(msg, content_blocks, categories)

    if message_type == "tool_result":
        return _render_tool_result(msg, content_blocks, categories)

    return _render_unknown(msg, categories)


# ── Private renderers ──


def _cats_attr(categories: set[str]) -> str:
    """Build data-categories attribute value."""
    return ",".join(sorted(categories))


def _message_attrs(msg: MessageView, categories: set[str], cls: str) -> str:
    cats = _cats_attr(categories)
    return (
        f'class="message {cls}" '
        f'data-categories="{cats}" '
        f'data-message-uuid="{escape(msg.uuid)}" '
        f'id="msg-{escape(msg.uuid)}"'
    )


def _render_user(msg: MessageView, categories: set[str]) -> str:
    """Render a user message."""
    text = msg.content_text.strip()
    if not text:
        body = _empty_placeholder("(empty user message)")
    else:
        md_html = render_markdown(text[:5000])
        body = _extract_body(md_html)

    timestamp = msg.timestamp[:19] if msg.timestamp else ""
    return (
        f"<div {_message_attrs(msg, categories, 'user')}>"
        f'<div class="msg-header">'
        f'<span class="role-badge user">You</span>'
        f'<span class="timestamp">{timestamp}</span>'
        f"</div>"
        f"{body}</div>"
    )


def _render_assistant(
    msg: MessageView,
    categories: set[str],
    content_blocks: list[dict[str, object]],
) -> str:
    """Render an assistant message with text, thinking, and tool calls."""
    has_text = False
    for block in content_blocks:
        if block.get("type") == "text" and str(block.get("text", "")).strip():
            has_text = True

    if not has_text and msg.content_text.strip():
        has_text = True

    if not has_text:
        return _render_unknown(msg, categories)

    parts: list[str] = []

    # Header
    timestamp = msg.timestamp[:19] if msg.timestamp else ""
    model_badge = ""
    if msg.model:
        model_badge = f'<span class="model-badge">{msg.model}</span>'
    token_badge = ""
    if msg.input_tokens or msg.output_tokens:
        token_badge = (
            f'<span class="token-badge">'
            f"{format_tokens(msg.input_tokens)}\u2193 "
            f"{format_tokens(msg.output_tokens)}\u2191</span>"
        )

    parts.append(
        f'<div class="msg-header">'
        f'<span class="role-badge assistant">Assistant</span>'
        f"{model_badge}"
        f'<span class="timestamp">{timestamp}</span>'
        f"{token_badge}"
        f"</div>"
    )

    # Content blocks
    for block in content_blocks:
        if block.get("type") != "text":
            continue
        text = str(block.get("text", ""))
        if text.strip():
            md_html = render_markdown(text[:10000])
            parts.append(_extract_body(md_html))
    if not parts and msg.content_text.strip():
        parts.append(_extract_body(render_markdown(msg.content_text[:10000])))

    body = "\n".join(parts)
    return f"<div {_message_attrs(msg, categories, 'assistant')}>{body}</div>"


def _render_tool_use_message(
    msg: MessageView,
    content_blocks: list[dict[str, object]],
    categories: set[str],
) -> str:
    """Render a canonical tool-use message."""
    parts: list[str] = []

    rendered_tool_use = False
    for block in content_blocks:
        if block.get("type") == "tool_use":
            tool_use = block.get("tool_use")
            if isinstance(tool_use, dict):
                name = str(tool_use.get("name", "unknown"))
                input_json = tool_use.get("input_json", "{}")
                bid = _next_block_id("tool")
                parts.append(render_tool_call_html(name, str(input_json), block_id=bid))
                rendered_tool_use = True

    if not rendered_tool_use:
        for tc in msg.tool_calls:
            bid = _next_block_id("tool")
            parts.append(render_tool_call_html(tc.tool_name, tc.input_json, block_id=bid))

    if not parts:
        return ""

    body = "\n".join(parts)
    return f"<div {_message_attrs(msg, categories, 'tool-call-only')}>{body}</div>"


def _render_thinking_message(
    msg: MessageView,
    categories: set[str],
    content_blocks: list[dict[str, object]],
) -> str:
    """Render a canonical thinking message."""
    parts: list[str] = []
    for block in content_blocks:
        if block.get("type") != "thinking":
            continue
        text = str(block.get("text", ""))
        if text.strip():
            bid = _next_block_id("thinking")
            parts.append(render_thinking_html(text, block_id=bid))
    if not parts and msg.content_text.strip():
        bid = _next_block_id("thinking")
        parts.append(render_thinking_html(msg.content_text, block_id=bid))
    if not parts:
        parts.append(_empty_placeholder("(empty thinking message)"))
    return f"<div {_message_attrs(msg, categories, 'assistant')}>{''.join(parts)}</div>"


def _render_system(msg: MessageView, categories: set[str]) -> str:
    """Render a system or summary message."""
    label = "System"
    timestamp = msg.timestamp[:19] if msg.timestamp else ""
    text = _system_text(msg)
    if text:
        md_html = render_markdown(text[:5000])
        body = _extract_body(md_html)
    else:
        body = _empty_placeholder("(empty system message)")

    return (
        f"<div {_message_attrs(msg, categories, 'system')}>"
        f'<div class="msg-header">'
        f'<span class="role-badge system">{label}</span>'
        f'<span class="timestamp">{timestamp}</span>'
        f"</div>"
        f"{body}</div>"
    )


def _render_tool_result(
    msg: MessageView, blocks: list[dict[str, object]], categories: set[str]
) -> str:
    """Render tool result blocks."""
    from html import escape

    parts: list[str] = []
    for block in blocks:
        if block.get("type") != "tool_result":
            continue
        text = str(block.get("text", ""))
        if not text:
            continue
        if len(text) > 3000:
            text = text[:3000] + "\n... (truncated)"

        escaped = escape(text)
        bid = _next_block_id("result")
        parts.append(
            f'<div id="{bid}" class="collapsible tool-result">'
            f'<div class="collapsible-header" onclick="toggleCollapsible(\'{bid}\')">'
            f'<span class="chevron">\u25b6</span> <b>Tool Result</b>'
            f"</div>"
            f'<div class="collapsible-body">'
            f'<div class="collapsible-body-inner">'
            f'<span style="font-family: {MONO_FAMILY}; font-size: 11px; '
            f'white-space: pre-wrap;">{escaped}</span>'
            f"</div></div></div>"
        )

    if not parts:
        parts.append(_empty_placeholder("(empty tool result)"))

    return f"<div {_message_attrs(msg, categories, 'tool-result')}>{''.join(parts)}</div>"


def _parse_content_json(content_json: str) -> list[dict[str, object]]:
    """Parse content_json string into list of blocks."""
    if not content_json:
        return []
    try:
        data = json.loads(content_json)
        if isinstance(data, list):
            return data  # type: ignore[return-value]
        return []
    except (json.JSONDecodeError, TypeError):
        return []


def _extract_body(html: str) -> str:
    """Extract the <body> content from a full HTML document."""
    start = html.find("<body>")
    end = html.find("</body>")
    if start != -1 and end != -1:
        return html[start + 6 : end]
    return html


def _system_text(msg: MessageView) -> str:
    """Prefer content_text; fallback to text blocks from content_json."""
    text = msg.content_text.strip()
    if text:
        return text
    blocks = _parse_content_json(msg.content_json)
    parts: list[str] = []
    for block in blocks:
        if block.get("type") != "text":
            continue
        value = str(block.get("text", "")).strip()
        if value:
            parts.append(value)
    return "\n\n".join(parts).strip()


def _empty_placeholder(text: str) -> str:
    """Render a lightweight muted placeholder paragraph."""
    return (
        f'<p style="color:#9AA3AA;font-size:12px;font-style:italic;'
        f'margin:0 0 4px 0;">{escape(text)}</p>'
    )


def _render_unknown(msg: MessageView, categories: set[str]) -> str:
    """Render a minimal card for unsupported/empty message structures."""
    message_type = normalize_message_type(msg.type)
    role_label = "Assistant"
    cls = "assistant"
    if message_type == "system":
        role_label = "System"
        cls = "system"
    elif message_type == "user":
        role_label = "You"
        cls = "user"
    timestamp = msg.timestamp[:19] if msg.timestamp else ""
    text = msg.content_text.strip()[:2000]
    body = _empty_placeholder("(unsupported or empty message)")
    if text:
        body += _extract_body(render_markdown(text))

    return (
        f"<div {_message_attrs(msg, categories, cls)}>"
        f'<div class="msg-header">'
        f'<span class="role-badge {cls}">{role_label}</span>'
        f'<span class="timestamp">{timestamp}</span>'
        f"</div>{body}</div>"
    )
