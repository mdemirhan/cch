"""PySide6 application bootstrap — main window, service init, run_app()."""

from __future__ import annotations

import logging
import os
import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import QByteArray, QSettings, Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QWidget,
)
from result import Ok

from cch.services.container import ServiceContainer
from cch.ui.async_bridge import async_slot, cancel_all_tasks, create_event_loop, schedule
from cch.ui.panels.content_panel import ContentPanel
from cch.ui.panels.detail_list_panel import DetailListPanel
from cch.ui.panels.list_panel import ListPanel
from cch.ui.panels.nav_sidebar import NavSidebar
from cch.ui.temp_cleanup import cleanup_stale_webview_temp_dirs
from cch.ui.theme import build_stylesheet

if TYPE_CHECKING:
    from cch.config import Config

logger = logging.getLogger(__name__)


def _ensure_webengine_flags() -> None:
    """Apply Chromium flags before QApplication starts."""
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip().split()
    if "--disable-features=SkiaGraphite" not in flags:
        flags.append("--disable-features=SkiaGraphite")
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(flags).strip()


class CCHMainWindow(QMainWindow):
    """Three-panel master-detail main window."""

    def __init__(self, config: Config) -> None:
        super().__init__()
        self._config = config
        self._services: ServiceContainer | None = None

        self.setWindowTitle("Code Chat History")
        self.setMinimumSize(1100, 700)

        # ── Central widget ──
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Nav sidebar ──
        self._sidebar = NavSidebar()
        layout.addWidget(self._sidebar)

        # ── Three-panel splitter ──
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self._list_panel = ListPanel()
        self._detail_panel = DetailListPanel()
        self._content_panel = ContentPanel()

        self._splitter.addWidget(self._list_panel)
        self._splitter.addWidget(self._detail_panel)
        self._splitter.addWidget(self._content_panel)

        self._splitter.setSizes([230, 220, 600])
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setStretchFactor(2, 1)

        layout.addWidget(self._splitter)

        # ── Status bar ──
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("Loading...")
        self._status_bar.addWidget(self._status_label)
        self._shutdown_in_progress = False
        self._project_request_generation = 0
        self._session_request_generation = 0
        self._current_nav = "history"
        self._session_focus_mode = False
        self._pre_focus_splitter_state: QByteArray | None = None
        self._pre_focus_project_list_state = self._list_panel.capture_view_state()
        self._pre_focus_session_list_state = self._detail_panel.capture_view_state()
        self._force_exit_timer = QTimer(self)
        self._force_exit_timer.setSingleShot(True)
        self._force_exit_timer.timeout.connect(lambda: os._exit(0))

        # ── Wire signals ──
        self._sidebar.nav_changed.connect(self._on_nav_changed)
        self._sidebar.pane_toggle_requested.connect(self._toggle_session_focus_mode)
        self._sidebar.keys_requested.connect(self._show_shortcuts_dialog)
        self._list_panel.project_selected.connect(self._on_project_selected)
        self._detail_panel.session_selected.connect(self._on_session_selected)
        self._content_panel.session_requested.connect(self._on_session_selected)
        self._sidebar.set_pane_collapsed(False)

        # ── Keyboard shortcuts ──
        self._setup_shortcuts()

        # ── Restore geometry ──
        self._restore_state()

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts."""
        from PySide6.QtGui import QKeySequence, QShortcut

        QShortcut(QKeySequence("Ctrl+1"), self, lambda: self._sidebar.select_nav("history"))
        QShortcut(QKeySequence("Ctrl+2"), self, lambda: self._sidebar.select_nav("search"))
        QShortcut(QKeySequence("Ctrl+3"), self, lambda: self._sidebar.select_nav("statistics"))
        QShortcut(QKeySequence("F11"), self, self._toggle_session_focus_mode)
        QShortcut(QKeySequence("Ctrl+Shift+M"), self, self._toggle_session_focus_mode)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._exit_session_focus_mode)
        QShortcut(QKeySequence("Ctrl++"), self, self._zoom_in_session)
        QShortcut(QKeySequence("Ctrl+="), self, self._zoom_in_session)
        QShortcut(QKeySequence("Ctrl+-"), self, self._zoom_out_session)
        QShortcut(QKeySequence("Ctrl+0"), self, self._reset_session_zoom)

    def _on_nav_changed(self, name: str) -> None:
        """Handle sidebar navigation change."""
        self._current_nav = name
        if self._session_focus_mode:
            if name != "history":
                self._exit_session_focus_mode()
            else:
                self._content_panel.show_history()
                return
        self._apply_nav_visibility(name)

    def _apply_nav_visibility(self, name: str) -> None:
        """Update panel visibility and active content for the selected nav."""
        if name == "history":
            # Keep panes visible in history mode so their internal selection/scroll
            # state is preserved; focus mode collapses width via splitter sizes.
            self._list_panel.setVisible(True)
            self._detail_panel.setVisible(True)
            self._content_panel.show_history()
        elif name == "search":
            self._list_panel.setVisible(False)
            self._detail_panel.setVisible(False)
            self._content_panel.show_search()
        elif name == "statistics":
            self._list_panel.setVisible(False)
            self._detail_panel.setVisible(False)
            self._content_panel.show_statistics()

    def _toggle_session_focus_mode(self) -> None:
        """Toggle session-detail focus mode for history view."""
        if self._session_focus_mode:
            self._exit_session_focus_mode()
            return
        self._enter_session_focus_mode()

    def _enter_session_focus_mode(self) -> None:
        """Hide side panels so session detail fills the available window."""
        if self._session_focus_mode:
            return
        if self._current_nav != "history" or not self._content_panel.is_history_active():
            return
        self._pre_focus_splitter_state = self._splitter.saveState()
        self._pre_focus_project_list_state = self._list_panel.capture_view_state()
        self._pre_focus_session_list_state = self._detail_panel.capture_view_state()
        self._session_focus_mode = True
        self._sidebar.set_pane_collapsed(True)
        self._splitter.setSizes([0, 0, max(1, self._splitter.width())])
        self._status_bar.showMessage(
            "Session focus mode enabled. Press Esc to restore.",
            2500,
        )

    def _exit_session_focus_mode(self) -> None:
        """Restore pre-focus layout after session detail focus mode."""
        if not self._session_focus_mode:
            return
        self._session_focus_mode = False
        self._sidebar.set_pane_collapsed(False)
        if self._pre_focus_splitter_state is not None:
            self._splitter.restoreState(self._pre_focus_splitter_state)
            self._pre_focus_splitter_state = None
        self._apply_nav_visibility(self._current_nav)
        self._list_panel.restore_view_state(self._pre_focus_project_list_state)
        self._detail_panel.restore_view_state(self._pre_focus_session_list_state)
        self._status_bar.showMessage("Session focus mode disabled.", 1500)

    def _zoom_in_session(self) -> None:
        """Increase session detail zoom when history view is active."""
        if self._current_nav != "history" or not self._content_panel.is_history_active():
            return
        factor = self._content_panel.zoom_in_session()
        self._status_bar.showMessage(f"Zoom: {factor:.0%}", 1200)

    def _zoom_out_session(self) -> None:
        """Decrease session detail zoom when history view is active."""
        if self._current_nav != "history" or not self._content_panel.is_history_active():
            return
        factor = self._content_panel.zoom_out_session()
        self._status_bar.showMessage(f"Zoom: {factor:.0%}", 1200)

    def _reset_session_zoom(self) -> None:
        """Reset session detail zoom when history view is active."""
        if self._current_nav != "history" or not self._content_panel.is_history_active():
            return
        factor = self._content_panel.reset_session_zoom()
        self._status_bar.showMessage(f"Zoom: {factor:.0%}", 1200)

    def _show_shortcuts_dialog(self) -> None:
        """Show keyboard shortcuts help."""
        QMessageBox.information(
            self,
            "Keyboard Shortcuts",
            "\n".join(
                [
                    "Ctrl+1: Projects view",
                    "Ctrl+2: Search view",
                    "Ctrl+3: Stats view",
                    "Ctrl+Shift+M or F11: Focus/unfocus session detail",
                    "Esc: Exit focus mode",
                    "Ctrl++ or Ctrl+=: Zoom in session detail",
                    "Ctrl+-: Zoom out session detail",
                    "Ctrl+0: Reset session detail zoom",
                ]
            ),
        )

    @async_slot
    async def _on_project_selected(self, project_id: str) -> None:
        """Load sessions for the selected project."""
        if not self._services:
            return
        self._project_request_generation += 1
        generation = self._project_request_generation
        result = await self._services.session_service.list_sessions(
            project_id=project_id, limit=200, sort_by="modified_at", sort_order="desc"
        )
        if generation != self._project_request_generation:
            return
        if isinstance(result, Ok):
            sessions, _total = result.ok_value
            self._detail_panel.set_sessions(sessions)

    @async_slot
    async def _on_session_selected(self, session_id: str, message_uuid: str = "") -> None:
        """Load full session detail and display in content panel."""
        if not self._services:
            return
        self._session_request_generation += 1
        generation = self._session_request_generation
        offset = 0
        if message_uuid:
            msg_offset = await self._services.session_service.get_message_offset(
                session_id,
                message_uuid,
            )
            if msg_offset is not None:
                offset = max(0, msg_offset - 200)
        result = await self._services.session_service.get_session_detail(
            session_id,
            limit=1200,
            offset=offset,
        )
        if generation != self._session_request_generation:
            return
        if isinstance(result, Ok):
            self._content_panel.show_session(
                result.ok_value,
                focus_message_uuid=message_uuid,
            )

    async def initialize(self) -> None:
        """Initialize services and load initial data."""
        try:
            logger.info("Starting CCH — building service container...")
            self._services = await ServiceContainer.create(self._config)

            # Background indexing
            logger.info("Starting background indexing...")
            force_reindex = bool(self._services.db.requires_full_reindex)
            if force_reindex:
                logger.info("Detected old DB schema. Running full reindex.")
            result = await self._services.indexer.index_all(
                force=force_reindex,
                progress_callback=lambda c, t, m: logger.info("[%d/%d] %s", c, t, m)
            )
            logger.info("Indexing complete: %s", result)

            # Pass services to panels that need them
            self._content_panel.set_services(self._services)

            # Load projects
            await self._load_projects()
        except Exception:
            logger.exception("Application startup failed")
            self._status_label.setText("Startup failed. Check terminal logs.")

    async def _load_projects(self) -> None:
        """Load projects into the list panel."""
        if not self._services:
            return
        projects_result = await self._services.project_service.list_projects()
        if isinstance(projects_result, Ok):
            projects = projects_result.ok_value
            self._list_panel.set_projects(projects)

            # Count sessions
            total_sessions = sum(p.session_count for p in projects)
            self._status_label.setText(f"{len(projects)} projects  {total_sessions} sessions")

    def _restore_state(self) -> None:
        """Restore window geometry and splitter positions from QSettings."""
        settings = QSettings("CCH", "ClaudeCodeHistory")
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)  # type: ignore[arg-type]
        splitter_state = settings.value("splitter")
        if splitter_state:
            self._splitter.restoreState(splitter_state)  # type: ignore[arg-type]

    def closeEvent(self, event: QCloseEvent) -> None:
        """Save state and terminate.

        Attempt graceful shutdown first; force-exit as a fallback if
        QWebEngine/Qt teardown gets stuck.
        """
        if self._session_focus_mode:
            self._exit_session_focus_mode()

        settings = QSettings("CCH", "ClaudeCodeHistory")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("splitter", self._splitter.saveState())
        settings.sync()

        if self._shutdown_in_progress:
            event.accept()
            return

        if self._services is None:
            event.accept()
            self._content_panel.dispose()
            app = QApplication.instance()
            if app is not None:
                app.quit()
            return

        self._shutdown_in_progress = True
        event.ignore()
        self._status_label.setText("Shutting down...")

        # Fallback for known QtWebEngine teardown hangs.
        self._force_exit_timer.start(2500)
        schedule(self._shutdown_and_quit())

    async def _shutdown_and_quit(self) -> None:
        """Best-effort cleanup before quitting the Qt app."""
        try:
            cancel_all_tasks()
            self._content_panel.dispose()
            if self._services is not None:
                await self._services.close()
                self._services = None
        except Exception:
            logger.exception("Error while shutting down services")
        finally:
            self._force_exit_timer.stop()
            app = QApplication.instance()
            if app is not None:
                app.quit()


def run_app(config: Config) -> None:
    """Entry point: create QApplication, event loop, main window, and run."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    _ensure_webengine_flags()
    removed = cleanup_stale_webview_temp_dirs()
    if removed:
        logger.info("Removed %d stale webview temp directories", removed)

    app = QApplication(sys.argv)
    app.setApplicationName("Code Chat History")
    app.setOrganizationName("CCH")
    app.setStyleSheet(build_stylesheet())

    loop = create_event_loop(app)

    window = CCHMainWindow(config)
    window.show()

    # Kick off async initialization
    schedule(window.initialize())

    with loop:
        loop.run_forever()
