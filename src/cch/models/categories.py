"""Shared canonical message category definitions and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MessageType(StrEnum):
    """Canonical message types used throughout the application."""

    USER = "user"
    ASSISTANT = "assistant"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"
    SYSTEM = "system"


@dataclass(frozen=True)
class CategoryFilter:
    """Display metadata for one filter chip/category."""

    key: str
    label: str
    color: str


CATEGORY_FILTERS: tuple[CategoryFilter, ...] = (
    CategoryFilter(MessageType.USER, "User", "#E67E22"),
    CategoryFilter(MessageType.ASSISTANT, "Assistant", "#27AE60"),
    CategoryFilter(MessageType.TOOL_USE, "Tool Use", "#8E44AD"),
    CategoryFilter(MessageType.THINKING, "Thinking", "#9B59B6"),
    CategoryFilter(MessageType.TOOL_RESULT, "Results", "#999999"),
    CategoryFilter(MessageType.SYSTEM, "System", "#F39C12"),
)
ALL_CATEGORY_KEYS: tuple[str, ...] = tuple(item.key for item in CATEGORY_FILTERS)
DEFAULT_ACTIVE_CATEGORY_KEYS: tuple[str, ...] = (MessageType.USER, MessageType.ASSISTANT)
_ALIAS_BY_KEY: dict[str, str] = {
    "tool_call": MessageType.TOOL_USE,
}
LABEL_BY_KEY: dict[str, str] = {item.key: item.label for item in CATEGORY_FILTERS}
COLOR_BY_KEY: dict[str, str] = {item.key: item.color for item in CATEGORY_FILTERS}


def normalize_category_keys(keys: list[str] | tuple[str, ...] | set[str] | None) -> list[str]:
    """Return category keys in canonical order, filtered to known values.

    Legacy aliases are mapped to canonical keys.
    """
    if keys is None:
        return list(ALL_CATEGORY_KEYS)
    selected: set[str] = set()
    for key in keys:
        mapped = _ALIAS_BY_KEY.get(key, key)
        if mapped in LABEL_BY_KEY:
            selected.add(mapped)
    return [key for key in ALL_CATEGORY_KEYS if key in selected]


def normalize_message_type(raw_type: str) -> MessageType:
    """Normalize any raw/legacy message type into a canonical category key."""
    normalized = raw_type.strip().lower()
    mapped = _ALIAS_BY_KEY.get(normalized, normalized)
    if mapped in LABEL_BY_KEY:
        return MessageType(mapped)
    return MessageType.SYSTEM
