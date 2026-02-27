"""PySide6 application bootstrap — main window, service init, run_app()."""

from __future__ import annotations

import logging
import os
import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
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
from cch.ui.session_focus import SessionFocusController
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
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color: #5A6570;")
        self._status_bar.addWidget(self._status_label, 1)
        self._copy_session_ref_btn = QPushButton("Copy")
        self._copy_session_ref_btn.setFixedHeight(20)
        self._copy_session_ref_btn.setToolTip("Copy selected project/session paths")
        self._copy_session_ref_btn.setEnabled(False)
        self._copy_session_ref_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_session_ref_btn.setStyleSheet(
            "QPushButton { "
            "  padding: 2px 8px; "
            "  border: 1px solid #D4D8DC; "
            "  border-radius: 8px; "
            "  background-color: #FFFFFF; "
            "  font-size: 11px; "
            "}"
            "QPushButton:hover:enabled { "
            "  border-color: #D86C1A; "
            "}"
            "QPushButton:disabled { "
            "  color: #AEB4BA; "
            "  background-color: #F5F7F9; "
            "}"
        )
        self._copy_session_ref_btn.clicked.connect(self._copy_session_reference)
        self._status_bar.addPermanentWidget(self._copy_session_ref_btn)
        self._status_default_text = "Ready"
        self._shutdown_in_progress = False
        self._project_request_generation = 0
        self._session_request_generation = 0
        self._selected_project_id = ""
        self._selected_project_name = ""
        self._selected_project_path = ""
        self._active_session_id = ""
        self._active_session_provider = ""
        self._active_session_file_path = ""
        self._active_session_cwd = ""
        self._project_names_by_id: dict[str, str] = {}
        self._project_paths_by_id: dict[str, str] = {}
        self._refresh_in_progress = False
        self._current_nav = "history"
        self._focus_controller = SessionFocusController(
            sidebar=self._sidebar,
            splitter=self._splitter,
            list_panel=self._list_panel,
            detail_panel=self._detail_panel,
            status_bar=self._status_bar,
        )
        self._force_exit_timer = QTimer(self)
        self._force_exit_timer.setSingleShot(True)
        self._force_exit_timer.timeout.connect(lambda: os._exit(0))

        # ── Wire signals ──
        self._sidebar.nav_changed.connect(self._on_nav_changed)
        self._sidebar.refresh_requested.connect(self._refresh_requested)
        self._sidebar.force_refresh_requested.connect(self._force_refresh_requested)
        self._sidebar.pane_toggle_requested.connect(self._toggle_session_focus_mode)
        self._sidebar.keys_requested.connect(self._show_shortcuts_dialog)
        self._list_panel.project_selected.connect(self._on_project_selected)
        self._detail_panel.session_selected.connect(self._on_session_selected)
        self._content_panel.session_requested.connect(self._on_session_selected)
        self._sidebar.set_pane_collapsed(False)
        self._status_label.setText(self._status_default_text)
        self._update_status_context()

        # ── Keyboard shortcuts ──
        self._setup_shortcuts()

        # ── Restore geometry ──
        self._restore_state()

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts."""
        from PySide6.QtGui import QKeySequence, QShortcut

        QShortcut(QKeySequence("Ctrl+1"), self, lambda: self._sidebar.select_nav("history"))
        QShortcut(QKeySequence("Ctrl+2"), self, lambda: self._sidebar.select_nav("search"))
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
        if self._focus_controller.active:
            if name != "history":
                self._focus_controller.exit(
                    current_nav=self._current_nav,
                    apply_nav_visibility=self._apply_nav_visibility,
                )
            else:
                self._content_panel.show_history()
                self._update_status_context()
                return
        self._apply_nav_visibility(name)
        self._update_status_context()

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

    def _toggle_session_focus_mode(self) -> None:
        """Toggle session-detail focus mode for history view."""
        self._focus_controller.toggle(
            current_nav=self._current_nav,
            history_active=self._content_panel.is_history_active(),
            apply_nav_visibility=self._apply_nav_visibility,
        )

    def _exit_session_focus_mode(self) -> None:
        """Restore pre-focus layout after session detail focus mode."""
        self._focus_controller.exit(
            current_nav=self._current_nav,
            apply_nav_visibility=self._apply_nav_visibility,
        )

    def _zoom_in_session(self) -> None:
        """Increase session detail zoom when history view is active."""
        if self._current_nav != "history" or not self._content_panel.is_history_active():
            return
        factor = self._content_panel.zoom_in_session()
        self._show_transient_status(f"Zoom: {factor:.0%}", 1200)

    def _zoom_out_session(self) -> None:
        """Decrease session detail zoom when history view is active."""
        if self._current_nav != "history" or not self._content_panel.is_history_active():
            return
        factor = self._content_panel.zoom_out_session()
        self._show_transient_status(f"Zoom: {factor:.0%}", 1200)

    def _reset_session_zoom(self) -> None:
        """Reset session detail zoom when history view is active."""
        if self._current_nav != "history" or not self._content_panel.is_history_active():
            return
        factor = self._content_panel.reset_session_zoom()
        self._show_transient_status(f"Zoom: {factor:.0%}", 1200)

    def _show_shortcuts_dialog(self) -> None:
        """Show keyboard shortcuts help."""
        QMessageBox.information(
            self,
            "Keyboard Shortcuts",
            "\n".join(
                [
                    "Ctrl+1: Projects view",
                    "Ctrl+2: Search view",
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
        self._selected_project_id = project_id
        self._selected_project_name = self._project_names_by_id.get(project_id, "")
        self._selected_project_path = self._project_paths_by_id.get(project_id, "")
        self._active_session_id = ""
        self._active_session_provider = ""
        self._active_session_file_path = ""
        self._active_session_cwd = ""
        self._update_status_context()
        await self._load_project_sessions(project_id)

    async def _load_project_sessions(self, project_id: str) -> None:
        """Load sessions for one project into the sessions list panel."""
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
        self._active_session_id = session_id
        self._update_status_context()
        await self._load_session_detail(session_id, message_uuid)

    async def _load_session_detail(self, session_id: str, message_uuid: str = "") -> None:
        """Load session detail and render it."""
        if not self._services:
            return
        self._session_request_generation += 1
        generation = self._session_request_generation
        result = await self._services.session_service.get_session_detail(
            session_id,
            limit=None,
        )
        if generation != self._session_request_generation:
            return
        if isinstance(result, Ok):
            detail = result.ok_value
            self._selected_project_id = detail.project_id or self._selected_project_id
            if detail.project_name:
                self._selected_project_name = detail.project_name
            if self._selected_project_id:
                self._selected_project_path = self._project_paths_by_id.get(
                    self._selected_project_id,
                    self._selected_project_path,
                )
            self._active_session_provider = detail.provider
            self._active_session_file_path = detail.file_path
            self._active_session_cwd = detail.cwd
            self._update_status_context()
            self._content_panel.show_session(
                detail,
                focus_message_uuid=message_uuid,
            )

    async def _run_indexing(self, *, force: bool = False, label: str = "Refreshing") -> None:
        """Run indexing while updating status text with progress."""
        if self._services is None:
            return
        self._status_label.setText(f"{label}: preparing...")
        result = await self._services.indexer.index_all(
            force=force,
            progress_callback=lambda c, t, m: self._status_label.setText(
                f"{label}: {c}/{t} {m}"
            ),
        )
        logger.info("Indexing complete: %s", result)
        self._show_transient_status(
            f"{label} complete: {result.files_indexed} indexed, "
            f"{result.files_skipped} skipped, {result.files_failed} failed",
            3500,
        )

    @async_slot
    async def _refresh_requested(self) -> None:
        """Perform an on-demand indexing refresh from the sidebar button."""
        await self._refresh(force=False, label="Refresh")

    @async_slot
    async def _force_refresh_requested(self) -> None:
        """Perform a full on-demand reindex from the sidebar button."""
        await self._refresh(force=True, label="Force refresh")

    async def _refresh(self, *, force: bool, label: str) -> None:
        """Run refresh workflow while preserving project/session pane state."""
        if self._shutdown_in_progress or self._services is None:
            return
        if self._refresh_in_progress:
            return
        self._refresh_in_progress = True
        self._sidebar.set_refresh_busy(True)
        prior_project_state = self._list_panel.capture_view_state()
        prior_session_state = self._detail_panel.capture_view_state()
        selected_project_id = self._selected_project_id or prior_project_state.selected_project_id
        selected_session_id = self._active_session_id or prior_session_state.selected_session_id
        try:
            await self._run_indexing(force=force, label=label)
            await self._load_projects()
            self._list_panel.restore_view_state(prior_project_state)
            if selected_project_id:
                await self._load_project_sessions(selected_project_id)
                self._detail_panel.restore_view_state(prior_session_state)
            if (
                selected_session_id
                and self._current_nav == "history"
                and self._content_panel.is_history_active()
            ):
                await self._load_session_detail(selected_session_id)
        except Exception:
            logger.exception("Refresh failed")
            self._show_transient_status("Refresh failed. Check terminal logs.", 4000)
        finally:
            self._refresh_in_progress = False
            self._sidebar.set_refresh_busy(False)
            self._update_status_context()

    async def initialize(self) -> None:
        """Initialize services and load initial data."""
        try:
            logger.info("Starting CCH — building service container...")
            self._services = await ServiceContainer.create(self._config)

            # Background indexing
            logger.info("Starting initial indexing...")
            force_reindex = bool(self._services.db.requires_full_reindex)
            if force_reindex:
                logger.info("Detected old DB schema. Running full reindex.")
            await self._run_indexing(force=force_reindex, label="Initial load")

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
            self._project_names_by_id = {
                project.project_id: project.project_name for project in projects
            }
            self._project_paths_by_id = {
                project.project_id: project.project_path for project in projects
            }
            if (
                self._selected_project_id
                and self._selected_project_id not in self._project_names_by_id
            ):
                self._selected_project_id = ""
                self._selected_project_name = ""
                self._selected_project_path = ""
                self._active_session_id = ""
                self._active_session_provider = ""
                self._active_session_file_path = ""
                self._active_session_cwd = ""
            self._update_status_context()

    def _update_status_context(self) -> None:
        """Render selected project/session context in the status bar."""
        has_selection = bool(self._active_session_id)
        if has_selection:
            project_label = self._selected_project_name or self._selected_project_id or "Unknown"
            self._status_default_text = (
                f"Project: {project_label} | Session ID: {self._active_session_id}"
            )
        else:
            self._status_default_text = "Ready"
        if not self._refresh_in_progress and not self._shutdown_in_progress:
            self._status_label.setText(self._status_default_text)
        self._copy_session_ref_btn.setEnabled(has_selection)

    def _copy_session_reference(self) -> None:
        """Copy selected project/session identifiers and absolute paths."""
        if not self._active_session_id:
            return
        if not self._active_session_file_path:
            return
        project_label = self._selected_project_name or self._selected_project_id or "Unknown"
        project_folder_path = _to_abs_path(self._selected_project_path)
        session_file_path = _to_abs_path(self._active_session_file_path)
        provider_history_path = _session_history_folder_path(session_file_path)
        text = (
            f"Project: {project_label}\n"
            f"Session ID: {self._active_session_id}\n"
            f"Project Folder: {project_folder_path}\n"
            f"Provider History Path: {provider_history_path}\n"
            f"Session File: {session_file_path}"
        )
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self._show_transient_status("Copied project/session/path reference", 1500)

    def _show_transient_status(self, text: str, timeout_ms: int) -> None:
        """Show temporary status text, then restore the default context text."""
        self._status_label.setText(text)

        def _restore() -> None:
            if self._refresh_in_progress or self._shutdown_in_progress:
                return
            self._status_label.setText(self._status_default_text)

        QTimer.singleShot(timeout_ms, _restore)

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
        if self._focus_controller.active:
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


def _to_abs_path(path: str) -> str:
    """Return absolute path string when available."""
    if not path:
        return ""
    return os.path.abspath(path)


def _session_history_folder_path(session_file_path: str) -> str:
    """Return the concrete history folder containing the selected session file."""
    if not session_file_path:
        return ""
    parent = os.path.dirname(session_file_path)
    if not parent:
        return ""
    return os.path.join(parent, "")
