"""Shared message category definitions and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntFlag
from typing import Any


class MessageCategory(IntFlag):
    """Bitmask categories used across indexing, search and UI filters."""

    USER = 1
    ASSISTANT = 2
    TOOL_CALL = 4
    THINKING = 8
    TOOL_RESULT = 16
    SYSTEM = 32


@dataclass(frozen=True)
class CategoryFilter:
    """Display metadata for one filter chip/category."""

    key: str
    label: str
    color: str
    mask: MessageCategory


CATEGORY_FILTERS: tuple[CategoryFilter, ...] = (
    CategoryFilter("user", "User", "#E67E22", MessageCategory.USER),
    CategoryFilter("assistant", "Assistant", "#27AE60", MessageCategory.ASSISTANT),
    CategoryFilter("tool_call", "Tool Calls", "#8E44AD", MessageCategory.TOOL_CALL),
    CategoryFilter("thinking", "Thinking", "#9B59B6", MessageCategory.THINKING),
    CategoryFilter("tool_result", "Results", "#999999", MessageCategory.TOOL_RESULT),
    CategoryFilter("system", "System", "#F39C12", MessageCategory.SYSTEM),
)
ALL_CATEGORY_KEYS: tuple[str, ...] = tuple(item.key for item in CATEGORY_FILTERS)
DEFAULT_ACTIVE_CATEGORY_KEYS: tuple[str, ...] = ("user", "assistant")
MASK_BY_KEY: dict[str, int] = {item.key: int(item.mask) for item in CATEGORY_FILTERS}


def normalize_category_keys(keys: list[str] | tuple[str, ...] | set[str] | None) -> list[str]:
    """Return category keys in canonical order, filtered to known values."""
    if keys is None:
        return list(ALL_CATEGORY_KEYS)
    selected = {key for key in keys if key in MASK_BY_KEY}
    return [key for key in ALL_CATEGORY_KEYS if key in selected]


def category_mask_for_keys(keys: list[str] | tuple[str, ...] | set[str] | None) -> int:
    """Return a bitmask OR of category keys."""
    if keys is None:
        keys = ALL_CATEGORY_KEYS
    mask = 0
    for key in keys:
        mask |= MASK_BY_KEY.get(key, 0)
    return mask


def category_keys_from_mask(mask: int) -> list[str]:
    """Decode mask into canonical category keys."""
    return [key for key in ALL_CATEGORY_KEYS if mask & MASK_BY_KEY[key]]


def category_mask_for_message(
    *,
    msg_type: str,
    role: str,
    content_blocks: list[Any],
    content_text: str,
    has_tool_calls: bool = False,
) -> int:
    """Classify message content into a category bitmask."""
    normalized_type = msg_type.strip().lower()
    normalized_role = role.strip().lower()
    if normalized_type in {"summary", "system"}:
        return int(MessageCategory.SYSTEM)

    mask = 0
    has_text_block = False
    has_tool_result = False

    for block in content_blocks:
        block_type = _block_type(block)
        block_text = _block_text(block)
        if block_type == "text" and block_text.strip():
            has_text_block = True
            if normalized_role == "assistant":
                mask |= int(MessageCategory.ASSISTANT)
        elif block_type == "thinking" and block_text.strip():
            mask |= int(MessageCategory.THINKING)
        elif block_type == "tool_use":
            mask |= int(MessageCategory.TOOL_CALL)
        elif block_type == "tool_result":
            has_tool_result = True
            mask |= int(MessageCategory.TOOL_RESULT)

    if normalized_role == "user" and normalized_type == "user":
        if has_text_block and content_text.strip():
            mask |= int(MessageCategory.USER)
        if has_tool_result:
            mask |= int(MessageCategory.TOOL_RESULT)

    if has_tool_calls:
        mask |= int(MessageCategory.TOOL_CALL)

    # Ensure messages are never uncategorizable, so counts/visibility stay consistent.
    if mask == 0:
        if normalized_role == "assistant":
            mask |= int(MessageCategory.ASSISTANT)
        elif normalized_role == "user":
            mask |= int(MessageCategory.USER)
        else:
            mask |= int(MessageCategory.SYSTEM)

    return mask


def _block_type(block: Any) -> str:
    if isinstance(block, dict):
        value = block.get("type", "")
        return value.strip().lower() if isinstance(value, str) else ""
    value = getattr(block, "type", "")
    return value.strip().lower() if isinstance(value, str) else ""


def _block_text(block: Any) -> str:
    if isinstance(block, dict):
        value = block.get("text", "")
        return value if isinstance(value, str) else ""
    value = getattr(block, "text", "")
    return value if isinstance(value, str) else ""
