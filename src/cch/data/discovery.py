"""Discover Claude/Codex/Gemini sessions and project metadata."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from cch.config import Config

logger = logging.getLogger(__name__)

_CLAUDE = "claude"
_CODEX = "codex"
_GEMINI = "gemini"


@dataclass
class DiscoveredSession:
    """A discovered session file with basic metadata for indexing."""

    session_id: str
    source_session_id: str
    provider: str
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
    """A discovered project directory or provider/project grouping."""

    project_id: str
    provider: str
    project_path: str
    project_name: str
    dir_path: Path | None
    session_count: int = 0
    session_files: tuple[Path, ...] = ()


@dataclass
class _CodexMeta:
    source_session_id: str = ""
    project_path: str = ""
    created: str = ""
    modified: str = ""
    git_branch: str = ""
    first_prompt: str = ""
    message_count: int = 0


def _decode_project_id(project_id: str) -> str:
    """Decode a Claude project ID '-Users-foo-src-myproject' -> '/Users/foo/src/myproject'."""
    if not project_id:
        return ""
    return project_id.replace("-", "/", 1).replace("-", "/")


def _encode_project_path(project_path: str) -> str:
    """Encode '/Users/foo/src/myproject' -> '-Users-foo-src-myproject'."""
    normalized = project_path.strip().rstrip("/")
    if not normalized:
        return ""
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    return normalized.replace("/", "-")


def _project_name_from_path(project_path: str) -> str:
    """Extract a human-readable project name from a project path."""
    if not project_path:
        return "Unknown"
    parts = project_path.rstrip("/").split("/")
    return parts[-1] if parts else "Unknown"


def _provider_project_id(provider: str, project_path: str, fallback: str = "unknown") -> str:
    """Build a provider-scoped project ID."""
    if provider == _CLAUDE:
        encoded = _encode_project_path(project_path)
        return encoded or fallback
    encoded = _encode_project_path(project_path)
    if encoded:
        return f"{provider}:{encoded}"
    return f"{provider}:{fallback}"


def _provider_session_id(
    provider: str,
    source_session_id: str,
    *,
    file_path: Path | None = None,
) -> str:
    """Build a provider-scoped session ID."""
    if provider == _CLAUDE:
        return source_session_id
    if file_path is None:
        return f"{provider}:{source_session_id}"
    # Some providers may duplicate session IDs across copied temp folders.
    suffix = hashlib.sha1(str(file_path).encode("utf-8")).hexdigest()[:8]
    return f"{provider}:{source_session_id}:{suffix}"


def discover_projects(config: Config) -> list[DiscoveredProject]:
    """Discover provider-aware projects from discovered sessions."""
    sessions = discover_sessions(config)
    by_id: dict[str, DiscoveredProject] = {}

    for session in sessions:
        project = by_id.get(session.project_id)
        if project is None:
            by_id[session.project_id] = DiscoveredProject(
                project_id=session.project_id,
                provider=session.provider,
                project_path=session.project_path,
                project_name=session.project_name,
                dir_path=session.file_path.parent,
                session_count=1,
                session_files=(session.file_path,),
            )
            continue

        project.session_count += 1
        project.session_files = (*project.session_files, session.file_path)
        if project.dir_path is None:
            project.dir_path = session.file_path.parent

    projects = list(by_id.values())
    projects.sort(key=lambda p: (p.provider, p.project_name.lower(), p.project_id))
    return projects


def discover_sessions(
    config: Config,
    projects: list[DiscoveredProject] | None = None,  # kept for backward compatibility
) -> list[DiscoveredSession]:
    """Discover all session files from Claude, Codex and Gemini stores."""
    del projects  # no longer needed now that discovery is provider-native

    sessions: list[DiscoveredSession] = []
    sessions.extend(_discover_claude_sessions(config))
    sessions.extend(_discover_codex_sessions(config))
    sessions.extend(_discover_gemini_sessions(config))

    sessions.sort(key=lambda s: s.mtime_ms, reverse=True)
    return sessions


def _discover_claude_sessions(config: Config) -> list[DiscoveredSession]:
    projects_dir = config.projects_dir
    if not projects_dir.is_dir():
        logger.info("Claude projects directory not found: %s", projects_dir)
        return []

    sessions: list[DiscoveredSession] = []
    for entry in sorted(projects_dir.iterdir()):
        if not entry.is_dir():
            continue

        project_id = entry.name
        project_path = _decode_project_id(project_id)
        project_name = _project_name_from_path(project_path)
        index_data = _load_sessions_index(entry)

        for jsonl_path in sorted(entry.glob("*.jsonl")):
            stat = jsonl_path.stat()
            source_session_id = jsonl_path.stem
            metadata = index_data.get(source_session_id, {})

            sessions.append(
                DiscoveredSession(
                    session_id=_provider_session_id(
                        _CLAUDE,
                        source_session_id,
                        file_path=jsonl_path,
                    ),
                    source_session_id=source_session_id,
                    provider=_CLAUDE,
                    file_path=jsonl_path,
                    project_id=project_id,
                    project_path=project_path,
                    project_name=project_name,
                    mtime_ms=int(stat.st_mtime * 1000),
                    file_size=stat.st_size,
                    first_prompt=str(metadata.get("firstPrompt", "")),
                    summary=str(metadata.get("summary", "")),
                    message_count=int(metadata.get("messageCount", 0)),  # type: ignore[arg-type]
                    created=str(metadata.get("created", "")),
                    modified=str(metadata.get("modified", "")),
                    git_branch=str(metadata.get("gitBranch", "")),
                    is_sidechain=bool(metadata.get("isSidechain", False)),
                )
            )

    return sessions


def _discover_codex_sessions(config: Config) -> list[DiscoveredSession]:
    codex_sessions_dir = config.codex_sessions_dir
    if not codex_sessions_dir.is_dir():
        logger.info("Codex sessions directory not found: %s", codex_sessions_dir)
        return []

    sessions: list[DiscoveredSession] = []
    for jsonl_path in sorted(codex_sessions_dir.rglob("*.jsonl")):
        stat = jsonl_path.stat()
        metadata = _scan_codex_metadata(jsonl_path)
        source_session_id = metadata.source_session_id or jsonl_path.stem

        project_path = metadata.project_path
        project_name = _project_name_from_path(project_path) if project_path else "Unknown"
        project_fallback = (
            _encode_project_path(project_path)
            or f"unknown-{jsonl_path.parent.name}-{jsonl_path.parent.parent.name}"
        )
        project_id = _provider_project_id(_CODEX, project_path, fallback=project_fallback)

        sessions.append(
            DiscoveredSession(
                session_id=_provider_session_id(
                    _CODEX,
                    source_session_id,
                    file_path=jsonl_path,
                ),
                source_session_id=source_session_id,
                provider=_CODEX,
                file_path=jsonl_path,
                project_id=project_id,
                project_path=project_path,
                project_name=project_name,
                mtime_ms=int(stat.st_mtime * 1000),
                file_size=stat.st_size,
                first_prompt=metadata.first_prompt,
                message_count=metadata.message_count,
                created=metadata.created,
                modified=metadata.modified,
                git_branch=metadata.git_branch,
            )
        )

    return sessions


def _discover_gemini_sessions(config: Config) -> list[DiscoveredSession]:
    gemini_tmp_dir = config.gemini_tmp_dir
    if not gemini_tmp_dir.is_dir():
        logger.info("Gemini tmp directory not found: %s", gemini_tmp_dir)
        return []

    hash_to_path = _build_gemini_project_hash_map(config)
    sessions: list[DiscoveredSession] = []

    for session_path in sorted(gemini_tmp_dir.rglob("session-*.json")):
        stat = session_path.stat()
        payload = _safe_load_json(session_path)
        if not isinstance(payload, dict):
            continue

        source_session_id = str(payload.get("sessionId", "")) or session_path.stem
        project_hash = str(payload.get("projectHash", "")).strip()

        project_path = hash_to_path.get(project_hash, "")
        if not project_path:
            project_root = session_path.parent.parent.parent / ".project_root"
            project_path = _read_text(project_root).strip()
            if project_path and project_hash:
                hash_to_path[project_hash] = project_path

        project_name = _project_name_from_path(project_path)
        if project_name == "Unknown":
            project_name = session_path.parent.parent.parent.name

        project_fallback = project_hash or session_path.parent.parent.parent.name or "unknown"
        project_id = _provider_project_id(_GEMINI, project_path, fallback=project_fallback)

        first_prompt = ""
        summary = ""
        message_count = 0
        messages = payload.get("messages")
        if isinstance(messages, list):
            for message in messages:
                if not isinstance(message, dict):
                    continue
                msg_type = str(message.get("type", "")).strip().lower()
                if msg_type in {"user", "gemini", "assistant", "info"}:
                    message_count += 1
                if not first_prompt and msg_type == "user":
                    first_prompt = _extract_gemini_text(message.get("content"))[:500]
                if not summary and msg_type in {"gemini", "assistant"}:
                    summary = _extract_gemini_text(message.get("content"))[:500]

        sessions.append(
            DiscoveredSession(
                session_id=_provider_session_id(
                    _GEMINI,
                    source_session_id,
                    file_path=session_path,
                ),
                source_session_id=source_session_id,
                provider=_GEMINI,
                file_path=session_path,
                project_id=project_id,
                project_path=project_path,
                project_name=project_name,
                mtime_ms=int(stat.st_mtime * 1000),
                file_size=stat.st_size,
                first_prompt=first_prompt,
                summary=summary,
                message_count=message_count,
                created=str(payload.get("startTime", "")),
                modified=str(payload.get("lastUpdated", "")),
            )
        )

    return sessions


def _scan_codex_metadata(path: Path) -> _CodexMeta:
    """Scan key metadata from a Codex JSONL session without full parse."""
    meta = _CodexMeta()
    max_lines = 600

    try:
        with open(path, encoding="utf-8") as file:
            for line_num, line in enumerate(file, start=1):
                if line_num > max_lines:
                    break

                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue

                timestamp = raw.get("timestamp")
                if isinstance(timestamp, str) and timestamp:
                    if not meta.created:
                        meta.created = timestamp
                    meta.modified = timestamp

                msg_type = raw.get("type")
                if msg_type == "session_meta":
                    payload = raw.get("payload")
                    if not isinstance(payload, dict):
                        continue
                    sid = payload.get("id")
                    if isinstance(sid, str) and sid:
                        meta.source_session_id = sid
                    cwd = payload.get("cwd")
                    if isinstance(cwd, str) and cwd:
                        meta.project_path = cwd
                    git_payload = payload.get("git")
                    if isinstance(git_payload, dict):
                        branch = git_payload.get("branch")
                        if isinstance(branch, str):
                            meta.git_branch = branch
                    continue

                if msg_type != "response_item":
                    continue

                payload = raw.get("payload")
                if not isinstance(payload, dict):
                    continue

                payload_type = str(payload.get("type", "")).strip()
                if payload_type == "message":
                    role = str(payload.get("role", "")).strip()
                    if role in {"user", "assistant"}:
                        meta.message_count += 1
                    if role == "user" and not meta.first_prompt:
                        prompt = _extract_codex_message_text(payload.get("content"))
                        if prompt and "<environment_context>" not in prompt:
                            meta.first_prompt = prompt[:500]
                elif payload_type in {"function_call", "function_call_output", "reasoning"}:
                    meta.message_count += 1
    except OSError:
        logger.warning("Failed to read Codex session metadata from %s", path)

    return meta


def _extract_codex_message_text(content: object) -> str:
    """Extract a textual message from Codex content arrays."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
            continue
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if isinstance(text, str) and text:
            parts.append(text)
    return "\n".join(parts)


