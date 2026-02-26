"""Shared fixtures for CCH tests."""

from __future__ import annotations

import json
import shutil
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest

from cch.config import Config
from cch.data.db import Database

SAMPLE_SESSION_PATH = Path(__file__).parent / "data" / "sample_session.jsonl"
SAMPLE_INDEX_PATH = Path(__file__).parent / "data" / "sample_sessions_index.json"
PROVIDER_DATA_ROOT = Path(__file__).parent / "data" / "providers"


@pytest.fixture
def sample_session_path() -> Path:
    """Path to the sample session JSONL file."""
    return SAMPLE_SESSION_PATH


@pytest.fixture
def tmp_claude_dir(tmp_path: Path) -> Path:
    """Create a temporary Claude directory with sample data."""
    claude_dir = tmp_path / ".claude"
    projects_dir = claude_dir / "projects" / "-tmp-test-project"
    projects_dir.mkdir(parents=True)

    # Copy sample session
    session_file = projects_dir / "test-session-001.jsonl"
    shutil.copy(SAMPLE_SESSION_PATH, session_file)

    # Create sessions-index.json
    index_data = json.loads(SAMPLE_INDEX_PATH.read_text())
    # Update paths to point to the temp dir
    for entry in index_data["entries"]:
        entry["fullPath"] = str(session_file)
    (projects_dir / "sessions-index.json").write_text(json.dumps(index_data))

    return claude_dir


@pytest.fixture
def test_config(tmp_claude_dir: Path, tmp_path: Path) -> Config:
    """Config pointing at temporary test data."""
    return Config(
        claude_dir=tmp_claude_dir,
        codex_dir=tmp_path / ".codex",
        gemini_dir=tmp_path / ".gemini",
        cache_dir=tmp_path / "cache",
    )


@pytest.fixture
async def test_db(tmp_path: Path) -> AsyncGenerator[Database]:
    """A fresh in-memory-like test database."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    await db.__aenter__()
    yield db  # type: ignore[misc]
    await db.__aexit__(None, None, None)


@pytest.fixture
async def in_memory_db() -> AsyncGenerator[Database]:
    """SQLite in-memory database for fast unit/integration tests."""
    db = Database(Path(":memory:"))
    await db.__aenter__()
    yield db  # type: ignore[misc]
    await db.__aexit__(None, None, None)


@pytest.fixture
def provider_data_root() -> Path:
    """Root path for anonymized provider fixture files."""
    return PROVIDER_DATA_ROOT


@pytest.fixture
def provider_test_config(tmp_path: Path, provider_data_root: Path) -> Config:
    """Config pointing to anonymized Claude/Codex/Gemini fixture trees."""
    claude_dir = tmp_path / ".claude"
    codex_dir = tmp_path / ".codex"
    gemini_dir = tmp_path / ".gemini"
    shutil.copytree(provider_data_root / "claude", claude_dir)
    shutil.copytree(provider_data_root / "codex", codex_dir)
    shutil.copytree(provider_data_root / "gemini", gemini_dir)
    return Config(
        claude_dir=claude_dir,
        codex_dir=codex_dir,
        gemini_dir=gemini_dir,
        cache_dir=tmp_path / "cache",
    )
