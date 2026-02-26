"""Custom item delegates for QListView — ProjectDelegate, SessionDelegate, SearchResultDelegate."""

from __future__ import annotations

import re

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem, QWidget

from cch.ui.theme import COLORS, format_relative_time, format_tokens

# Alternating row backgrounds for visual separation
_ROW_BG_EVEN = QColor(COLORS["panel_bg"])
_ROW_BG_ODD = QColor("#F5F5F5")
_SELECTED_BG = QColor(COLORS["primary_light"])
_HOVER_BG = QColor("#F0F0F0")
_BORDER_COLOR = QColor("#EBEBEB")


def _row_background(index: QModelIndex | QPersistentModelIndex) -> QColor:
    """Return alternating background color for a row."""
    return _ROW_BG_EVEN if index.row() % 2 == 0 else _ROW_BG_ODD


class ProjectDelegate(QStyledItemDelegate):
    """Renders a project row: name, path snippet, session count, last activity."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        return QSize(option.rect.width(), 62)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect

        # Background with selection/hover/alternating
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, _SELECTED_BG)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect, _HOVER_BG)
        else:
            painter.fillRect(rect, _row_background(index))

        # Data from model
        name = index.data(Qt.ItemDataRole.DisplayRole) or ""
        path = index.data(Qt.ItemDataRole.UserRole + 1) or ""
        count = index.data(Qt.ItemDataRole.UserRole + 2) or 0
        last_activity = index.data(Qt.ItemDataRole.UserRole + 3) or ""

        left = rect.left() + 14
        right = rect.right() - 14

        # Project name
        font = QFont(painter.font().family(), 13, QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(COLORS["text"]))
        name_rect = QRect(left, rect.top() + 10, right - left - 70, 20)
        painter.drawText(
            name_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name
        )

        # Session count badge (right-aligned, pill-shaped)
        painter.setFont(QFont(painter.font().family(), 10))
        count_text = str(count)
        fm = painter.fontMetrics()
        badge_w = max(fm.horizontalAdvance(count_text) + 14, 28)
        badge_h = 18
        badge_x = right - badge_w
        badge_y = rect.top() + 11
        badge_rect = QRect(badge_x, badge_y, badge_w, badge_h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#EAEAEA"))
        painter.drawRoundedRect(badge_rect, 9, 9)
        painter.setPen(QColor(COLORS["text_muted"]))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, count_text)

        # Path and last activity
        painter.setFont(QFont(painter.font().family(), 11))
        painter.setPen(QColor(COLORS["text_muted"]))
        display_path = path
        if len(display_path) > 40:
            display_path = "..." + display_path[-37:]
        sub_rect = QRect(left, rect.top() + 34, right - left, 18)
        sub_text = display_path
        if last_activity:
            sub_text += f"  ·  {format_relative_time(last_activity)}"
        painter.drawText(
            sub_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, sub_text
        )

        # Bottom separator line
        painter.setPen(QPen(_BORDER_COLOR, 1))
        painter.drawLine(rect.left() + 14, rect.bottom(), rect.right() - 14, rect.bottom())

        painter.restore()


class SessionDelegate(QStyledItemDelegate):
    """Renders a session row: first prompt, model, token counts, timestamp."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        return QSize(option.rect.width(), 68)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, _SELECTED_BG)
            # Draw left accent bar on selected item
            painter.fillRect(
                QRect(rect.left(), rect.top(), 3, rect.height()),
                QColor(COLORS["primary"]),
            )
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect, _HOVER_BG)
        else:
            painter.fillRect(rect, _row_background(index))

        summary = index.data(Qt.ItemDataRole.DisplayRole) or ""
        model = index.data(Qt.ItemDataRole.UserRole + 1) or ""
        input_tokens = index.data(Qt.ItemDataRole.UserRole + 2) or 0
        output_tokens = index.data(Qt.ItemDataRole.UserRole + 3) or 0
        modified = index.data(Qt.ItemDataRole.UserRole + 4) or ""
        msg_count = index.data(Qt.ItemDataRole.UserRole + 5) or 0

        left = rect.left() + 14
        right = rect.right() - 14

        # Summary (first line)
        painter.setFont(QFont(painter.font().family(), 12))
        painter.setPen(QColor(COLORS["text"]))
        summary_display = summary[:55] + ("..." if len(summary) > 55 else "")
        summary_rect = QRect(left, rect.top() + 8, right - left, 20)
        painter.drawText(
            summary_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            summary_display,
        )

        # Second line: model + tokens + messages
        painter.setFont(QFont(painter.font().family(), 10))
        painter.setPen(QColor(COLORS["text_muted"]))
        token_str = f"{format_tokens(input_tokens)}\u2193 {format_tokens(output_tokens)}\u2191"
        meta = f"{model}  \u00b7  {msg_count} msgs  \u00b7  {token_str}"
        meta_rect = QRect(left, rect.top() + 28, right - left, 16)
        painter.drawText(
            meta_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, meta
        )

        # Third line: relative time
        if modified:
            painter.setFont(QFont(painter.font().family(), 10))
            painter.setPen(QColor("#B0B0B0"))
            time_rect = QRect(left, rect.top() + 44, right - left, 16)
            painter.drawText(
                time_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                format_relative_time(modified),
            )

        # Bottom separator
        painter.setPen(QPen(_BORDER_COLOR, 1))
        painter.drawLine(rect.left() + 14, rect.bottom(), rect.right() - 14, rect.bottom())

        painter.restore()


