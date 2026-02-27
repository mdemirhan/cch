"""Custom list delegates for project, session and search rows."""

from __future__ import annotations

import re

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from cch.models.categories import COLOR_BY_KEY, LABEL_BY_KEY, normalize_message_type
from cch.models.projects import ProjectRoles
from cch.models.search import SearchResultRoles
from cch.models.sessions import SessionRoles
from cch.ui.theme import (
    COLORS,
    format_relative_time,
    format_tokens,
    provider_color,
    provider_label,
)

_ROW_BG_EVEN = QColor(COLORS["panel_bg"])
_ROW_BG_ODD = QColor("#F5F6F7")
_SELECTED_BG = QColor(COLORS["primary_light"])
_HOVER_BG = QColor("#EEF3F7")
_BORDER_COLOR = QColor("#E8E8E8")


def _row_background(index: QModelIndex | QPersistentModelIndex) -> QColor:
    return _ROW_BG_EVEN if index.row() % 2 == 0 else _ROW_BG_ODD


def _elide_middle(text: str, max_width: int, painter: QPainter) -> str:
    return painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideMiddle, max_width)


def _wrap_and_elide(text: str, max_width: int, max_lines: int, painter: QPainter) -> str:
    """Wrap text to max_lines and ellide the final line if needed."""
    if max_width <= 0 or max_lines <= 0:
        return ""
    normalized = " ".join(text.split())
    if not normalized:
        return ""

    fm = painter.fontMetrics()
    words = normalized.split(" ")
    lines: list[str] = []
    current = ""

    for word in words:
        candidate = word if not current else f"{current} {word}"
        if fm.horizontalAdvance(candidate) <= max_width:
            current = candidate
            continue

        if current:
            lines.append(current)
            if len(lines) >= max_lines:
                current = ""
                break

        if fm.horizontalAdvance(word) <= max_width:
            current = word
            continue

        chunk = ""
        for char in word:
            trial = chunk + char
            if fm.horizontalAdvance(trial) <= max_width or not chunk:
                chunk = trial
                continue
            lines.append(chunk)
            if len(lines) >= max_lines:
                chunk = ""
                break
            chunk = char
        current = chunk
        if len(lines) >= max_lines:
            current = ""
            break

    if current and len(lines) < max_lines:
        lines.append(current)

    if not lines:
        return fm.elidedText(normalized, Qt.TextElideMode.ElideRight, max_width)
    if len(lines) == max_lines:
        lines[-1] = fm.elidedText(lines[-1], Qt.TextElideMode.ElideRight, max_width)
    return "\n".join(lines)


def _draw_provider_badge(
    painter: QPainter,
    *,
    provider: str,
    top: int,
    right: int,
) -> QRect:
    label = provider_label(provider)
    color = provider_color(provider)

    font = QFont(painter.font().family(), 9, QFont.Weight.DemiBold)
    painter.setFont(font)
    fm = painter.fontMetrics()
    badge_w = max(fm.horizontalAdvance(label) + 12, 52)
    badge_rect = QRect(right - badge_w, top, badge_w, 18)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(badge_rect, 9, 9)
    painter.setPen(QColor("#FFFFFF"))
    painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, label)
    return badge_rect


class ProjectDelegate(QStyledItemDelegate):
    """Project row: name, provider badge, path, relative time and session count."""

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        return QSize(option.rect.width(), 72)

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

        name = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        path = str(index.data(ProjectRoles.PATH) or "")
        count = int(index.data(ProjectRoles.SESSION_COUNT) or 0)
        last_activity = str(index.data(ProjectRoles.LAST_ACTIVITY) or "")
        provider = str(index.data(ProjectRoles.PROVIDER) or "claude")

        left = rect.left() + 16
        right = rect.right() - 16

        badge_rect = _draw_provider_badge(
            painter,
            provider=provider,
            top=rect.top() + 10,
            right=right,
        )

        count_text = str(count)
        painter.setFont(QFont(painter.font().family(), 10, QFont.Weight.DemiBold))
        count_w = painter.fontMetrics().horizontalAdvance(count_text) + 12
        count_rect = QRect(badge_rect.left() - count_w - 8, rect.top() + 10, count_w, 18)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#E6E8EA"))
        painter.drawRoundedRect(count_rect, 9, 9)
        painter.setPen(QColor("#616A72"))
        painter.drawText(count_rect, Qt.AlignmentFlag.AlignCenter, count_text)

        name_right = max(left, count_rect.left() - 10)
        painter.setFont(QFont(painter.font().family(), 14, QFont.Weight.DemiBold))
        painter.setPen(QColor(COLORS["text"]))
        name_text = _elide_middle(name, name_right - left, painter)
        name_rect = QRect(left, rect.top() + 10, name_right - left, 20)
        painter.drawText(
            name_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            name_text,
        )

        painter.setFont(QFont(painter.font().family(), 11))
        painter.setPen(QColor("#7A848C"))
        path_text = _elide_middle(path, right - left, painter)
        path_rect = QRect(left, rect.top() + 36, right - left, 17)
        painter.drawText(
            path_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            path_text,
        )

        if last_activity:
            painter.setPen(QColor("#9AA3AA"))
            time_rect = QRect(left, rect.top() + 54, right - left, 14)
            painter.drawText(
                time_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                format_relative_time(last_activity),
            )

        painter.setPen(QPen(_BORDER_COLOR, 1))
        painter.drawLine(rect.left() + 14, rect.bottom(), rect.right() - 14, rect.bottom())
        painter.restore()


