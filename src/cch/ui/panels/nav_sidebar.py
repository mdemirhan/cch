"""Left navigation sidebar with icon-backed navigation buttons."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QStyle, QVBoxLayout, QWidget

from cch.ui.theme import COLORS

_NAV_ITEMS = [
    ("history", "Projects", QStyle.StandardPixmap.SP_FileDialogDetailedView),
    ("search", "Search", QStyle.StandardPixmap.SP_FileDialogContentsView),
    ("statistics", "Stats", QStyle.StandardPixmap.SP_FileDialogInfoView),
]


class NavSidebar(QWidget):
    """Vertical sidebar for top-level navigation."""

    nav_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(96)
        self.setStyleSheet(
            "background-color: #F4F6F8; "
            f"border-right: 1px solid {COLORS['border']};"
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
