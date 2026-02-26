"""Session detail focus-mode controller for the main window."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QSplitter, QStatusBar

from cch.ui.panels.detail_list_panel import DetailListPanel, SessionListViewState
from cch.ui.panels.list_panel import ListPanel, ProjectListViewState
from cch.ui.panels.nav_sidebar import NavSidebar


@dataclass
class _FocusSnapshot:
    splitter_state: QByteArray | None = None
    project_list_state: ProjectListViewState | None = None
    session_list_state: SessionListViewState | None = None


class SessionFocusController:
    """Owns focus/unfocus state for projects+sessions panes."""

    def __init__(
        self,
        *,
        sidebar: NavSidebar,
        splitter: QSplitter,
        list_panel: ListPanel,
        detail_panel: DetailListPanel,
        status_bar: QStatusBar,
    ) -> None:
        self._sidebar = sidebar
        self._splitter = splitter
        self._list_panel = list_panel
        self._detail_panel = detail_panel
        self._status_bar = status_bar
        self._active = False
        self._snapshot = _FocusSnapshot(
            project_list_state=self._list_panel.capture_view_state(),
            session_list_state=self._detail_panel.capture_view_state(),
        )

    @property
    def active(self) -> bool:
        return self._active

    def toggle(
        self,
        *,
        current_nav: str,
        history_active: bool,
        apply_nav_visibility: Callable[[str], None],
    ) -> None:
        if self._active:
            self.exit(current_nav=current_nav, apply_nav_visibility=apply_nav_visibility)
            return
        self.enter(current_nav=current_nav, history_active=history_active)

    def enter(self, *, current_nav: str, history_active: bool) -> None:
        if self._active:
            return
        if current_nav != "history" or not history_active:
            return
        self._snapshot.splitter_state = self._splitter.saveState()
        self._snapshot.project_list_state = self._list_panel.capture_view_state()
        self._snapshot.session_list_state = self._detail_panel.capture_view_state()
        self._active = True
        self._sidebar.set_pane_collapsed(True)
        self._splitter.setSizes([0, 0, max(1, self._splitter.width())])
        self._status_bar.showMessage("Session focus mode enabled. Press Esc to restore.", 2500)

    def exit(self, *, current_nav: str, apply_nav_visibility: Callable[[str], None]) -> None:
        if not self._active:
            return
        self._active = False
        self._sidebar.set_pane_collapsed(False)
        if self._snapshot.splitter_state is not None:
            self._splitter.restoreState(self._snapshot.splitter_state)
            self._snapshot.splitter_state = None
        apply_nav_visibility(current_nav)
        if self._snapshot.project_list_state is not None:
            self._list_panel.restore_view_state(self._snapshot.project_list_state)
        if self._snapshot.session_list_state is not None:
            self._detail_panel.restore_view_state(self._snapshot.session_list_state)
        self._status_bar.showMessage("Session focus mode disabled.", 1500)
