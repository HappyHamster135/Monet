"""Category navigation and accessible tool rows in the Utilities window."""
from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QPalette, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from actions import CATEGORIES, category_for


class ToolRow(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(150, max(54, option.fontMetrics.height() * 2 + 12))

    def paint(self, painter, option, index):
        item = QStyleOptionViewItem(option)
        self.initStyleOption(item, index)
        bounds = item.rect.adjusted(2, 2, -3, -2)
        active = bool(item.state & QStyle.State_Selected)
        hover = bool(item.state & QStyle.State_MouseOver)
        color = item.palette.color(QPalette.AlternateBase)
        accent = item.palette.color(QPalette.Highlight)
        if active or hover:
            portion = 0.20 if active else 0.09
            color = QColor.fromRgbF(*(a * (1 - portion) + b * portion for a, b in
                                      zip(color.getRgbF()[:3], accent.getRgbF()[:3])))
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        line = QColor(accent if active else item.palette.color(QPalette.Mid))
        line.setAlpha(175 if active else 50)
        painter.setPen(QPen(line, 1))
        painter.setBrush(color)
        painter.drawRoundedRect(bounds, 11, 11)
        # Mirror the icon and disclosure indicator with the application's layout.
        rtl = item.direction == Qt.RightToLeft
        iconbox = bounds.adjusted(13, 0, -13, 0)
        ix = iconbox.right() - 24 if rtl else iconbox.left()
        item.icon.paint(painter, ix, bounds.center().y() - 12, 24, 24)
        text_box = bounds.adjusted(32 if rtl else 50, 0, -50 if rtl else -32, 0)
        painter.setPen(item.palette.color(QPalette.Text))
        font = item.font
        font.setWeight(font.Weight.Medium)
        painter.setFont(font)
        align = Qt.AlignVCenter | (Qt.AlignRight if rtl else Qt.AlignLeft)
        hint = index.data(Qt.AccessibleDescriptionRole)
        title_box = QRect(text_box)
        if hint:
            title_box.setHeight(text_box.height() // 2)
        painter.drawText(title_box, align, painter.fontMetrics().elidedText(item.text, Qt.ElideRight, text_box.width()))
        if hint:
            font.setWeight(font.Weight.Normal)
            painter.setFont(font)
            hint_box = QRect(text_box)
            hint_box.setTop(title_box.bottom() + 1)
            painter.setPen(item.palette.color(QPalette.PlaceholderText))
            painter.drawText(hint_box, align, painter.fontMetrics().elidedText(hint, Qt.ElideRight, hint_box.width()))
        x = bounds.left() + 17 if rtl else bounds.right() - 17
        y = bounds.center().y()
        step = -3 if rtl else 3
        painter.setPen(QPen(item.palette.color(QPalette.PlaceholderText), 1.5))
        painter.drawLine(x, y - 4, x + step, y)
        painter.drawLine(x + step, y, x, y + 4)
        painter.restore()
