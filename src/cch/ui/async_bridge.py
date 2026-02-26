"""Async bridge — qasync event loop integration for PySide6."""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

logger = logging.getLogger(__name__)


def create_event_loop(app: QApplication) -> QEventLoop:
    """Create and install a qasync event loop bridging Qt and asyncio."""
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    return loop


def async_slot[**P, T](
    func: Callable[P, Coroutine[Any, Any, T]],
) -> Callable[P, None]:
    """Decorator that wraps an async coroutine so it can be used as a Qt slot.

    Usage::

        @async_slot
        async def on_button_clicked(self) -> None:
            result = await some_service.fetch_data()
            self.update_ui(result)
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
        coro = func(*args, **kwargs)
        future = asyncio.ensure_future(coro)
        future.add_done_callback(_log_exception)

    return wrapper


def _log_exception(future: asyncio.Future[Any]) -> None:
    """Log any exception from an async slot."""
    if future.cancelled():
        return
    exc = future.exception()
    if exc is not None:
        logger.exception("Unhandled exception in async slot", exc_info=exc)


def schedule[T](coro: Coroutine[Any, Any, T]) -> asyncio.Future[T]:
    """Schedule an async coroutine on the running event loop."""
    return asyncio.ensure_future(coro)
