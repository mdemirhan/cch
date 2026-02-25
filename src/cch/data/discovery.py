"""Enumerate Claude Code projects and session files."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from cch.config import Config

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredSession:
    """A discovered session file with metadata from sessions-index.json."""

    session_id: str
    file_path: Path
    project_id: str
    project_path: str
    project_name: str
    mtime_ms: int
    file_size: int
    first_prompt: str = ""
    summary: str = ""
    message_count: int = 0
    created: str = ""
    modified: str = ""
    git_branch: str = ""
    is_sidechain: bool = False


@dataclass
class DiscoveredProject:
    """A discovered project directory."""

    project_id: str
    project_path: str
    project_name: str
    dir_path: Path
    session_count: int = 0


def _decode_project_id(project_id: str) -> str:
    """Decode a project ID like '-Users-foo-src-myproject' into '/Users/foo/src/myproject'."""
    if not project_id:
        return ""
    return project_id.replace("-", "/", 1).replace("-", "/")


def _project_name_from_path(project_path: str) -> str:
    """Extract a human-readable project name from a project path."""
    if not project_path:
        return "Unknown"
    parts = project_path.rstrip("/").split("/")
    return parts[-1] if parts else "Unknown"


def discover_projects(config: Config) -> list[DiscoveredProject]:
    """Enumerate all project directories under ~/.claude/projects/."""
    projects_dir = config.projects_dir
    if not projects_dir.is_dir():
        logger.warning("Projects directory not found: %s", projects_dir)
        return []

    projects: list[DiscoveredProject] = []
    for entry in sorted(projects_dir.iterdir()):
        if not entry.is_dir():
            continue
        project_id = entry.name
        project_path = _decode_project_id(project_id)
        project_name = _project_name_from_path(project_path)

        # Count JSONL session files
        jsonl_files = list(entry.glob("*.jsonl"))
        session_count = len(jsonl_files)

        projects.append(
            DiscoveredProject(
                project_id=project_id,
                project_path=project_path,
                project_name=project_name,
                dir_path=entry,
                session_count=session_count,
            )
        )

    return projects


def discover_sessions(config: Config) -> list[DiscoveredSession]:
    """Enumerate all session files, enriching with sessions-index.json metadata."""
    projects = discover_projects(config)
    sessions: list[DiscoveredSession] = []

    for project in projects:
        # Try to load sessions-index.json for metadata
        index_data = _load_sessions_index(project.dir_path)

        for jsonl_path in sorted(project.dir_path.glob("*.jsonl")):
            session_id = jsonl_path.stem
            stat = jsonl_path.stat()

            # Look up metadata from index
            entry = index_data.get(session_id, {})

            sessions.append(
                DiscoveredSession(
                    session_id=session_id,
                    file_path=jsonl_path,
                    project_id=project.project_id,
                    project_path=project.project_path,
                    project_name=project.project_name,
                    mtime_ms=int(stat.st_mtime * 1000),
                    file_size=stat.st_size,
                    first_prompt=str(entry.get("firstPrompt", "")),
                    summary=str(entry.get("summary", "")),
                    message_count=int(entry.get("messageCount", 0)),  # type: ignore[arg-type]
                    created=str(entry.get("created", "")),
                    modified=str(entry.get("modified", "")),
                    git_branch=str(entry.get("gitBranch", "")),
                    is_sidechain=bool(entry.get("isSidechain", False)),
                )
            )

    return sessions


def _load_sessions_index(project_dir: Path) -> dict[str, dict[str, object]]:
    """Load sessions-index.json and return a dict keyed by session ID."""
    index_path = project_dir / "sessions-index.json"
    if not index_path.is_file():
        return {}
    try:
        with open(index_path) as f:
            data = json.load(f)
        entries = data.get("entries", [])
        return {e["sessionId"]: e for e in entries if "sessionId" in e}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load sessions index %s: %s", index_path, exc)
        return {}
