"""Left navigation sidebar with icon-backed navigation buttons."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QStyle, QVBoxLayout, QWidget

from cch.ui.theme import COLORS

_NAV_ITEMS = [
    ("history", "Projects", QStyle.StandardPixmap.SP_FileDialogDetailedView),
    ("search", "Search", QStyle.StandardPixmap.SP_FileDialogContentsView),
]


class NavSidebar(QWidget):
    """Vertical sidebar for top-level navigation."""

    nav_changed = Signal(str)
    pane_toggle_requested = Signal()
    keys_requested = Signal()
    refresh_requested = Signal()
    force_refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(96)
        self.setStyleSheet(
            f"background-color: #F4F6F8; border-right: 1px solid {COLORS['border']};"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(6)

        # App title badge
        title = QLabel("CCH")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-weight: 700; font-size: 13px; color: #D86C1A; "
            "padding: 8px 6px; background-color: #FFF; border: 1px solid #E5E8EB; "
            "border-radius: 10px; letter-spacing: 1px;"
        )
        layout.addWidget(title)

        self._buttons: dict[str, QPushButton] = {}
        for name, label, icon_type in _NAV_ITEMS:
            btn = QPushButton(label)
            btn.setIcon(self.style().standardIcon(icon_type))
            btn.setIconSize(QSize(14, 14))
            btn.setFixedSize(80, 36)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._button_style(False))
            btn.clicked.connect(lambda _checked, n=name: self._on_clicked(n))
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
            self._buttons[name] = btn

        layout.addStretch()

        self._refresh_btn = QPushButton("Inc\nRefresh")
        self._refresh_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self._refresh_btn.setIconSize(QSize(14, 14))
        self._refresh_btn.setFixedSize(80, 44)
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.setStyleSheet(self._toolbar_button_style())
        self._refresh_btn.setToolTip("Incremental refresh (changed files only)")
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)
        layout.addWidget(self._refresh_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self._force_refresh_btn = QPushButton("Force\nRefresh")
        self._force_refresh_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self._force_refresh_btn.setIconSize(QSize(14, 14))
        self._force_refresh_btn.setFixedSize(80, 44)
        self._force_refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._force_refresh_btn.setStyleSheet(self._toolbar_button_style())
        self._force_refresh_btn.setToolTip("Force full refresh (reindex all files)")
        self._force_refresh_btn.clicked.connect(self.force_refresh_requested.emit)
        layout.addWidget(self._force_refresh_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self._pane_btn = QPushButton("Focus")
        self._pane_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarShadeButton)
        )
        self._pane_btn.setIconSize(QSize(14, 14))
        self._pane_btn.setFixedSize(80, 34)
        self._pane_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pane_btn.setStyleSheet(self._toolbar_button_style())
        self._pane_btn.setToolTip("Focus session detail (Ctrl+Shift+M / F11)")
        self._pane_btn.clicked.connect(self.pane_toggle_requested.emit)
        layout.addWidget(self._pane_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self._keys_btn = QPushButton("Keys")
        self._keys_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogHelpButton)
        )
        self._keys_btn.setIconSize(QSize(14, 14))
        self._keys_btn.setFixedSize(80, 34)
        self._keys_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._keys_btn.setStyleSheet(self._toolbar_button_style())
        self._keys_btn.setToolTip("Show keyboard shortcuts")
        self._keys_btn.clicked.connect(self.keys_requested.emit)
        layout.addWidget(self._keys_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Select history by default
        self.select_nav("history")

    def select_nav(self, name: str) -> None:
        """Programmatically select a nav item."""
        self._on_clicked(name)

    def _on_clicked(self, name: str) -> None:
        """Handle nav button click."""
        for key, btn in self._buttons.items():
            is_active = key == name
            btn.setChecked(is_active)
            btn.setStyleSheet(self._button_style(is_active))
        self.nav_changed.emit(name)

    def set_pane_collapsed(self, collapsed: bool) -> None:
        """Update pane toggle button label to reflect current state."""
        if collapsed:
            self._pane_btn.setText("Unfocus")
            self._pane_btn.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarUnshadeButton)
            )
            self._pane_btn.setToolTip("Return to full panes layout (Esc)")
        else:
            self._pane_btn.setText("Focus")
            self._pane_btn.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarShadeButton)
            )
            self._pane_btn.setToolTip("Focus session detail (Ctrl+Shift+M / F11)")

    def set_refresh_busy(self, busy: bool) -> None:
        """Update refresh button state while a refresh is running."""
        self._refresh_btn.setEnabled(not busy)
        self._force_refresh_btn.setEnabled(not busy)
        if busy:
            self._refresh_btn.setText("Running")
            self._force_refresh_btn.setText("Running")
            return
        self._refresh_btn.setText("Inc\nRefresh")
        self._force_refresh_btn.setText("Force\nRefresh")

    @staticmethod
    def _button_style(active: bool) -> str:
        """Return QSS for a nav button."""
        if active:
            return (
                f"QPushButton {{ "
                "  background-color: #FFFFFF; "
                f"  color: {COLORS['text']}; "
                f"  border: 1px solid {COLORS['border']}; "
                f"  border-left: 3px solid {COLORS['primary']}; "
                "  border-radius: 8px; "
                "  font-size: 11px; font-weight: 600; "
                "  text-align: left; padding: 6px 8px; "
                f"}}"
            )
        return (
            f"QPushButton {{ "
            f"  background-color: transparent; "
            f"  color: {COLORS['text_muted']}; "
            "  border: 1px solid transparent; border-radius: 8px; "
            "  font-size: 11px; "
            "  text-align: left; padding: 6px 8px; "
            f"}} "
            f"QPushButton:hover {{ "
            "  background-color: #FFFFFF; "
            f"  border-color: {COLORS['border']}; "
            f"  color: {COLORS['text']}; "
            f"}}"
        )

    @staticmethod
    def _toolbar_button_style() -> str:
        """Return QSS for bottom toolbar-style action buttons."""
        return (
            f"QPushButton {{ "
            "  background-color: #FFFFFF; "
            f"  color: {COLORS['text']}; "
            f"  border: 1px solid {COLORS['border']}; "
            "  border-radius: 8px; "
            "  font-size: 11px; font-weight: 600; "
            "  text-align: left; padding: 6px 8px; "
            f"}} "
            f"QPushButton:hover {{ "
            "  background-color: #FBFCFD; "
            f"  border-color: {COLORS['primary']}; "
            f"}} "
            f"QPushButton:pressed {{ "
            "  background-color: #F3F6F8; "
            f"}}"
        )