class SessionDelegate(QStyledItemDelegate):
    """Session row: summary, model/meta, tokens/time and provider badge."""

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        return QSize(option.rect.width(), 92)

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
            painter.fillRect(
                QRect(rect.left(), rect.top(), 3, rect.height()),
                QColor(COLORS["primary"]),
            )
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect, _HOVER_BG)
        else:
            painter.fillRect(rect, _row_background(index))

        summary = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        model = str(index.data(SessionRoles.MODEL) or "")
        input_tokens = int(index.data(SessionRoles.INPUT_TOKENS) or 0)
        output_tokens = int(index.data(SessionRoles.OUTPUT_TOKENS) or 0)
        modified = str(index.data(SessionRoles.MODIFIED_AT) or "")
        msg_count = int(index.data(SessionRoles.MESSAGE_COUNT) or 0)
        provider = str(index.data(SessionRoles.PROVIDER) or "claude")

        left = rect.left() + 16
        right = rect.right() - 16
        badge_rect = _draw_provider_badge(
            painter,
            provider=provider,
            top=rect.top() + 10,
            right=right,
        )

        painter.setFont(QFont(painter.font().family(), 13, QFont.Weight.DemiBold))
        painter.setPen(QColor(COLORS["text"]))
        summary_width = max(0, badge_rect.left() - left - 8)
        summary_text = _wrap_and_elide(summary, summary_width, 2, painter)
        painter.drawText(
            QRect(left, rect.top() + 8, summary_width, 34),
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignTop
            | Qt.TextFlag.TextWordWrap
            | Qt.TextFlag.TextWrapAnywhere,
            summary_text,
        )

        painter.setFont(QFont(painter.font().family(), 11))
        painter.setPen(QColor("#707A83"))
        meta = f"{model or 'Unknown model'}  ·  {msg_count} msgs"
        meta_text = _elide_middle(meta, right - left, painter)
        painter.drawText(
            QRect(left, rect.top() + 46, right - left, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            meta_text,
        )

        painter.setPen(QColor("#8A949B"))
        token_text = f"{format_tokens(input_tokens)} in · {format_tokens(output_tokens)} out"
        token_width = max(0, right - left - 96)
        token_text = _elide_middle(token_text, token_width, painter)
        painter.drawText(
            QRect(left, rect.top() + 66, token_width, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            token_text,
        )
        if modified:
            painter.drawText(
                QRect(right - 90, rect.top() + 66, 90, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                format_relative_time(modified),
            )

        painter.setPen(QPen(_BORDER_COLOR, 1))
        painter.drawLine(rect.left() + 14, rect.bottom(), rect.right() - 14, rect.bottom())
        painter.restore()


class SearchResultDelegate(QStyledItemDelegate):
    """Search result row: snippet, message type, provider badge, project and timestamp."""

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        return QSize(option.rect.width(), 72)

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

        snippet = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        message_type = normalize_message_type(
            str(index.data(SearchResultRoles.MESSAGE_TYPE) or "")
        )
        project = str(index.data(SearchResultRoles.PROJECT_NAME) or "")
        timestamp = str(index.data(SearchResultRoles.TIMESTAMP) or "")
        provider = str(index.data(SearchResultRoles.PROVIDER) or "claude")

        left = rect.left() + 16
        right = rect.right() - 16

        role_color = COLOR_BY_KEY.get(message_type, COLORS["text_muted"])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(role_color))
        painter.drawEllipse(left, rect.top() + 13, 6, 6)

        painter.setPen(QColor(role_color))
        painter.setFont(QFont(painter.font().family(), 10, QFont.Weight.DemiBold))
        painter.drawText(
            QRect(left + 10, rect.top() + 7, 72, 14),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            LABEL_BY_KEY.get(message_type, message_type.capitalize()),
        )

        badge_rect = _draw_provider_badge(
            painter,
            provider=provider,
            top=rect.top() + 8,
            right=right,
        )
        if timestamp:
            painter.setPen(QColor("#95A0A7"))
            painter.setFont(QFont(painter.font().family(), 10))
            painter.drawText(
                QRect(badge_rect.left() - 98, rect.top() + 8, 92, 18),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                format_relative_time(timestamp),
            )

        painter.setPen(QColor("#7A848C"))
        painter.setFont(QFont(painter.font().family(), 10))
        project_width = max(0, badge_rect.left() - left - 186)
        painter.drawText(
            QRect(left + 82, rect.top() + 7, project_width, 14),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            _elide_middle(project, project_width, painter),
        )

        plain_snippet = re.sub(r"<[^>]+>", "", snippet).strip()
        painter.setPen(QColor(COLORS["text"]))
        painter.setFont(QFont(painter.font().family(), 12))
        painter.drawText(
            QRect(left, rect.top() + 30, right - left, 28),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            _elide_middle(plain_snippet, right - left, painter),
        )

        painter.setPen(QPen(_BORDER_COLOR, 1))
        painter.drawLine(rect.left() + 14, rect.bottom(), rect.right() - 14, rect.bottom())
        painter.restore()
