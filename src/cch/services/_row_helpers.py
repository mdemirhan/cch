"""Shared row-to-model conversion helpers for service modules."""

from __future__ import annotations


def row_str(row: dict[str, object], key: str, default: str = "") -> str:
    """Extract a string value from a database row dict."""
    v = row.get(key, default)
    return str(v) if v else default


def row_int(row: dict[str, object], key: str) -> int:
    """Extract an integer value from a database row dict."""
    v = row.get(key, 0)
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str):
        try:
            return int(v)
        except ValueError:
            return 0
    return 0
