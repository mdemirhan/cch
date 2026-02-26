"""Protocol module smoke test."""

from __future__ import annotations

from cch.services import protocols


def test_protocols_module_imports() -> None:
    assert hasattr(protocols, "SessionServiceProtocol")
    assert hasattr(protocols, "ProjectServiceProtocol")
    assert hasattr(protocols, "AnalyticsServiceProtocol")
    assert hasattr(protocols, "SearchServiceProtocol")
