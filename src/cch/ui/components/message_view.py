"""Message view component for session detail."""

from __future__ import annotations

import difflib
import json
import os
from html import escape

from nicegui import ui

from cch.models.sessions import MessageView as MessageViewModel
from cch.ui.theme import COLORS

# File extension to syntax highlighting language mapping
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

# Inline styles for diff rendering (ui.html strips <style> tags)
_DIFF_CONTAINER = (
    f"font-family: 'SF Mono','Fira Code','Consolas',monospace; font-size: 12px; "
    f"line-height: 1.5; border-radius: 4px; overflow-x: auto; "
    f"background-color: {COLORS['bg']}; padding: 8px 0"
)
_DIFF_LINE = "padding: 1px 12px; white-space: pre-wrap; word-break: break-all"
_DIFF_ADDED = f"{_DIFF_LINE}; background-color: rgba(16,185,129,0.15); color: #6EE7B7"
_DIFF_REMOVED = f"{_DIFF_LINE}; background-color: rgba(239,68,68,0.15); color: #FCA5A5"
_DIFF_CONTEXT = f"{_DIFF_LINE}; color: {COLORS['text_muted']}"
_DIFF_HEADER = (
    f"padding: 2px 12px; white-space: pre-wrap; word-break: break-all; "
    f"color: {COLORS['primary']}; font-weight: bold"
)


def _detect_language(file_path: str) -> str:
    """Detect syntax highlighting language from file extension."""
    _, ext = os.path.splitext(file_path)
    return _EXT_LANG_MAP.get(ext.lower(), "text")


def _render_file_header(file_path: str, icon: str = "description") -> None:
    """Render a file path header badge."""
    with ui.row().classes("items-center gap-2 mb-2"):
        ui.icon(icon).classes("text-sm").style(f"color: {COLORS['primary']}")
        ui.label(file_path).classes("text-xs font-mono").style(
            f"color: {COLORS['primary']}; "
            f"background-color: {COLORS['primary']}15; "
            f"padding: 2px 8px; border-radius: 4px"
        )


def _build_diff_html(old_string: str, new_string: str) -> str:
    """Build HTML for an inline diff view using difflib."""
    old_lines = old_string.splitlines(keepends=True)
    new_lines = new_string.splitlines(keepends=True)

    diff = difflib.unified_diff(old_lines, new_lines, lineterm="")

    lines_html: list[str] = []
    for line in diff:
        escaped = escape(line.rstrip("\n"))
        if line.startswith("@@") or line.startswith("---") or line.startswith("+++"):
            lines_html.append(f'<div style="{_DIFF_HEADER}">{escaped}</div>')
        elif line.startswith("+"):
            lines_html.append(f'<div style="{_DIFF_ADDED}">{escaped}</div>')
        elif line.startswith("-"):
            lines_html.append(f'<div style="{_DIFF_REMOVED}">{escaped}</div>')
        else:
            lines_html.append(f'<div style="{_DIFF_CONTEXT}">{escaped}</div>')

    if not lines_html:
        return (
            f'<div style="{_DIFF_CONTAINER}"><div style="{_DIFF_CONTEXT}">(no changes)</div></div>'
        )

    return f'<div style="{_DIFF_CONTAINER}">' + "\n".join(lines_html) + "</div>"


