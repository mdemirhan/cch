"""Provider-aware session parser for Claude/Codex/Gemini session files."""

from __future__ import annotations

import json
import logging
from collections.abc import Generator
from pathlib import Path

from cch.models.categories import MessageType, normalize_message_type
from cch.models.messages import ContentBlock, ParsedMessage, TokenUsage, ToolUseBlock

logger = logging.getLogger(__name__)


def parse_session_file(
    path: Path,
    *,
    provider: str = "claude",
    session_id: str = "",
) -> Generator[ParsedMessage]:
    """Stream-parse a provider session file and yield canonical messages.

    Canonical message types:
      - user
      - assistant
      - tool_use
      - tool_result
      - thinking
      - system
    """
    normalized_provider = provider.strip().lower() or "claude"
    fallback_session = session_id or path.stem

    match normalized_provider:
        case "codex":
            yield from _parse_codex_session(path, fallback_session)
        case "gemini":
            yield from _parse_gemini_session(path, fallback_session)
        case _:
            yield from _parse_claude_session(path, fallback_session)


def _parse_claude_session(path: Path, session_key: str) -> Generator[ParsedMessage]:
    sequence = 0
    with open(path, encoding="utf-8") as file:
        for line_num, line in enumerate(file, 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON at %s:%d", path, line_num)
                continue

            msg_type = _as_str(raw.get("type"))
            match msg_type:
                case "user" | "assistant":
                    parsed = _parse_claude_conversation_message(raw, sequence, session_key)
                case "summary":
                    parsed = _parse_summary_message(raw, sequence, session_key)
                case "system":
                    parsed = _parse_system_message(raw, sequence, session_key)
                case "progress" | "file-history-snapshot" | "queue-operation":
                    continue
                case _:
                    continue

            for msg in parsed:
                msg.sequence_num = sequence
                if not msg.uuid:
                    msg.uuid = _fallback_uuid(session_key, sequence)
                sequence += 1
                yield msg


def _parse_codex_session(path: Path, session_key: str) -> Generator[ParsedMessage]:
    sequence = 0
    current_model = ""

    with open(path, encoding="utf-8") as file:
        for line_num, line in enumerate(file, 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON at %s:%d", path, line_num)
                continue

            timestamp = _as_str(raw.get("timestamp"))
            msg_type = _as_str(raw.get("type"))

            if msg_type == "turn_context":
                payload = raw.get("payload")
                if isinstance(payload, dict):
                    current_model = _as_str(payload.get("model"))
                continue

            if msg_type != "response_item":
                continue

            payload = raw.get("payload")
            if not isinstance(payload, dict):
                continue

            payload_type = _as_str(payload.get("type"))
            parsed: list[ParsedMessage] = []

            if payload_type == "message":
                role = _as_str(payload.get("role"))
                if role not in {"user", "assistant"}:
                    continue
                blocks, text = _parse_codex_content(payload.get("content"))
                parsed = _normalize_parts(
                    session_key=session_key,
                    sequence_start=sequence,
                    base_uuid=_as_str(payload.get("id")),
                    parent_uuid=None,
                    source_type=role,
                    model=current_model,
                    content_blocks=blocks,
                    content_text=text,
                    usage=TokenUsage(),
                    timestamp=timestamp,
                )

            elif payload_type == "function_call":
                tool_name = _as_str(payload.get("name")) or "tool"
                call_id = _as_str(payload.get("call_id")) or _fallback_tool_id(
                    session_key,
                    sequence,
                )
                arguments = payload.get("arguments")
                input_json = _safe_json_string(arguments)
                parsed = [
                    ParsedMessage(
                        uuid=_fallback_uuid(session_key, sequence),
                        type=MessageType.TOOL_USE,
                        model=current_model,
                        content_blocks=[
                            ContentBlock(
                                type="tool_use",
                                tool_use=ToolUseBlock(
                                    tool_use_id=call_id,
                                    name=tool_name,
                                    input_json=input_json,
                                ),
                            )
                        ],
                        content_text=f"{tool_name}\n{input_json}",
                        timestamp=timestamp,
                    )
                ]

            elif payload_type == "function_call_output":
                output = _extract_codex_function_output(payload.get("output"))
                parsed = [
                    ParsedMessage(
                        uuid=_fallback_uuid(session_key, sequence),
                        type=MessageType.TOOL_RESULT,
                        model=current_model,
                        content_blocks=[ContentBlock(type="tool_result", text=output)],
                        content_text=output,
                        timestamp=timestamp,
                    )
                ]

            elif payload_type == "reasoning":
                thinking_text = _extract_codex_reasoning(payload)
                if thinking_text:
                    parsed = [
                        ParsedMessage(
                            uuid=_fallback_uuid(session_key, sequence),
                            type=MessageType.THINKING,
                            model=current_model,
                            content_blocks=[ContentBlock(type="thinking", text=thinking_text)],
                            content_text=thinking_text,
                            timestamp=timestamp,
                        )
                    ]

            for msg in parsed:
                msg.sequence_num = sequence
                if not msg.uuid:
                    msg.uuid = _fallback_uuid(session_key, sequence)
                sequence += 1
                yield msg


def _parse_gemini_session(path: Path, session_key: str) -> Generator[ParsedMessage]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("Invalid Gemini JSON file: %s", path)
        return

    if not isinstance(payload, dict):
        return

    messages = payload.get("messages")
    if not isinstance(messages, list):
        return

    sequence = 0
    for raw in messages:
        if not isinstance(raw, dict):
            continue

        msg_type = _as_str(raw.get("type")).lower()
        timestamp = _as_str(raw.get("timestamp"))
        model = _as_str(raw.get("model"))
        base_uuid = _as_str(raw.get("id"))
        usage = _parse_gemini_usage(raw.get("tokens"))
        parsed: list[ParsedMessage] = []

        if msg_type == "user":
            text = _extract_gemini_content_text(raw.get("content"))
            parsed = _normalize_parts(
                session_key=session_key,
                sequence_start=sequence,
                base_uuid=base_uuid,
                parent_uuid=None,
                source_type="user",
                model=model,
                content_blocks=[ContentBlock(type="text", text=text)] if text else [],
                content_text=text,
                usage=usage,
                timestamp=timestamp,
            )
        elif msg_type in {"gemini", "assistant", "model"}:
            text = _extract_gemini_content_text(raw.get("content"))
            thoughts = _extract_gemini_thoughts(raw.get("thoughts"))
            blocks: list[ContentBlock] = []
            text_parts: list[str] = []
            if thoughts:
                blocks.append(ContentBlock(type="thinking", text=thoughts))
                text_parts.append(thoughts)
            if text:
                blocks.append(ContentBlock(type="text", text=text))
                text_parts.append(text)
            parsed = _normalize_parts(
                session_key=session_key,
                sequence_start=sequence,
                base_uuid=base_uuid,
                parent_uuid=None,
                source_type="assistant",
                model=model,
                content_blocks=blocks,
                content_text="\n".join(text_parts),
                usage=usage,
                timestamp=timestamp,
            )
        elif msg_type == "info":
            text = _extract_gemini_content_text(raw.get("content"))
            parsed = _normalize_parts(
                session_key=session_key,
                sequence_start=sequence,
                base_uuid=base_uuid,
                parent_uuid=None,
                source_type="system",
                model=model,
                content_blocks=[ContentBlock(type="text", text=text)] if text else [],
                content_text=text,
                usage=TokenUsage(),
                timestamp=timestamp,
            )

        for msg in parsed:
            msg.sequence_num = sequence
            if not msg.uuid:
                msg.uuid = _fallback_uuid(session_key, sequence)
            sequence += 1
            yield msg


def _parse_claude_conversation_message(
    raw: dict[str, object],
    sequence: int,
    session_key: str,
) -> list[ParsedMessage]:
    msg = raw.get("message")
    if not isinstance(msg, dict):
        return []

    source_type = _as_str(raw.get("type"))
    model = _as_str(msg.get("model"))
    uuid = _as_str(raw.get("uuid"))
    parent_uuid = _as_optional_str(raw.get("parentUuid"))
    timestamp = _as_str(raw.get("timestamp"))
    is_sidechain = bool(raw.get("isSidechain", False))

    usage_raw = msg.get("usage")
    usage_dict = usage_raw if isinstance(usage_raw, dict) else {}
    usage = TokenUsage(
        input_tokens=_int(usage_dict.get("input_tokens", 0)),
        output_tokens=_int(usage_dict.get("output_tokens", 0)),
        cache_read_tokens=_int(usage_dict.get("cache_read_input_tokens", 0)),
        cache_creation_tokens=_int(usage_dict.get("cache_creation_input_tokens", 0)),
    )

    raw_content = msg.get("content", [])
    content_blocks: list[ContentBlock] = []
    text_parts: list[str] = []
    if isinstance(raw_content, str):
        content_blocks.append(ContentBlock(type="text", text=raw_content))
        text_parts.append(raw_content)
    elif isinstance(raw_content, list):
        for block in raw_content:
            if isinstance(block, str):
                content_blocks.append(ContentBlock(type="text", text=block))
                text_parts.append(block)
            elif isinstance(block, dict):
                parsed_block = _parse_claude_content_block(block)
                content_blocks.append(parsed_block)
                if parsed_block.type in {"text", "thinking", "tool_result"} and parsed_block.text:
                    text_parts.append(parsed_block.text)

    messages = _normalize_parts(
        session_key=session_key,
        sequence_start=sequence,
        base_uuid=uuid,
        parent_uuid=parent_uuid,
        source_type=source_type,
        model=model,
        content_blocks=content_blocks,
        content_text="\n".join(text_parts),
        usage=usage,
        timestamp=timestamp,
        is_sidechain=is_sidechain,
    )
    return messages


def _normalize_parts(
    *,
    session_key: str,
    sequence_start: int,
    base_uuid: str,
    parent_uuid: str | None,
    source_type: str,
    model: str,
    content_blocks: list[ContentBlock],
    content_text: str,
    usage: TokenUsage,
    timestamp: str,
    is_sidechain: bool = False,
) -> list[ParsedMessage]:
    """Split provider-specific payload into canonical single-type messages."""
    normalized_source = source_type.strip().lower()
    parts: list[tuple[str, list[ContentBlock], str]] = []

    if normalized_source in {"summary", "system", "info"}:
        text = content_text.strip() or _first_text(content_blocks)
        parts.append(
            (
                MessageType.SYSTEM,
                [ContentBlock(type="text", text=text)] if text else [],
                text,
            )
        )
    elif normalized_source == "user":
        for block in content_blocks:
            block_type = block.type.strip().lower()
            if block_type == "tool_result":
                text = block.text.strip()
                parts.append(
                    (
                        MessageType.TOOL_RESULT,
                        [ContentBlock(type="tool_result", text=text)],
                        text,
                    )
                )
            elif block_type == "user":
                text = block.text
                if text.strip():
                    parts.append(
                        (
                            MessageType.USER,
                            [ContentBlock(type="text", text=text)],
                            text,
                        )
                    )
        if not parts and content_text.strip():
            parts.append(
                (
                    MessageType.USER,
                    [ContentBlock(type="text", text=content_text)],
                    content_text,
                )
            )
    elif normalized_source == "assistant":
        for block in content_blocks:
            block_type = block.type.strip().lower()
            if block_type == "text":
                text = block.text
                if text.strip():
                    parts.append(
                        (
                            MessageType.ASSISTANT,
                            [ContentBlock(type="text", text=text)],
                            text,
                        )
                    )
            elif block_type == "thinking":
                text = block.text
                if text.strip():
                    parts.append(
                        (
                            MessageType.THINKING,
                            [ContentBlock(type="thinking", text=text)],
                            text,
                        )
                    )
            elif block_type == "tool_use" and block.tool_use is not None:
                tool_text = _tool_use_search_text(block.tool_use)
                parts.append(
                    (
                        MessageType.TOOL_USE,
                        [ContentBlock(type="tool_use", tool_use=block.tool_use)],
                        tool_text,
                    )
                )
            elif block_type == "tool_result":
                text = block.text.strip()
                parts.append(
                    (
                        MessageType.TOOL_RESULT,
                        [ContentBlock(type="tool_result", text=text)],
                        text,
                    )
                )
        if not parts and content_text.strip():
            parts.append(
                (
                    MessageType.ASSISTANT,
                    [ContentBlock(type="text", text=content_text)],
                    content_text,
                )
            )
    else:
        text = content_text.strip() or _first_text(content_blocks)
        parts.append(
            (
                MessageType.SYSTEM,
                [ContentBlock(type="text", text=text)] if text else [],
                text,
            )
        )

    if not parts:
        parts.append((MessageType.SYSTEM, [], ""))

    canonical_base = base_uuid or _fallback_uuid(session_key, sequence_start)
    rows: list[ParsedMessage] = []
    last_uuid = parent_uuid
    for idx, (msg_type, blocks, text) in enumerate(parts):
        msg_uuid = canonical_base if idx == 0 else f"{canonical_base}#{idx + 1}"
        msg_usage = usage if idx == 0 else TokenUsage()
        rows.append(
            ParsedMessage(
                uuid=msg_uuid,
                parent_uuid=last_uuid,
                type=normalize_message_type(msg_type),
                model=model,
                content_blocks=blocks,
                content_text=text,
                usage=msg_usage,
                timestamp=timestamp,
                is_sidechain=is_sidechain,
            )
        )
        last_uuid = msg_uuid
    return rows


def _first_text(content_blocks: list[ContentBlock]) -> str:
    for block in content_blocks:
        if block.text.strip():
            return block.text
    return ""


def _tool_use_search_text(tool_use: ToolUseBlock) -> str:
    name = tool_use.name.strip()
    input_json = tool_use.input_json.strip()
    if name and input_json:
        return f"{name}\n{input_json}"
    return name or input_json


def _parse_claude_content_block(block: dict[str, object]) -> ContentBlock:
    block_type = _as_str(block.get("type")) or "unknown"

    match block_type:
        case "text":
            return ContentBlock(type="text", text=_as_str(block.get("text")))
        case "thinking":
            return ContentBlock(type="thinking", text=_as_str(block.get("thinking")))
        case "tool_use":
            tool_id = _as_str(block.get("id"))
            tool_name = _as_str(block.get("name"))
            tool_input = block.get("input", {})
            input_json = json.dumps(tool_input) if tool_input else "{}"
            return ContentBlock(
                type="tool_use",
                tool_use=ToolUseBlock(tool_use_id=tool_id, name=tool_name, input_json=input_json),
            )
        case "tool_result":
            content = block.get("content", "")
            return ContentBlock(type="tool_result", text=_extract_content_text(content))
        case _:
            return ContentBlock(type=block_type, text=_as_str(block.get("text")))


def _parse_summary_message(
    raw: dict[str, object],
    sequence: int,
    session_key: str,
) -> list[ParsedMessage]:
    summary_text = _as_str(raw.get("summary"))
    return _normalize_parts(
        session_key=session_key,
        sequence_start=sequence,
        base_uuid=_as_str(raw.get("uuid")),
        parent_uuid=None,
        source_type="summary",
        model="",
        content_blocks=[ContentBlock(type="text", text=summary_text)] if summary_text else [],
        content_text=summary_text,
        usage=TokenUsage(),
        timestamp=_as_str(raw.get("timestamp")),
    )


def _parse_system_message(
    raw: dict[str, object],
    sequence: int,
    session_key: str,
) -> list[ParsedMessage]:
    text = _as_str(raw.get("text"))
    return _normalize_parts(
        session_key=session_key,
        sequence_start=sequence,
        base_uuid=_as_str(raw.get("uuid")),
        parent_uuid=None,
        source_type="system",
        model="",
        content_blocks=[ContentBlock(type="text", text=text)] if text else [],
        content_text=text,
        usage=TokenUsage(),
        timestamp=_as_str(raw.get("timestamp")),
    )


def _parse_codex_content(raw_content: object) -> tuple[list[ContentBlock], str]:
    if isinstance(raw_content, str):
        return [ContentBlock(type="text", text=raw_content)], raw_content
    if not isinstance(raw_content, list):
        return [], ""

    blocks: list[ContentBlock] = []
    text_parts: list[str] = []
    for block in raw_content:
        if isinstance(block, str):
            blocks.append(ContentBlock(type="text", text=block))
            text_parts.append(block)
            continue
        if not isinstance(block, dict):
            continue
        text = _as_str(block.get("text"))
        if not text:
            continue
        block_type = _as_str(block.get("type"))
        if block_type in {"input_text", "output_text"}:
            blocks.append(ContentBlock(type="text", text=text))
        else:
            blocks.append(ContentBlock(type=block_type or "text", text=text))
        text_parts.append(text)

    return blocks, "\n".join(text_parts)


def _extract_codex_function_output(value: object) -> str:
    match value:
        case str():
            return value
        case dict():
            output = value.get("output")
            if isinstance(output, str):
                return output
            return json.dumps(value, ensure_ascii=False)
        case _:
            return _as_str(value)


def _extract_codex_reasoning(payload: dict[str, object]) -> str:
    summary = payload.get("summary")
    if isinstance(summary, list):
        parts: list[str] = []
        for block in summary:
            if not isinstance(block, dict):
                continue
            text = _as_str(block.get("text"))
            if text:
                parts.append(text)
        if parts:
            return "\n".join(parts)
    return _as_str(payload.get("content"))


def _extract_gemini_content_text(content: object) -> str:
    match content:
        case str():
            return content
        case dict():
            return _as_str(content.get("text"))
        case list():
            parts: list[str] = []
            for block in content:
                match block:
                    case str():
                        parts.append(block)
                    case dict():
                        text = _as_str(block.get("text"))
                        if text:
                            parts.append(text)
            return "\n".join(parts)
        case _:
            return ""


def _extract_gemini_thoughts(thoughts: object) -> str:
    match thoughts:
        case str():
            return thoughts
        case list():
            return "\n".join(item for item in thoughts if isinstance(item, str))
        case _:
            return ""


def _parse_gemini_usage(tokens: object) -> TokenUsage:
    match tokens:
        case dict():
            return TokenUsage(
                input_tokens=_int(tokens.get("input", 0)),
                output_tokens=_int(tokens.get("output", 0)),
                cache_read_tokens=_int(tokens.get("cached", 0)),
                cache_creation_tokens=0,
            )
        case _:
            return TokenUsage()


def _extract_content_text(content: object) -> str:
    match content:
        case str():
            return content
        case list():
            parts: list[str] = []
            for item in content:
                match item:
                    case dict() if item.get("type") == "text":
                        parts.append(_as_str(item.get("text")))
                    case str():
                        parts.append(item)
            return "\n".join(parts)
        case _:
            return _as_str(content)


def _safe_json_string(value: object) -> str:
    match value:
        case str():
            stripped = value.strip()
            return stripped or "{}"
        case None:
            return "{}"
        case _:
            try:
                return json.dumps(value, ensure_ascii=False)
            except TypeError:
                return "{}"


def _fallback_uuid(session_key: str, seq: int) -> str:
    return f"{session_key}:msg:{seq}"


def _fallback_tool_id(session_key: str, seq: int) -> str:
    return f"{session_key}:tool:{seq}"


def _as_str(value: object) -> str:
    match value:
        case str():
            return value
        case _:
            return ""


def _as_optional_str(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _int(val: object) -> int:
    match val:
        case bool():
            return int(val)
        case int():
            return val
        case float():
            return int(val)
        case str():
            try:
                return int(float(val))
            except ValueError:
                return 0
        case _:
            return 0
