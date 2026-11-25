"""Floating, keyboard-accessible launcher for the favorites shared by Monet Utilities."""
import math

from PySide6.QtCore import QEvent, QModelIndex, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication, QIcon, QPainter, QPalette, QPen
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDialog, QHBoxLayout,
                               QLabel, QListView, QListWidget, QListWidgetItem, QPushButton,
                               QStackedWidget, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QToolButton, QVBoxLayout, QWidget)

from actions import ACTIONS, tr


class FavoriteTile(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return option.widget.gridSize()

    def paint(self, painter, option, index):
        item = QStyleOptionViewItem(option)
        self.initStyleOption(item, index)
        palette = item.palette
        selected = bool(item.state & QStyle.State_Selected)
        hovered = bool(item.state & QStyle.State_MouseOver)
        tile = item.rect.adjusted(3, 3, -3, -3)
        border = palette.color(QPalette.Highlight if selected or hovered else QPalette.Mid)
        border.setAlpha(255 if selected else 160 if hovered else 80)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(palette.color(QPalette.Highlight if selected else QPalette.Button))
        painter.setPen(QPen(border, 2 if selected or hovered else 1))
        painter.drawRoundedRect(tile, 8, 8)
        item.rect = tile.adjusted(6, 6, -6, -4)
        item.state &= ~(QStyle.State_Selected | QStyle.State_HasFocus | QStyle.State_MouseOver)
        item.displayAlignment = Qt.AlignHCenter | Qt.AlignTop
        item.decorationAlignment = Qt.AlignCenter
        item.palette.setColor(QPalette.Text, palette.color(QPalette.HighlightedText if selected else QPalette.ButtonText))
        option.widget.style().drawControl(QStyle.CE_ItemViewItem, item, painter, option.widget)
        painter.restore()


class FavoriteGrid(QListWidget):
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # IconMode reserves room for a scrollbar when it decides where to wrap.
        extent = self.style().pixelMetric(QStyle.PM_ScrollBarExtent, None, self)
        room = max(1, self.contentsRect().width() - extent - 2)
        columns = max(1, min(3, room // 120))
        size = QSize(room // columns, self.tile_height())
        if size != self.gridSize():
            self.setGridSize(size)

    def tile_height(self):
        return max(82, self.fontMetrics().height() * 3 + 39)


class QuickPanel(QDialog):
    chosen = Signal(str)
    reordered = Signal(list)
    dismissed = Signal()

    def __init__(self):
        super().__init__(None, Qt.Window | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowTitle(tr("Quick Panel"))
        self.setWindowIcon(QIcon.fromTheme("view-grid"))
        self.keys = []
        self.hidden_tools = set()
        layout = QVBoxLayout(self)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        page = QWidget()
        grid_layout = QVBoxLayout(page)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid = FavoriteGrid()
        self.grid.setAccessibleName(tr("Favorite tools"))
        self.grid.setViewMode(QListView.IconMode)
        self.grid.setMovement(QListView.Static)
        self.grid.setResizeMode(QListView.Adjust)
        self.grid.setSelectionMode(QAbstractItemView.SingleSelection)
        self.grid.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.grid.setWordWrap(True)
        self.grid.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.grid.setUniformItemSizes(True)
        self.grid.setItemDelegate(FavoriteTile(self.grid))
        self.grid.setMouseTracking(True)
        self.grid.setIconSize(QSize(32, 32))
        self.grid.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.grid.setFrameShape(QListWidget.NoFrame)
        self.grid.itemClicked.connect(self.activate)
        self.grid.installEventFilter(self)
        grid_layout.addWidget(self.grid)
        self.empty = QLabel(tr("Add a favorite to use it from the Quick Panel."))
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setWordWrap(True)
        grid_layout.addWidget(self.empty)
        edit = QPushButton(tr("Edit favorites…"), clicked=self.edit)
        edit.setAutoDefault(False)
        grid_layout.addWidget(edit, 0, Qt.AlignRight)
        self.stack.addWidget(page)

        editor = QWidget()
        box = QVBoxLayout(editor)
        box.setContentsMargins(0, 0, 0, 0)
        hint = QLabel(tr("Drag to reorder. The first eight favorites appear in the wheel."))
        hint.setWordWrap(True)
        box.addWidget(hint)
        self.order = QListWidget()
        self.order.setAccessibleName(tr("Favorite tools"))
        self.order.setSelectionMode(QAbstractItemView.SingleSelection)
        self.order.setDragDropMode(QAbstractItemView.InternalMove)
        self.order.setDefaultDropAction(Qt.MoveAction)
        self.order.setDragDropOverwriteMode(False)
        self.order.model().rowsMoved.connect(self.save_order)
        self.order.currentRowChanged.connect(self.update_buttons)
        box.addWidget(self.order)
        commands = QHBoxLayout()
        self.up = self.tool_button(commands, "go-up", tr("Move up"), lambda: self.move_favorite(-1))
        self.down = self.tool_button(commands, "go-down", tr("Move down"), lambda: self.move_favorite(1))
        self.remove = self.tool_button(commands, "list-remove", tr("Remove from favorites"), self.remove_tool)
        commands.addStretch()
        done = QPushButton(tr("Done"), clicked=self.finish_editing)
        done.setAutoDefault(False)
        commands.addWidget(done)
        box.addLayout(commands)
        add_row = QHBoxLayout()
        self.available = QComboBox()
        self.available.setAccessibleName(tr("Available tools"))
        self.available.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.available.setMinimumContentsLength(10)
        add_row.addWidget(self.available, 1)
        self.add = QPushButton(tr("Add"), clicked=self.add_tool)
        self.add.setAutoDefault(False)
        add_row.addWidget(self.add)
        box.addLayout(add_row)
        self.stack.addWidget(editor)

    def tool_button(self, layout, icon, name, call):
        button = QToolButton()
        fallback = {"go-up": QStyle.SP_ArrowUp, "go-down": QStyle.SP_ArrowDown, "list-remove": QStyle.SP_DialogDiscardButton}
        button.setIcon(QIcon.fromTheme(icon, self.style().standardIcon(fallback[icon])))
        button.setAccessibleName(name)
        button.setToolTip(name)
        button.clicked.connect(call)
        layout.addWidget(button)
        return button

    def present(self, favorites, hidden):
        self.keys = list(dict.fromkeys(k for k in favorites if k in ACTIONS and k not in hidden and k != "quick-panel"))
        self.hidden_tools = set(hidden)
        screen = QGuiApplication.screenAt(QCursor.pos()) or self.screen()
        self.setScreen(screen)
        area = screen.availableGeometry()
        width = min(490, area.width())
        columns = min(3, max(1, (width - 36) // 120))
        height = self.grid.tile_height()
        rows = max(2, math.ceil(len(self.keys) / columns))
        self.resize(width, min(round(area.height() * .8), rows * height + 90))
        self.finish_editing()
        self.move(area.center() - self.rect().center())
        self.show()
        self.raise_()
        self.activateWindow()
        if self.keys:
            self.grid.setFocus(Qt.ShortcutFocusReason)

    @staticmethod
    def entry(key):
        icon = QIcon.fromTheme(ACTIONS[key].icon, QApplication.style().standardIcon(QStyle.SP_FileIcon))
        item = QListWidgetItem(icon, ACTIONS[key].name)
        item.setData(Qt.UserRole, key)
        item.setToolTip(ACTIONS[key].name)
        return item

    def finish_editing(self):
        selected = self.order.currentItem() or self.grid.currentItem()
        key = selected.data(Qt.UserRole) if selected else None
        self.stack.setCurrentIndex(0)
        self.grid.clear()
        for tool in self.keys:
            self.grid.addItem(self.entry(tool))
        self.grid.setVisible(bool(self.keys))
        self.empty.setVisible(not self.keys)
        if self.keys:
            self.grid.setCurrentRow(self.keys.index(key) if key in self.keys else 0)
            self.grid.setFocus(Qt.ShortcutFocusReason)

    def edit(self):
        item = self.grid.currentItem()
        row = self.grid.currentRow() if item else 0
        self.order.clear()
        for tool in self.keys:
            entry = self.entry(tool)
            entry.setFlags(entry.flags() & ~Qt.ItemIsDropEnabled)
            self.order.addItem(entry)
        self.stack.setCurrentIndex(1)
        self.order.setCurrentRow(row)
        self.update_available()
        self.update_buttons()
        (self.order if self.keys else self.available).setFocus(Qt.ShortcutFocusReason)

    def update_available(self):
        selected = self.available.currentData()
        self.available.clear()
        for key in sorted(ACTIONS, key=lambda k: ACTIONS[k].name.casefold()):
            if key != "quick-panel" and key not in self.hidden_tools and key not in self.keys:
                self.available.addItem(QIcon.fromTheme(ACTIONS[key].icon), ACTIONS[key].name, key)
        index = self.available.findData(selected)
        if index >= 0:
            self.available.setCurrentIndex(index)
        can_add = self.available.count() > 0
        self.available.setEnabled(can_add)
        self.add.setEnabled(can_add)

    def update_buttons(self, *_):
        row = self.order.currentRow()
        self.up.setEnabled(row > 0)
        self.down.setEnabled(0 <= row < self.order.count() - 1)
        self.remove.setEnabled(row >= 0)

    def save_order(self, *_):
        self.keys = [self.order.item(i).data(Qt.UserRole) for i in range(self.order.count())]
        self.reordered.emit(self.keys)
        self.update_available()
        self.update_buttons()

    def move_favorite(self, step):
        index = self.order.currentRow()
        target = index + step
        if index >= 0 and 0 <= target < len(self.keys):
            self.order.model().moveRow(QModelIndex(), index, QModelIndex(), target + (step > 0))
            self.order.setCurrentRow(target)

    def add_tool(self):
        key = self.available.currentData()
        if key and key != "quick-panel" and key not in self.keys and key not in self.hidden_tools:
            entry = self.entry(key)
            entry.setFlags(entry.flags() & ~Qt.ItemIsDropEnabled)
            self.order.addItem(entry)
            self.order.setCurrentItem(entry)
            self.save_order()

    def remove_tool(self):
        row = self.order.currentRow()
        if row >= 0:
            self.order.takeItem(row)
            self.save_order()

    def activate(self, item):
        if self.isVisible() and item:
            key = item.data(Qt.UserRole)
            self.hide()
            self.chosen.emit(key)

    def eventFilter(self, obj, event):
        if obj is self.grid and event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            if not event.isAutoRepeat():
                self.activate(self.grid.currentItem())
            return True
        return super().eventFilter(obj, event)

    def reject(self):
        if self.stack.currentIndex() == 1:
            self.finish_editing()
        else:
            self.hide()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.ActivationChange and self.isVisible() and not self.isActiveWindow():
            # A combo menu is its own native window. Let Qt finish the focus transfer.
            QTimer.singleShot(0, self.dismiss_if_inactive)

    def dismiss_if_inactive(self):
        if self.isVisible() and not self.isActiveWindow() and not QApplication.activePopupWidget():
            self.hide()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.dismissed.emit()
