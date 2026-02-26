"""Service container with DI wiring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cch.data.db import Database
from cch.data.indexer import Indexer
from cch.data.search import SearchEngine
from cch.services.analytics_service import AnalyticsService
from cch.services.project_service import ProjectService
from cch.services.search_service import SearchService
from cch.services.session_service import SessionService

if TYPE_CHECKING:
    from cch.config import Config


@dataclass
class ServiceContainer:
    """Holds all application services. Built once at startup, immutable."""

    db: Database
    indexer: Indexer
    session_service: SessionService
    project_service: ProjectService
    analytics_service: AnalyticsService
    search_service: SearchService

    @classmethod
    async def create(cls, config: Config) -> ServiceContainer:
        """Async factory that wires all dependencies."""
        db = Database(config.db_path)
        await db.__aenter__()

        indexer = Indexer(db, config)
        search_engine = SearchEngine(db)

        session_service = SessionService(db)
        project_service = ProjectService(db)
        analytics_service = AnalyticsService(db)
        search_service = SearchService(search_engine)

        return cls(
            db=db,
            indexer=indexer,
            session_service=session_service,
            project_service=project_service,
            analytics_service=analytics_service,
            search_service=search_service,
        )

    async def close(self) -> None:
        """Shut down all services."""
        await self.db.__aexit__(None, None, None)
