"""NiceGUI bootstrap — wires DI, runs background indexing, registers pages."""

from __future__ import annotations

import logging

from nicegui import app, ui

from cch.config import Config
from cch.services.container import ServiceContainer
from cch.ui.deps import set_services

logger = logging.getLogger(__name__)


def run_app(config: Config) -> None:
    """Start the NiceGUI application."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    @app.on_startup
    async def startup() -> None:
        logger.info("Starting CCH — building service container...")
        container = await ServiceContainer.create(config)
        set_services(container)

        # Background indexing
        logger.info("Starting background indexing...")
        result = await container.indexer.index_all(
            progress_callback=lambda c, t, m: logger.info("[%d/%d] %s", c, t, m)
        )
        logger.info("Indexing complete: %s", result)

    @app.on_shutdown
    async def shutdown() -> None:
        from cch.ui.deps import get_services

        try:
            container = get_services()
            await container.close()
            logger.info("CCH shut down cleanly")
        except RuntimeError:
            pass

    # Register all pages
    from cch.ui.pages import (
        analytics,
        compare,
        dashboard,
        export,
        projects,
        search,
        session_detail,
        sessions,
        tools,
    )

    dashboard.setup()
    sessions.setup()
    session_detail.setup()
    projects.setup()
    search.setup()
    analytics.setup()
    tools.setup()
    compare.setup()
    export.setup()

    ui.run(
        title="Claude Code History",
        host=config.host,
        port=config.port,
        reload=False,
        show=True,
    )
