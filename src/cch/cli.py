"""Typer CLI for CCH — serve and reindex commands."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from cch.config import Config

app = typer.Typer(
    name="cch",
    help="Claude Code History — Interactive dashboard for Claude Code session data.",
    no_args_is_help=True,
)


@app.command()
def serve(
    claude_dir: Annotated[
        Path | None,
        typer.Option("--claude-dir", help="Path to Claude data directory"),
    ] = None,
    port: Annotated[int, typer.Option("--port", help="Server port")] = 8765,
    host: Annotated[str, typer.Option("--host", help="Server host")] = "127.0.0.1",
) -> None:
    """Start the CCH dashboard server."""
    config = Config(
        claude_dir=claude_dir or Path.home() / ".claude",
        port=port,
        host=host,
    )
    from cch.ui.app import run_app

    run_app(config)


@app.command()
def reindex(
    claude_dir: Annotated[
        Path | None,
        typer.Option("--claude-dir", help="Path to Claude data directory"),
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Force full re-index")] = False,
) -> None:
    """Force rebuild the SQLite index."""
    config = Config(
        claude_dir=claude_dir or Path.home() / ".claude",
    )
    asyncio.run(_do_reindex(config, force))


async def _do_reindex(config: Config, force: bool) -> None:
    """Run the reindex operation."""
    from cch.data.db import Database
    from cch.data.indexer import Indexer

    typer.echo(f"Indexing sessions from {config.projects_dir}...")

    async with Database(config.db_path) as db:
        indexer = Indexer(db, config)

        def progress(current: int, total: int, message: str) -> None:
            typer.echo(f"  [{current}/{total}] {message}")

        result = await indexer.index_all(progress_callback=progress, force=force)

    typer.echo(f"\nDone! {result}")
