"""Schema/version and category behavior tests."""

from __future__ import annotations

import pytest
from result import Ok

from cch.data.db import SCHEMA_VERSION, Database
from cch.models.categories import (
    ALL_CATEGORY_KEYS,
    normalize_category_keys,
    normalize_message_type,
)
from cch.models.sessions import MessageView
from cch.services.session_service import SessionService
from cch.ui.widgets.message_widget import render_message_html


@pytest.mark.asyncio
async def test_db_rebuilds_when_schema_version_changes(tmp_path) -> None:
    db_path = tmp_path / "schema-reset.db"
    async with Database(db_path) as db:
        await db.execute(
            """INSERT INTO projects
               (project_id, provider, project_path, project_name, session_count)
               VALUES (?, ?, ?, ?, 0)""",
            ("p1", "claude", "/tmp/p1", "p1"),
        )
        await db.execute(
            "INSERT OR REPLACE INTO app_meta (key, value) VALUES ('schema_version', '1')"
        )
        await db.commit()

    async with Database(db_path) as db:
        version = await db.fetch_one("SELECT value FROM app_meta WHERE key = 'schema_version'")
        projects = await db.fetch_one("SELECT COUNT(*) as cnt FROM projects")
        assert version is not None and int(version["value"]) == SCHEMA_VERSION
        assert projects is not None and int(projects["cnt"]) == 0
        assert db.requires_full_reindex is True


def test_category_key_normalization() -> None:
    normalized = normalize_category_keys(["assistant", "invalid", "user", "tool_call"])
    assert normalized == ["user", "assistant", "tool_use"]
    assert normalize_category_keys(None) == list(ALL_CATEGORY_KEYS)
    assert normalize_message_type("tool_call") == "tool_use"
    assert normalize_message_type("unknown-value") == "system"


def test_unknown_message_is_rendered_as_placeholder() -> None:
    msg = MessageView(
        uuid="msg-1",
        type="assistant",
        content_text="",
        content_json="[]",
        timestamp="2026-01-01T00:00:00Z",
    )
    html = render_message_html(msg)
    assert "unsupported or empty message" in html


@pytest.mark.asyncio
async def test_session_detail_default_limit_window(in_memory_db: Database) -> None:
    session_id = "s-large"
    await in_memory_db.execute(
        """INSERT INTO projects
           (project_id, provider, project_path, project_name, session_count)
           VALUES (?, ?, ?, ?, 1)""",
        ("p-large", "claude", "/tmp/large", "large"),
    )
    await in_memory_db.execute(
        """INSERT INTO sessions
           (session_id, project_id, provider, file_path, first_prompt, summary,
            message_count, user_message_count, assistant_message_count, tool_call_count,
            total_input_tokens, total_output_tokens, total_cache_read_tokens,
            total_cache_creation_tokens, model, models_used, git_branch, cwd,
            created_at, modified_at, duration_ms, is_sidechain)
           VALUES (?, ?, ?, ?, '', '', ?, 0, ?, 0, 0, 0, 0, 0, '', '', '', '',
                   '2026-01-01T00:00:00Z', '2026-01-01T00:00:01Z', 0, 0)""",
        (session_id, "p-large", "claude", "/tmp/large/session.jsonl", 1500, 1500),
    )
    message_rows = [
        (
            session_id,
            f"m-{idx}",
            None,
            "assistant",
            "model-x",
            f"text-{idx}",
            '[{"type":"text","text":"text"}]',
            0,
            0,
            0,
            0,
            f"2026-01-01T00:00:{idx % 60:02d}Z",
            0,
            idx,
        )
        for idx in range(1500)
    ]
    await in_memory_db.execute_many(
        """INSERT INTO messages
           (session_id, uuid, parent_uuid, type, model,
            content_text, content_json,
            input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens,
            timestamp, is_sidechain, sequence_num)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        message_rows,
    )
    await in_memory_db.commit()

    svc = SessionService(in_memory_db)
    result = await svc.get_session_detail(session_id)
    assert isinstance(result, Ok)
    assert result.ok_value.message_count == 1500
    assert len(result.ok_value.messages) == 1000
