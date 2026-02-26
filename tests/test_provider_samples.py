"""Anonymized provider fixture tests (Claude/Codex/Gemini)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cch.config import Config
from cch.data.db import Database
from cch.data.discovery import discover_projects, discover_sessions
from cch.data.indexer import Indexer
from cch.data.parser import parse_session_file


def _provider_session_paths(root: Path) -> tuple[Path, Path, Path]:
    claude_path = (
        root
        / "claude"
        / "projects"
        / "-Users-redacted-workspace-demo-claude"
        / "claude-session-redacted-001.jsonl"
    )
    codex_path = (
        root / "codex" / "sessions" / "2026" / "02" / "20" / "codex-session-redacted-001.jsonl"
    )
    gemini_path = (
        root
        / "gemini"
        / "tmp"
        / "2f5846f17316d9a788d405036ac5f4a3f6c4bd93311ce0982dab34ed9152a416"
        / "sessions"
        / "session-redacted-001"
        / "session-0001.json"
    )
    return claude_path, codex_path, gemini_path


def test_provider_fixture_files_parse(provider_data_root: Path) -> None:
    claude_path, codex_path, gemini_path = _provider_session_paths(provider_data_root)

    claude_messages = list(parse_session_file(claude_path, provider="claude"))
    assert {m.type for m in claude_messages} >= {
        "user",
        "assistant",
        "thinking",
        "tool_use",
        "tool_result",
        "system",
    }

    codex_messages = list(
        parse_session_file(codex_path, provider="codex", session_id="codex:fixture")
    )
    assert {m.type for m in codex_messages} >= {
        "user",
        "assistant",
        "thinking",
        "tool_use",
        "tool_result",
    }

    gemini_messages = list(
        parse_session_file(gemini_path, provider="gemini", session_id="gemini:fixture")
    )
    assert {m.type for m in gemini_messages} >= {"user", "assistant", "thinking", "system"}


def test_discovery_reads_all_provider_fixture_trees(provider_test_config: Config) -> None:
    sessions = discover_sessions(provider_test_config)
    assert len(sessions) == 3

    providers = {session.provider for session in sessions}
    assert providers == {"claude", "codex", "gemini"}

    session_ids = {session.session_id for session in sessions}
    assert "claude-session-redacted-001" in session_ids
    assert any(sid.startswith("codex:codex-session-redacted-001:") for sid in session_ids)
    assert any(sid.startswith("gemini:gemini-session-redacted-001:") for sid in session_ids)

    projects = discover_projects(provider_test_config)
    assert len(projects) == 3
    assert {project.provider for project in projects} == {"claude", "codex", "gemini"}


@pytest.mark.asyncio
async def test_indexer_indexes_all_provider_fixtures(
    in_memory_db: Database,
    provider_test_config: Config,
) -> None:
    indexer = Indexer(in_memory_db, provider_test_config)
    result = await indexer.index_all(force=True)
    assert result.files_indexed == 3

    provider_rows = await in_memory_db.fetch_all(
        """SELECT provider, COUNT(*) as cnt
           FROM sessions
           GROUP BY provider
           ORDER BY provider"""
    )
    counts = {str(row["provider"]): int(row["cnt"]) for row in provider_rows}
    assert counts == {"claude": 1, "codex": 1, "gemini": 1}
