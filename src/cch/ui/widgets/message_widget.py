"""Single message renderer — builds HTML for one conversation message."""

from __future__ import annotations

import json

from cch.models.sessions import MessageView
from cch.ui.theme import MONO_FAMILY, format_tokens
from cch.ui.widgets.markdown_renderer import render_markdown
from cch.ui.widgets.thinking_widget import render_thinking_html
from cch.ui.widgets.tool_call_widget import render_tool_call_html

# Global counter for generating unique block IDs within a render pass
_block_counter: int = 0


def _next_block_id(prefix: str = "block") -> str:
    """Return a unique block ID for collapsible elements."""
    global _block_counter  # noqa: PLW0603
    _block_counter += 1
    return f"{prefix}_{_block_counter}"


def classify_message(msg: MessageView) -> set[str]:
    """Return the set of content categories present in a message."""
    categories: set[str] = set()

    if msg.type in ("summary", "system"):
        categories.add("system")
        return categories

    if msg.role == "user" and msg.type == "user":
        content_blocks = _parse_content_json(msg.content_json)
        has_text = any(b.get("type") == "text" for b in content_blocks)
        is_tool_result = any(b.get("type") == "tool_result" for b in content_blocks)

        if is_tool_result:
            categories.add("tool_result")
        if has_text and msg.content_text.strip():
            categories.add("user")

    elif msg.role == "assistant":
        content_blocks = _parse_content_json(msg.content_json)
        for block in content_blocks:
            match block.get("type"):
                case "text":
                    if str(block.get("text", "")).strip():
                        categories.add("assistant")
                case "thinking":
                    if str(block.get("text", "")).strip():
                        categories.add("thinking")
                case "tool_use":
                    categories.add("tool_call")

        if msg.tool_calls:
            categories.add("tool_call")

    return categories


def render_message_html(msg: MessageView) -> str:
    """Render a single message as an HTML fragment with data-categories."""
    categories = classify_message(msg)

    if msg.type in ("system", "summary"):
        return _render_system(msg, categories)

    if msg.type == "user" and msg.role == "user":
        content_blocks = _parse_content_json(msg.content_json)
        has_text = any(b.get("type") == "text" for b in content_blocks)
        is_tool_result = any(b.get("type") == "tool_result" for b in content_blocks)

        if is_tool_result and not has_text:
            return _render_tool_result(content_blocks, categories)

        if msg.content_text.strip():
            return _render_user(msg, categories)

    if msg.role == "assistant":
        return _render_assistant(msg, categories)

    return ""


# ── Private renderers ──


def _cats_attr(categories: set[str]) -> str:
    """Build data-categories attribute value."""
    return ",".join(sorted(categories))


def _render_user(msg: MessageView, categories: set[str]) -> str:
    """Render a user message."""
    md_html = render_markdown(msg.content_text[:5000])
    body = _extract_body(md_html)

    timestamp = msg.timestamp[:19] if msg.timestamp else ""
    cats = _cats_attr(categories)
    return (
        f'<div class="message user" data-categories="{cats}">'
        f'<div class="msg-header">'
        f'<span class="role-badge user">You</span>'
        f'<span class="timestamp">{timestamp}</span>'
        f"</div>"
        f"{body}</div>"
    )


def _render_assistant(msg: MessageView, categories: set[str]) -> str:
    """Render an assistant message with text, thinking, and tool calls."""
    content_blocks = _parse_content_json(msg.content_json)

    has_text = False
    has_thinking = False
    has_tool_use = False
    for block in content_blocks:
        if block.get("type") == "text" and str(block.get("text", "")).strip():
            has_text = True
        if block.get("type") == "thinking" and str(block.get("text", "")).strip():
            has_thinking = True
        if block.get("type") == "tool_use":
            has_tool_use = True

    # Check fallback tool calls
    if not has_tool_use and msg.tool_calls:
        has_tool_use = True

    if not has_text and not has_thinking and not has_tool_use:
        return ""

    # Tool-call-only messages: compact card without "Assistant" header
    has_content = has_text or has_thinking
    if not has_content and has_tool_use:
        return _render_tool_call_only(msg, content_blocks, categories)

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
    rendered_tool_use = False
    for block in content_blocks:
        match block.get("type"):
            case "text":
                text = str(block.get("text", ""))
                if text.strip():
                    md_html = render_markdown(text[:10000])
                    parts.append(_extract_body(md_html))
            case "thinking":
                text = str(block.get("text", ""))
                if text.strip():
                    bid = _next_block_id("thinking")
                    parts.append(render_thinking_html(text, block_id=bid))
            case "tool_use":
                tool_use = block.get("tool_use")
                if isinstance(tool_use, dict):
                    name = str(tool_use.get("name", "unknown"))
                    input_json = tool_use.get("input_json", "{}")
                    bid = _next_block_id("tool")
                    parts.append(render_tool_call_html(name, str(input_json), block_id=bid))
                    rendered_tool_use = True

    # Fallback: use msg.tool_calls if content_json had no tool_use blocks
    if not rendered_tool_use:
        for tc in msg.tool_calls:
            bid = _next_block_id("tool")
            parts.append(render_tool_call_html(tc.tool_name, tc.input_json, block_id=bid))

    body = "\n".join(parts)
    cats = _cats_attr(categories)
    return f'<div class="message assistant" data-categories="{cats}">{body}</div>'


def _render_tool_call_only(
    msg: MessageView,
    content_blocks: list[dict[str, object]],
    categories: set[str],
) -> str:
    """Render an assistant message that contains only tool calls (no text/thinking)."""
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
    cats = _cats_attr(categories)
    return f'<div class="message tool-call-only" data-categories="{cats}">{body}</div>'


def _render_system(msg: MessageView, categories: set[str]) -> str:
    """Render a system or summary message."""
    if not msg.content_text.strip():
        return ""
    label = "Summary" if msg.type == "summary" else "System"
    timestamp = msg.timestamp[:19] if msg.timestamp else ""
    md_html = render_markdown(msg.content_text[:5000])
    body = _extract_body(md_html)

    cats = _cats_attr(categories)
    return (
        f'<div class="message system" data-categories="{cats}">'
        f'<div class="msg-header">'
        f'<span class="role-badge system">{label}</span>'
        f'<span class="timestamp">{timestamp}</span>'
        f"</div>"
        f"{body}</div>"
    )


def _render_tool_result(blocks: list[dict[str, object]], categories: set[str]) -> str:
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
        return ""

    cats = _cats_attr(categories)
    return f'<div class="message tool-result" data-categories="{cats}">{"".join(parts)}</div>'


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
