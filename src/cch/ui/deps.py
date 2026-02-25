"""Dependency access for UI pages."""

from __future__ import annotations

from nicegui import app

from cch.services.container import ServiceContainer

_CONTAINER_KEY = "cch_services"


def set_services(container: ServiceContainer) -> None:
    """Store the service container in NiceGUI app state."""
    setattr(app.state, _CONTAINER_KEY, container)


def get_services() -> ServiceContainer:
    """Retrieve the service container from NiceGUI app state."""
    container = getattr(app.state, _CONTAINER_KEY, None)
    if container is None:
        msg = "ServiceContainer not initialized"
        raise RuntimeError(msg)
    return container  # type: ignore[return-value]