def _extract_gemini_text(content: object) -> str:
    """Extract textual content from Gemini message payloads."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
                continue
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
        return "\n".join(parts)
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return text
    return ""


def _load_sessions_index(project_dir: Path) -> dict[str, dict[str, object]]:
    """Load Claude sessions-index.json and return entries keyed by sessionId."""
    index_path = project_dir / "sessions-index.json"
    if not index_path.is_file():
        return {}
    try:
        with open(index_path, encoding="utf-8") as file:
            data = json.load(file)
        entries = data.get("entries", [])
        return {e["sessionId"]: e for e in entries if isinstance(e, dict) and "sessionId" in e}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load sessions index %s: %s", index_path, exc)
        return {}


def _build_gemini_project_hash_map(config: Config) -> dict[str, str]:
    """Build map of project SHA256 hash -> project path for Gemini sessions."""
    hash_to_path: dict[str, str] = {}

    projects_json = config.gemini_dir / "projects.json"
    payload = _safe_load_json(projects_json)
    if isinstance(payload, dict):
        projects = payload.get("projects")
        if isinstance(projects, dict):
            for project_path in projects:
                if isinstance(project_path, str) and project_path.strip():
                    digest = hashlib.sha256(project_path.encode("utf-8")).hexdigest()
                    hash_to_path[digest] = project_path

    for history_project in sorted((config.gemini_dir / "history").glob("*/.project_root")):
        project_path = _read_text(history_project).strip()
        if not project_path:
            continue
        digest = hashlib.sha256(project_path.encode("utf-8")).hexdigest()
        hash_to_path[digest] = project_path

    for tmp_project in sorted(config.gemini_tmp_dir.glob("*/.project_root")):
        project_path = _read_text(tmp_project).strip()
        if not project_path:
            continue
        digest = hashlib.sha256(project_path.encode("utf-8")).hexdigest()
        hash_to_path[digest] = project_path

    return hash_to_path


def _safe_load_json(path: Path) -> object:
    if not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""
