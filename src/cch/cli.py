"""Typer CLI for CCH — serve and reindex commands."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from cch.config import Config

app = typer.Typer(
    name="cch",
    help="CCH - Code CLI Helper for Claude/Codex/Gemini session data.",
    invoke_without_command=True,
)


@app.callback(invoke_without_command=True)
def serve(
    ctx: typer.Context,
    claude_dir: Annotated[
        Path | None,
        typer.Option("--claude-dir", help="Path to Claude data directory"),
    ] = None,
    codex_dir: Annotated[
        Path | None,
        typer.Option("--codex-dir", help="Path to Codex data directory"),
    ] = None,
    gemini_dir: Annotated[
        Path | None,
        typer.Option("--gemini-dir", help="Path to Gemini data directory"),
    ] = None,
) -> None:
    """Start the CCH desktop application."""
    if ctx.invoked_subcommand is not None:
        return
    config = Config(
        claude_dir=claude_dir or Path.home() / ".claude",
        codex_dir=codex_dir or Path.home() / ".codex",
        gemini_dir=gemini_dir or Path.home() / ".gemini",
    )
    from cch.ui.app import run_app

    run_app(config)


@app.command()
def reindex(
    claude_dir: Annotated[
        Path | None,
        typer.Option("--claude-dir", help="Path to Claude data directory"),
    ] = None,
    codex_dir: Annotated[
        Path | None,
        typer.Option("--codex-dir", help="Path to Codex data directory"),
    ] = None,
    gemini_dir: Annotated[
        Path | None,
        typer.Option("--gemini-dir", help="Path to Gemini data directory"),
    ] = None,
) -> None:
    """Rebuild the SQLite index from scratch."""
    config = Config(
        claude_dir=claude_dir or Path.home() / ".claude",
        codex_dir=codex_dir or Path.home() / ".codex",
        gemini_dir=gemini_dir or Path.home() / ".gemini",
    )
    asyncio.run(_do_reindex(config))


async def _do_reindex(config: Config) -> None:
    """Run the reindex operation."""
    from cch.data.db import Database
    from cch.data.indexer import Indexer

    typer.echo(
        "Indexing sessions from "
        f"{config.projects_dir}, {config.codex_sessions_dir}, {config.gemini_tmp_dir}..."
    )

    async with Database(config.db_path) as db:
        indexer = Indexer(db, config)

        def progress(current: int, total: int, message: str) -> None:
            typer.echo(f"  [{current}/{total}] {message}")

        result = await indexer.index_all(progress_callback=progress, force=True)

    typer.echo(f"\nDone! {result}")
