"""Indexing result models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class IndexResult:
    """Result summary for an indexing run."""

    files_indexed: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    total_messages: int = 0
