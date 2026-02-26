"""Tests for discovery module."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from cch.config import Config
from cch.data.discovery import (
    _build_gemini_project_hash_map,
    _decode_project_id,
    _load_sessions_index,
    _project_name_from_path,
    _provider_project_id,
    _provider_session_id,
    _read_text,
    _safe_load_json,
    _scan_codex_metadata,
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
        assert all(p.project_id.startswith(f"{p.provider}:") for p in projects)
        assert any(p.project_path == "/Users/test/myproject" for p in projects)

    def test_missing_dir(self, tmp_path: Path) -> None:
        config = Config(
            claude_dir=tmp_path / "nonexistent",
            codex_dir=tmp_path / "nonexistent_codex",
            gemini_dir=tmp_path / "nonexistent_gemini",
        )
        projects = discover_projects(config)
        assert projects == []


class TestDiscoverSessions:
    def test_discovers_sessions(self, test_config: Config) -> None:
        sessions = discover_sessions(test_config)
        assert len(sessions) >= 1
        session = sessions[0]
        assert session.session_id == "test-session-001"
        assert session.provider == "claude"
        assert session.file_path.exists()
        assert session.mtime_ms > 0
        assert session.file_size > 0

    def test_enriches_from_index(self, test_config: Config) -> None:
        sessions = discover_sessions(test_config)
        session = sessions[0]
        assert session.first_prompt == "Hello, can you help me fix a bug in my Python code?"
        assert session.summary == "Fixed Python add function bug"


class TestDiscoveryHelpers:
    def test_provider_project_id(self) -> None:
        claude_expected = hashlib.sha1(b"claude:/Users/a/demo").hexdigest()[:16]
        codex_expected = hashlib.sha1(b"codex:/Users/a/demo").hexdigest()[:16]
        gemini_expected = hashlib.sha1(b"gemini:x").hexdigest()[:16]
        assert _provider_project_id("claude", "/Users/a/demo") == f"claude:{claude_expected}"
        assert _provider_project_id("codex", "/Users/a/demo") == f"codex:{codex_expected}"
        assert _provider_project_id("gemini", "", fallback="x") == f"gemini:{gemini_expected}"

    def test_provider_session_id(self, tmp_path: Path) -> None:
        assert _provider_session_id("claude", "abc") == "abc"
        assert _provider_session_id("codex", "abc", file_path=None) == "codex:abc"
        path = tmp_path / "s.jsonl"
        path.write_text("{}", encoding="utf-8")
        expected_suffix = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:8]
        assert _provider_session_id("codex", "abc", file_path=path) == f"codex:abc:{expected_suffix}"

    def test_scan_codex_metadata(self, provider_data_root: Path) -> None:
        codex_path = (
            provider_data_root
            / "codex"
            / "sessions"
            / "2026"
            / "02"
            / "20"
            / "codex-session-redacted-001.jsonl"
        )
        meta = _scan_codex_metadata(codex_path)
        assert meta.source_session_id == "codex-session-redacted-001"
        assert meta.project_path == "/Users/redacted/workspace/demo-codex"
        assert meta.git_branch == "feature/testing"
        assert meta.created == "2026-02-20T11:00:00.000Z"
        assert meta.modified == "2026-02-20T11:00:00.000Z"

    def test_scan_codex_metadata_handles_io_error(self) -> None:
        with patch("builtins.open", side_effect=OSError("boom")):
            meta = _scan_codex_metadata(Path("/tmp/none.jsonl"))
        assert meta.source_session_id == ""
        assert meta.project_path == ""

    def test_load_sessions_index_missing_or_bad(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        assert _load_sessions_index(project_dir) == {}

        (project_dir / "sessions-index.json").write_text("{bad-json", encoding="utf-8")
        assert _load_sessions_index(project_dir) == {}

        payload = {"entries": [{"sessionId": "a", "summary": "ok"}, {"oops": 1}]}
        (project_dir / "sessions-index.json").write_text(json.dumps(payload), encoding="utf-8")
        index = _load_sessions_index(project_dir)
        assert index["a"]["summary"] == "ok"

    def test_build_gemini_project_hash_map(self, provider_test_config: Config) -> None:
        result = _build_gemini_project_hash_map(provider_test_config)
        path = "/Users/redacted/workspace/demo-gemini"
        digest = hashlib.sha256(path.encode("utf-8")).hexdigest()
        assert result[digest] == path

    def test_safe_load_json_and_read_text(self, tmp_path: Path) -> None:
        file = tmp_path / "data.json"
        file.write_text('{"a": 1}', encoding="utf-8")
        assert _safe_load_json(file) == {"a": 1}

        bad = tmp_path / "bad.json"
        bad.write_text("{bad", encoding="utf-8")
        assert _safe_load_json(bad) is None
        assert _safe_load_json(tmp_path / "missing.json") is None

        text = tmp_path / "x.txt"
        text.write_text("hello", encoding="utf-8")
        assert _read_text(text) == "hello"
        assert _read_text(tmp_path / "nope.txt") == ""