class SearchResultDelegate(QStyledItemDelegate):
    """Renders a search result row: snippet, role, project, timestamp."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        return QSize(option.rect.width(), 64)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, _SELECTED_BG)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect, _HOVER_BG)
        else:
            painter.fillRect(rect, _row_background(index))

        snippet = index.data(Qt.ItemDataRole.DisplayRole) or ""
        role = index.data(Qt.ItemDataRole.UserRole + 1) or ""
        project = index.data(Qt.ItemDataRole.UserRole + 2) or ""
        timestamp = index.data(Qt.ItemDataRole.UserRole + 3) or ""

        left = rect.left() + 14
        right = rect.right() - 14

        # Role indicator (small colored dot + text)
        role_color = COLORS["primary"] if role == "user" else COLORS["success"]
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(role_color))
        dot_y = rect.top() + 13
        painter.drawEllipse(left, dot_y, 6, 6)

        painter.setPen(QColor(role_color))
        painter.setFont(QFont(painter.font().family(), 10, QFont.Weight.DemiBold))
        role_rect = QRect(left + 10, rect.top() + 6, 60, 16)
        painter.drawText(
            role_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            role.capitalize(),
        )

        # Project badge
        if project:
            painter.setPen(QColor(COLORS["text_muted"]))
            painter.setFont(QFont(painter.font().family(), 10))
            proj_rect = QRect(left + 75, rect.top() + 6, right - left - 175, 16)
            painter.drawText(
                proj_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                project,
            )

        # Timestamp (right-aligned)
        if timestamp:
            painter.setFont(QFont(painter.font().family(), 10))
            painter.setPen(QColor("#B0B0B0"))
            time_rect = QRect(right - 100, rect.top() + 6, 100, 16)
            painter.drawText(
                time_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                format_relative_time(timestamp),
            )

        # Snippet (strip HTML tags for plain text rendering)
        plain_snippet = re.sub(r"<[^>]+>", "", snippet)[:80]
        painter.setFont(QFont(painter.font().family(), 12))
        painter.setPen(QColor(COLORS["text"]))
        snippet_rect = QRect(left, rect.top() + 26, right - left, 20)
        painter.drawText(
            snippet_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            plain_snippet,
        )

        # Bottom separator
        painter.setPen(QPen(_BORDER_COLOR, 1))
        painter.drawLine(rect.left() + 14, rect.bottom(), rect.right() - 14, rect.bottom())

        painter.restore()
