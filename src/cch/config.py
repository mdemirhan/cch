"""Configuration for CCH."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Application configuration."""

    claude_dir: Path = field(default_factory=lambda: Path.home() / ".claude")
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "cch")
    port: int = 8765
    host: str = "127.0.0.1"

    @property
    def projects_dir(self) -> Path:
        return self.claude_dir / "projects"

    @property
    def db_path(self) -> Path:
        return self.cache_dir / "index.db"

    @property
    def stats_cache_path(self) -> Path:
        return self.claude_dir / "stats-cache.json"
