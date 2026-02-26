"""Left navigation sidebar — fixed-width text buttons."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from cch.ui.theme import COLORS

_NAV_ITEMS = [
    ("history", "History"),
    ("search", "Search"),
    ("statistics", "Stats"),
    ("export", "Export"),
]


class NavSidebar(QWidget):
    """Vertical sidebar for top-level navigation."""

    nav_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(72)
        self.setStyleSheet(
            f"background-color: {COLORS['sidebar_bg']}; "
            f"border-right: 1px solid {COLORS['border']};"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(2)

        # App title
        title = QLabel("CCH")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"font-weight: bold; font-size: 13px; color: {COLORS['primary']}; "
            f"padding: 8px 0 16px 0; background-color: transparent; "
            f"letter-spacing: 2px;"
        )
        layout.addWidget(title)

        self._buttons: dict[str, QPushButton] = {}
        for name, label in _NAV_ITEMS:
            btn = QPushButton(label)
            btn.setFixedSize(64, 32)
            btn.setCheckable(True)
            btn.setStyleSheet(self._button_style(False))
            btn.clicked.connect(lambda _checked, n=name: self._on_clicked(n))
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
            self._buttons[name] = btn

        layout.addStretch()

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

    @staticmethod
    def _button_style(active: bool) -> str:
        """Return QSS for a nav button."""
        if active:
            return (
                f"QPushButton {{ "
                f"  background-color: {COLORS['primary']}; "
                f"  color: white; "
                f"  border: none; border-radius: 6px; "
                f"  font-size: 11px; font-weight: 600; "
                f"  padding: 6px 4px; "
                f"}}"
            )
        return (
            f"QPushButton {{ "
            f"  background-color: transparent; "
            f"  color: {COLORS['text_muted']}; "
            f"  border: none; border-radius: 6px; "
            f"  font-size: 11px; "
            f"  padding: 6px 4px; "
            f"}} "
            f"QPushButton:hover {{ "
            f"  background-color: #E8E8E8; "
            f"  color: {COLORS['text']}; "
            f"}}"
        )
