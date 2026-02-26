"""WebEngine-based message view that renders sessions as HTML."""

from __future__ import annotations

import json
import logging
import tempfile
import urllib.parse
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from cch.models.categories import DEFAULT_ACTIVE_CATEGORY_KEYS, normalize_category_keys
from cch.models.sessions import SessionDetail
from cch.ui.temp_cleanup import WEBVIEW_TEMP_MARKER_FILENAME
from cch.ui.widgets.session_document import build_session_document

_INLINE_CONTENT_LIMIT_BYTES = 1_500_000
_MAX_DATA_URL_LENGTH = 1_900_000
_MIN_ZOOM_FACTOR = 0.6
_MAX_ZOOM_FACTOR = 2.4
_ZOOM_STEP = 0.1
logger = logging.getLogger(__name__)


def _encode_document(document: str) -> bytes:
    return document.encode("utf-8", errors="replace")


def _data_url_length(content: bytes) -> int:
    prefix = "data:text/html;charset=UTF-8,"
    return len(prefix) + len(urllib.parse.quote_from_bytes(content))


def _can_use_inline_content(content: bytes) -> bool:
    if len(content) > _INLINE_CONTENT_LIMIT_BYTES:
        return False
    return _data_url_length(content) <= _MAX_DATA_URL_LENGTH


def _normalize_filters(raw: object) -> list[str] | None:
    values: list[str] | None = None
    if isinstance(raw, str):
        if raw == "__CCH_NO_STATE__":
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, list):
            return None
        values = [item for item in parsed if isinstance(item, str)]
    elif isinstance(raw, (list, tuple, set)):
        values = [item for item in raw if isinstance(item, str)]
    else:
        return None
    return normalize_category_keys(values)


class _HtmlTransport:
    """HTML transport strategy for QWebEngine content loading."""

    def __init__(self, webview: QWebEngineView) -> None:
        self._webview = webview
        self._temp_dir = tempfile.TemporaryDirectory(prefix="cch-webview-")
        marker = Path(self._temp_dir.name) / WEBVIEW_TEMP_MARKER_FILENAME
        try:
            marker.write_text("cch webview temp dir\n", encoding="utf-8")
        except OSError:
            logger.debug("Failed creating webview temp marker: %s", marker, exc_info=True)
        self._temp_files: list[Path] = []

    def load_document(self, document: str, generation: int) -> None:
        content = _encode_document(document)
        if _can_use_inline_content(content):
            self._webview.setContent(content, "text/html;charset=UTF-8")
            return

        target = Path(self._temp_dir.name) / f"conversation-{generation}.html"
        target.write_bytes(content)
        self._temp_files.append(target)
        if len(self._temp_files) > 6:
            old = self._temp_files.pop(0)
            old.unlink(missing_ok=True)
        self._webview.load(QUrl.fromLocalFile(str(target)))

    def dispose(self) -> None:
        for old in self._temp_files:
            old.unlink(missing_ok=True)
        self._temp_files.clear()
        self._temp_dir.cleanup()


class MessageWebView(QWidget):
    """Full session view powered by QWebEngineView."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._webview = QWebEngineView()
        layout.addWidget(self._webview)
        self._transport = _HtmlTransport(self._webview)

        self._pending_detail: SessionDetail | None = None
        self._pending_focus_message_uuid: str = ""
        self._current_focus_message_uuid: str = ""
        self._render_generation = 0
        self._rendered_generation = -1
        self._capture_generation = 0
        self._active_filters: list[str] = list(DEFAULT_ACTIVE_CATEGORY_KEYS)
        self._capture_timeout = QTimer(self)
        self._capture_timeout.setSingleShot(True)
        self._capture_timeout.timeout.connect(self._on_capture_timeout)

        self._webview.loadFinished.connect(self._on_load_finished)
        self._zoom_factor = 1.0
        self._webview.setZoomFactor(self._zoom_factor)

    def show_session(self, detail: SessionDetail, *, focus_message_uuid: str = "") -> None:
        """Render the full session (header + filters + messages)."""
        self._pending_detail = detail
        self._pending_focus_message_uuid = focus_message_uuid
        self._render_generation += 1
        self._capture_filters_and_render(self._render_generation)

    def _capture_filters_and_render(self, generation: int) -> None:
        self._capture_generation = generation
        self._capture_timeout.start(320)
        script = (
            "(function(){"
            "var filters = null;"
            "if (Array.isArray(window._activeFilters)) {"
            "  filters = window._activeFilters;"
            "} else if (typeof _activeFilters !== 'undefined' && Array.isArray(_activeFilters)) {"
            "  filters = _activeFilters;"
            "}"
            "if (!Array.isArray(filters)) {"
            "  return '__CCH_NO_STATE__';"
            "}"
            "try { return JSON.stringify(filters); } catch (_e) { return '__CCH_NO_STATE__'; }"
            "})()"
        )

        def _on_filters(raw: object) -> None:
            if generation != self._render_generation:
                return
            normalized = _normalize_filters(raw)
            if normalized is not None:
                self._active_filters = normalized
            if self._capture_timeout.isActive():
                self._capture_timeout.stop()
            self._render_pending(generation)

        self._webview.page().runJavaScript(script, _on_filters)

    def _on_capture_timeout(self) -> None:
        generation = self._capture_generation
        if generation != self._render_generation:
            return
        self._render_pending(generation)

    def _render_pending(self, generation: int) -> None:
        if generation != self._render_generation:
            return
        if generation == self._rendered_generation:
            return
        detail = self._pending_detail
        if detail is None:
            return

        self._current_focus_message_uuid = self._pending_focus_message_uuid
        document = build_session_document(detail, self._active_filters)
        self._rendered_generation = generation
        self._transport.load_document(document, generation)

    def _on_load_finished(self, ok: bool) -> None:
        if not ok or not self._current_focus_message_uuid:
            return
        target = self._current_focus_message_uuid
        self._current_focus_message_uuid = ""
        script = (
            f"(function(target){{"
            "if (!target) return;"
            "var tries = 0;"
            "var maxTries = 24;"
            "var delayMs = 50;"
            "function attempt(){"
            "  tries += 1;"
            "  if (typeof focusMessageByUuid !== 'function') {"
            "    if (tries < maxTries) { setTimeout(attempt, delayMs); }"
            "    return;"
            "  }"
            "  var focused = false;"
            "  try { focused = !!focusMessageByUuid(target); } catch (_e) { focused = false; }"
            "  if (!focused && tries < maxTries) {"
            "    setTimeout(attempt, delayMs);"
            "  }"
            "}"
            "attempt();"
            f"}})({repr(target)})"
        )
        self._webview.page().runJavaScript(script)

    def zoom_in(self) -> float:
        return self._set_zoom(self._zoom_factor + _ZOOM_STEP)

    def zoom_out(self) -> float:
        return self._set_zoom(self._zoom_factor - _ZOOM_STEP)

    def reset_zoom(self) -> float:
        return self._set_zoom(1.0)

    def _set_zoom(self, factor: float) -> float:
        clamped = max(_MIN_ZOOM_FACTOR, min(_MAX_ZOOM_FACTOR, factor))
        self._zoom_factor = round(clamped, 2)
        self._webview.setZoomFactor(self._zoom_factor)
        return self._zoom_factor

    def dispose(self) -> None:
        self._capture_timeout.stop()
        self._webview.stop()
        self._webview.setHtml("<html><body></body></html>")
        self._transport.dispose()
