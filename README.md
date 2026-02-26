# CCH - Code CLI Helper

CCH is a local desktop app for exploring AI coding session history across multiple providers:
- Claude (`~/.claude/projects`)
- Codex (`~/.codex/sessions`)
- Gemini (`~/.gemini/tmp`)

It discovers session files, normalizes messages into a shared schema, indexes them into SQLite + FTS5, and provides a fast PySide6 UI for browsing, filtering, and searching.

## Authorship

This project is coded mostly by **Codex**, with additional contributions from **Claude Code**.

## Why This Project Exists

Provider logs are spread across different directories and formats. CCH unifies them so you can:
- inspect sessions/project activity in one place
- run full-text search across providers
- filter by provider and message category consistently
- review detailed conversations with usage/cost context

## Core Features

- Multi-provider ingestion for Claude/Codex/Gemini.
- Canonical message categories:
  - `user`
  - `assistant`
  - `tool_use`
  - `tool_result`
  - `thinking`
  - `system`
- Incremental indexing with forced full reindex support.
- Automatic DB schema-version detection and full reindex trigger when needed.
- Fast SQLite FTS5 search with filters:
  - providers
  - project name/path query
  - message categories
- Search chips show per-category counts (faceted counts).
- Project and session list views with provider-aware grouping.
- Session detail view with:
  - rich web rendering
  - persistent category filters across session navigation
  - focus mode (`Focus/Unfocus`) for detail-first reading
  - zoom controls
- Context menus to open project/session locations in Finder (macOS).
- Stats dashboard with aggregate metrics and charts.

## Design Choices

- `src/` layout (`src/cch`) for packaging hygiene and import safety.
- Layered architecture:
  - `data/`: discovery, parsing, indexing, SQL
  - `services/`: query/use-case APIs for UI
  - `ui/`: Qt views/panels/widgets
- Provider-specific parsing + canonical normalization:
  - parser converts provider-specific payloads into one message model.
- SQLite as the local source of truth:
  - WAL mode for responsive reads/writes
  - FTS5 for scalable full-text search
- UI rendering strategy:
  - session detail uses `QWebEngineView` for modern HTML rendering
  - large payload fallback to temporary file-backed loading
  - defensive startup cleanup for stale webview temp directories

## Project Structure

```text
src/cch/
  cli.py                # Typer CLI entrypoints
  config.py             # directory + DB config
  data/                 # discovery/parser/indexer/db/search
  models/               # pydantic/domain models
  services/             # service layer
  ui/                   # app shell, panels, views, widgets
tests/                  # unit/integration tests
```

## Requirements

- Python 3.13+
- `uv` (recommended) or equivalent virtualenv/pip workflow
- macOS/Linux desktop environment for the UI

## Install & Run

```bash
uv sync
uv run cch
```

Optional provider path overrides:

```bash
uv run cch \
  --claude-dir /path/to/.claude \
  --codex-dir /path/to/.codex \
  --gemini-dir /path/to/.gemini
```

## Reindex

Reindex always performs a full rebuild:

```bash
uv run cch reindex
```

## Development

Run checks:

```bash
uv run ruff check src tests
uv run basedpyright
uv run pytest -q
```

## Keyboard Shortcuts (UI)

- `Ctrl+1` Projects view
- `Ctrl+2` Search view
- `Ctrl+3` Stats view
- `Ctrl+Shift+M` or `F11` Focus/Unfocus session detail
- `Esc` Exit focus mode
- `Ctrl++` / `Ctrl+=` Zoom in (session detail)
- `Ctrl+-` Zoom out (session detail)
- `Ctrl+0` Reset zoom (session detail)

## License

MIT. See [LICENSE](LICENSE).