def _render_smart_tool_content(name: str, params: dict[str, object]) -> None:
    """Render tool-specific content based on tool name."""
    match name:
        case "Write":
            file_path = str(params.get("file_path", ""))
            content = str(params.get("content", ""))
            _render_file_header(file_path, icon="edit_note")
            lang = _detect_language(file_path)
            if len(content) > 5000:
                content = content[:5000] + "\n... (truncated)"
            ui.code(content, language=lang).classes("text-xs w-full")

        case "Edit":
            file_path = str(params.get("file_path", ""))
            old_string = str(params.get("old_string", ""))
            new_string = str(params.get("new_string", ""))
            _render_file_header(file_path, icon="edit")
            if params.get("replace_all"):
                ui.badge("replace all").props("outline color=warning").classes("text-xs mb-1")
            # Truncate very long diffs
            max_diff = 3000
            if len(old_string) > max_diff:
                old_string = old_string[:max_diff] + "\n... (truncated)"
            if len(new_string) > max_diff:
                new_string = new_string[:max_diff] + "\n... (truncated)"
            diff_html = _build_diff_html(old_string, new_string)
            ui.html(diff_html).classes("w-full")

        case "Read":
            file_path = str(params.get("file_path", ""))
            _render_file_header(file_path, icon="visibility")
            extras: list[str] = []
            if params.get("offset"):
                extras.append(f"offset: {params['offset']}")
            if params.get("limit"):
                extras.append(f"limit: {params['limit']}")
            if extras:
                ui.label(", ".join(extras)).classes("text-xs").style(
                    f"color: {COLORS['text_muted']}"
                )

        case "Bash":
            command = str(params.get("command", ""))
            desc = str(params.get("description", ""))
            if desc:
                ui.label(desc).classes("text-xs mb-1").style(f"color: {COLORS['text_muted']}")
            if len(command) > 3000:
                command = command[:3000] + "\n... (truncated)"
            ui.html(
                f'<div style="background-color: {COLORS["bg"]}; '
                f"color: #E2E8F0; padding: 10px 14px; border-radius: 6px; "
                f"font-family: 'SF Mono','Fira Code','Consolas',monospace; "
                f"font-size: 12px; white-space: pre-wrap; word-break: break-all; "
                f'border-left: 3px solid {COLORS["secondary"]}">'
                f'<span style="color: {COLORS["secondary"]}">$ </span>'
                f"{escape(command)}</div>"
            ).classes("w-full")

        case "Grep":
            pattern = str(params.get("pattern", ""))
            path = str(params.get("path", "."))
            with ui.row().classes("items-center gap-2 flex-wrap"):
                ui.icon("search").classes("text-sm").style(f"color: {COLORS['accent']}")
                ui.label(f"/{pattern}/").classes("text-xs font-mono font-bold").style(
                    f"color: {COLORS['accent']}"
                )
                ui.label(f"in {path}").classes("text-xs").style(f"color: {COLORS['text_muted']}")
                if params.get("glob"):
                    ui.badge(f"glob: {params['glob']}").props("outline").classes("text-xs")
                if params.get("type"):
                    ui.badge(f"type: {params['type']}").props("outline").classes("text-xs")

        case "Glob":
            pattern = str(params.get("pattern", ""))
            path = str(params.get("path", "."))
            with ui.row().classes("items-center gap-2"):
                ui.icon("folder_open").classes("text-sm").style(f"color: {COLORS['accent']}")
                ui.label(pattern).classes("text-xs font-mono font-bold").style(
                    f"color: {COLORS['accent']}"
                )
                ui.label(f"in {path}").classes("text-xs").style(f"color: {COLORS['text_muted']}")

        case _:
            # Default: JSON view
            _render_json_params(params)


def _render_json_params(params: dict[str, object]) -> None:
    """Render params as formatted JSON (fallback)."""
    formatted = json.dumps(params, indent=2)
    if len(formatted) > 3000:
        formatted = formatted[:3000] + "\n... (truncated)"
    ui.code(formatted, language="json").classes("text-xs w-full")


def _tool_icon(name: str) -> str:
    """Return an appropriate icon for a tool name."""
    icons: dict[str, str] = {
        "Write": "edit_note",
        "Edit": "edit",
        "Read": "visibility",
        "Bash": "terminal",
        "Grep": "search",
        "Glob": "folder_open",
        "Task": "account_tree",
        "WebFetch": "language",
        "WebSearch": "travel_explore",
    }
    return icons.get(name, "build")


def classify_message(msg: MessageViewModel) -> set[str]:
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


def render_message(msg: MessageViewModel) -> None:
    """Render a single message in the conversation view."""
    if msg.type == "system" or msg.type == "summary":
        _render_system_message(msg)
        return

    if msg.type == "user" and msg.role == "user":
        # Check if this is a tool_result (not a human message)
        content_blocks = _parse_content_json(msg.content_json)
        has_text = any(b.get("type") == "text" for b in content_blocks)
        is_tool_result = any(b.get("type") == "tool_result" for b in content_blocks)

        if is_tool_result and not has_text:
            # Render tool result inline
            for block in content_blocks:
                if block.get("type") == "tool_result":
                    _render_tool_result(block)
            return

        if msg.content_text.strip():
            _render_user_message(msg)
    elif msg.role == "assistant":
        _render_assistant_message(msg)


def render_message_with_badge(msg: MessageViewModel, session_label: str, badge_color: str) -> None:
    """Render a message with a session badge for the combined view."""
    # Inject the session badge before rendering
    with ui.column().classes("w-full gap-0"):
        with ui.row().classes("items-center gap-2 mb-0"):
            ui.badge(session_label).style(
                f"background-color: {badge_color}; color: white; font-size: 10px"
            )
        render_message(msg)


def _render_user_message(msg: MessageViewModel) -> None:
    """Render a user message."""
    with (
        ui.card()
        .classes("w-full p-4")
        .style(
            f"background-color: {COLORS['primary']}15; border-left: 3px solid {COLORS['primary']}"
        )
    ):
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.icon("person").style(f"color: {COLORS['primary']}")
            ui.label("You").classes("font-bold text-sm")
            if msg.timestamp:
                ui.label(msg.timestamp[:19]).classes("text-xs").style(
                    f"color: {COLORS['text_muted']}"
                )
        ui.markdown(msg.content_text[:5000]).classes("text-sm")


