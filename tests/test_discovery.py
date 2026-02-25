"""Tests for discovery module."""

from __future__ import annotations

from pathlib import Path

from cch.config import Config
from cch.data.discovery import (
    _decode_project_id,
    _project_name_from_path,
    discover_projects,
    discover_sessions,
)


class TestDecodeProjectId:
    def test_basic_path(self) -> None:
        assert _decode_project_id("-Users-foo-src-myproject") == "/Users/foo/src/myproject"

    def test_empty(self) -> None:
        assert _decode_project_id("") == ""

    def test_single_segment(self) -> None:
        result = _decode_project_id("-home")
        assert result == "/home"


class TestProjectNameFromPath:
    def test_basic(self) -> None:
        assert _project_name_from_path("/Users/foo/src/myproject") == "myproject"

    def test_empty(self) -> None:
        assert _project_name_from_path("") == "Unknown"

    def test_trailing_slash(self) -> None:
        assert _project_name_from_path("/foo/bar/") == "bar"


class TestDiscoverProjects:
    def test_discovers_projects(self, test_config: Config) -> None:
        projects = discover_projects(test_config)
        assert len(projects) >= 1
        assert any(p.project_id == "-tmp-test-project" for p in projects)

    def test_missing_dir(self, tmp_path: Path) -> None:
        config = Config(claude_dir=tmp_path / "nonexistent")
        projects = discover_projects(config)
        assert projects == []


class TestDiscoverSessions:
    def test_discovers_sessions(self, test_config: Config) -> None:
        sessions = discover_sessions(test_config)
        assert len(sessions) >= 1
        session = sessions[0]
        assert session.session_id == "test-session-001"
        assert session.file_path.exists()
        assert session.mtime_ms > 0
        assert session.file_size > 0

    def test_enriches_from_index(self, test_config: Config) -> None:
        sessions = discover_sessions(test_config)
        session = sessions[0]
        assert session.first_prompt == "Hello, can you help me fix a bug in my Python code?"
        assert session.summary == "Fixed Python add function bug"
