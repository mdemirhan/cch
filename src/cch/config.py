"""Configuration for CCH."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Application configuration."""

    claude_dir: Path = field(default_factory=lambda: Path.home() / ".claude")
    codex_dir: Path = field(default_factory=lambda: Path.home() / ".codex")
    gemini_dir: Path = field(default_factory=lambda: Path.home() / ".gemini")
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "cch")

    @property
    def projects_dir(self) -> Path:
        return self.claude_dir / "projects"

    @property
    def codex_sessions_dir(self) -> Path:
        return self.codex_dir / "sessions"

    @property
    def gemini_tmp_dir(self) -> Path:
        return self.gemini_dir / "tmp"

    @property
    def db_path(self) -> Path:
        return self.cache_dir / "index.db"
