"""Tests for MessageWebView filter-state normalization."""

from __future__ import annotations

from cch.ui.widgets.message_webview import (
    _can_use_inline_content,
    _encode_document,
    _normalize_filters,
)


def test_normalize_filters_from_json_string() -> None:
    assert _normalize_filters('["assistant","user","tool_call"]') == [
        "user",
        "assistant",
        "tool_use",
    ]


def test_normalize_filters_from_python_list() -> None:
    assert _normalize_filters(["thinking", "system", "invalid"]) == [
        "thinking",
        "system",
    ]


def test_normalize_filters_no_state_marker() -> None:
    assert _normalize_filters("__CCH_NO_STATE__") is None


def test_normalize_filters_bad_payload() -> None:
    assert _normalize_filters("{bad-json") is None
    assert _normalize_filters({"user"}) == ["user"]


def test_encode_document_replaces_invalid_surrogate() -> None:
    raw = "hello\ud800world"
    encoded = _encode_document(raw)
    assert encoded.decode("utf-8") == "hello?world"


def test_can_use_inline_content_rejects_large_encoded_data_url() -> None:
    # "<" expands to "%3C" in data URLs, making encoded URL much larger than raw bytes.
    content = ("<" * 700_000).encode("utf-8")
    assert _can_use_inline_content(content) is False
