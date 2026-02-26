"""Protocol definitions for data access."""

from __future__ import annotations

from typing import Any, Protocol


class DatabaseProtocol(Protocol):
    """Async database interface."""

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any: ...

    async def execute_many(self, sql: str, params_seq: list[tuple[Any, ...]]) -> None: ...

    async def fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[Any]: ...

    async def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> Any | None: ...


class IndexerProtocol(Protocol):
    """Interface for session indexer."""

    async def index_all(
        self,
        progress_callback: ProgressCallback | None = None,
        force: bool = False,
    ) -> IndexResult: ...

    async def needs_reindex(self, file_path: str, mtime_ms: int, size: int) -> bool: ...


class ProgressCallback(Protocol):
    """Callback for indexing progress updates."""

    def __call__(self, current: int, total: int, message: str) -> None: ...


class IndexResult:
    """Result of an indexing operation."""

    def __init__(
        self,
        files_indexed: int = 0,
        files_skipped: int = 0,
        files_failed: int = 0,
        total_messages: int = 0,
    ):
        self.files_indexed = files_indexed
        self.files_skipped = files_skipped
        self.files_failed = files_failed
        self.total_messages = total_messages

    def __repr__(self) -> str:
        return (
            f"IndexResult(indexed={self.files_indexed}, skipped={self.files_skipped}, "
            f"failed={self.files_failed}, messages={self.total_messages})"
        )