def _render_assistant_message(msg: MessageViewModel) -> None:
    """Render an assistant message."""
    content_blocks = _parse_content_json(msg.content_json)

    # Filter: only render if there's text or tool_use content
    has_text = False
    for block in content_blocks:
        if block.get("type") == "text" and str(block.get("text", "")).strip():
            has_text = True
            break
        if block.get("type") == "thinking" and str(block.get("text", "")).strip():
            has_text = True
            break

    has_tool_use = any(b.get("type") == "tool_use" for b in content_blocks)
    if not has_text and not has_tool_use:
        return

    with (
        ui.card()
        .classes("w-full p-4")
        .style(
            f"background-color: {COLORS['surface']}; border-left: 3px solid {COLORS['secondary']}"
        )
    ):
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.icon("smart_toy").style(f"color: {COLORS['secondary']}")
            ui.label("Assistant").classes("font-bold text-sm")
            if msg.model:
                ui.badge(msg.model).props("outline").classes("text-xs")
            if msg.timestamp:
                ui.label(msg.timestamp[:19]).classes("text-xs").style(
                    f"color: {COLORS['text_muted']}"
                )
            if msg.output_tokens:
                ui.label(f"{msg.output_tokens:,} tokens").classes("text-xs").style(
                    f"color: {COLORS['text_muted']}"
                )

        rendered_tool_use = False
        for block in content_blocks:
            match block.get("type"):
                case "text":
                    text = str(block.get("text", ""))
                    if text.strip():
                        ui.markdown(text[:10000]).classes("text-sm")
                case "thinking":
                    text = str(block.get("text", ""))
                    if text.strip():
                        with ui.expansion("Thinking", icon="psychology").classes("w-full text-xs"):
                            ui.markdown(text[:5000]).classes("text-xs opacity-70")
                case "tool_use":
                    tool_use = block.get("tool_use")
                    if isinstance(tool_use, dict):
                        _render_tool_call(tool_use)
                        rendered_tool_use = True

        # Only use msg.tool_calls as fallback when content_json had no tool_use blocks
        if not rendered_tool_use:
            for tc in msg.tool_calls:
                _render_tool_call_view(tc)


def _render_system_message(msg: MessageViewModel) -> None:
    """Render a system or summary message."""
    if not msg.content_text.strip():
        return
    label = "Summary" if msg.type == "summary" else "System"
    icon = "summarize" if msg.type == "summary" else "settings"
    with (
        ui.card()
        .classes("w-full p-4")
        .style(
            f"background-color: {COLORS['accent']}10; border-left: 3px solid {COLORS['accent']}"
        )
    ):
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.icon(icon).style(f"color: {COLORS['accent']}")
            ui.label(label).classes("font-bold text-sm")
            if msg.timestamp:
                ui.label(msg.timestamp[:19]).classes("text-xs").style(
                    f"color: {COLORS['text_muted']}"
                )
        ui.markdown(msg.content_text[:5000]).classes("text-sm")


def _parse_tool_params(input_json: str | object) -> dict[str, object]:
    """Parse tool input JSON into a dict."""
    try:
        parsed = json.loads(str(input_json))
        if isinstance(parsed, dict):
            return parsed  # type: ignore[return-value]
        return {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _render_tool_call(tool_use: dict[str, object]) -> None:
    """Render a tool call from content block with smart rendering."""
    name = str(tool_use.get("name", "unknown"))
    input_json = tool_use.get("input_json", "{}")
    params = _parse_tool_params(input_json)
    icon = _tool_icon(name)

    with (
        ui.expansion(f"Tool: {name}", icon=icon)
        .classes("w-full")
        .style(f"background-color: {COLORS['surface_light']}; border-radius: 4px")
    ):
        _render_smart_tool_content(name, params)


def _render_tool_call_view(tc: object) -> None:
    """Render a ToolCallView from the message model."""
    from cch.models.sessions import ToolCallView

    if not isinstance(tc, ToolCallView):
        return

    params = _parse_tool_params(tc.input_json)
    icon = _tool_icon(tc.tool_name)

    with (
        ui.expansion(f"Tool: {tc.tool_name}", icon=icon)
        .classes("w-full")
        .style(f"background-color: {COLORS['surface_light']}; border-radius: 4px")
    ):
        _render_smart_tool_content(tc.tool_name, params)


def _render_tool_result(block: dict[str, object]) -> None:
    """Render a tool result block (collapsed by default)."""
    text = block.get("text", "")
    if not text:
        return
    text_str = str(text)
    with (
        ui.expansion("Tool Result", icon="output")
        .classes("w-full opacity-60")
        .style(f"background-color: {COLORS['surface_light']}; border-radius: 4px")
    ):
        if len(text_str) > 3000:
            text_str = text_str[:3000] + "\n... (truncated)"
        ui.code(text_str).classes("text-xs w-full")


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
