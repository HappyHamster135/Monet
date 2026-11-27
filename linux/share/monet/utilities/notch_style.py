"""Compact, width-aware styling for tools hosted by the island only."""
from shiboken6 import isValid
from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (QAbstractItemView, QBoxLayout, QCheckBox, QComboBox, QFormLayout,
    QLabel, QLayout, QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy,
    QStyle, QTabWidget, QTextEdit, QWidget)

STYLE = """
QWidget { color: #f5f5f7; font-size: 13px; }
QWidget#notchSurface, QScrollArea, QScrollArea > QWidget > QWidget { background: #101011; }
QLabel { background: transparent; }
QLabel[muted="true"] { color: #a2a2ad; font-size: 12px; }
QLineEdit, QTextEdit, QPlainTextEdit, QListWidget, QTreeView, QTableView, QComboBox,
QSpinBox, QDoubleSpinBox { background: #202024; border: 1px solid #303035; border-radius: 9px; padding: 7px; selection-background-color: #455f80; }
QLineEdit:focus, QPlainTextEdit:focus { border-color: #a3ccff; }
QPushButton, QToolButton { background: #27272c; border: 0; border-radius: 10px; padding: 8px 10px; }
QPushButton:hover, QToolButton:hover { background: #36363c; }
QPushButton:pressed, QToolButton:pressed { background: #45454e; }
QPushButton[primary="true"] { background: #c6defb; color: #142338; }
QPushButton:disabled, QToolButton:disabled { color: #85858e; background: #1d1d20; }
QCheckBox { spacing: 7px; padding: 3px 0; }
QSlider::groove:horizontal { height:4px; background:#36363d; border-radius:2px; }
QSlider::sub-page:horizontal { background:#c6defb; border-radius:2px; }
QSlider::handle:horizontal { width:14px; margin:-5px 0; background:#f5f5f7; border-radius:7px; }
QListWidget::item { padding: 8px; border-radius: 7px; }
QListWidget::item:selected { background: #34343c; }
QListWidget#emojiGrid { border: 0; background: transparent; padding: 0; }
QScrollBar:vertical { background: transparent; width: 5px; margin: 0; }
QScrollBar::handle:vertical { background: #44444c; min-height: 24px; border-radius: 2px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QGroupBox { border: 1px solid #303035; border-radius: 10px; margin-top: 9px; padding: 12px 8px 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; }
QTabWidget::pane { border: 0; background: #101011; }
QTabBar::tab { background: #202024; color: #b5b5bf; padding: 7px; border-radius: 8px; }
QTabBar::tab:selected { background: #34343c; color: #f5f5f7; }
"""


def style_surface(surface):
    surface.setObjectName("notchSurface")
    font = QFont(surface.font())
    font.setPixelSize(13)
    surface.setFont(font)
    surface.setStyleSheet(STYLE)


class ResponsiveTool(QObject):
    """Reflow desktop rows before constraining their width, never scale the text."""
    def __init__(self, widget, scroll):
        super().__init__(widget)
        self.widget, self.scroll = widget, scroll
        self.rows = []
        self.labels = []
        self.checks = {}
        self.nested = []
        self.prepared = set()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.fit)
        self.prepare(widget)
        scroll.viewport().installEventFilter(self)
        widget.installEventFilter(self)
        self.timer.start(0)

    def prepare(self, widget):
        if widget in self.prepared:
            return
        self.prepared.add(widget)
        if self.widget.property("notchInline"): widget.setProperty("notchInline",True)
        widget.setMinimumWidth(0)
        if isinstance(widget, QLabel):
            widget.setWordWrap(True)
            if not self.widget.property('settingsDesigned'):
                widget.setTextInteractionFlags(widget.textInteractionFlags() | Qt.TextSelectableByMouse)
            widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            self.labels.append(widget)
        elif isinstance(widget, QCheckBox):
            widget.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
            self.checks[widget] = (widget.text(), widget.text())
        elif isinstance(widget, (QLineEdit, QComboBox, QAbstractItemView, QPlainTextEdit, QTextEdit)):
            widget.setSizePolicy(QSizePolicy.Ignored, widget.sizePolicy().verticalPolicy())
        if isinstance(widget, (QPlainTextEdit, QTextEdit)):
            widget.setMinimumHeight(80)
            widget.setMaximumHeight(150)
            widget.setLineWrapMode(QPlainTextEdit.WidgetWidth if isinstance(widget, QPlainTextEdit) else QTextEdit.WidgetWidth)
        if isinstance(widget, QAbstractItemView):
            widget.setMinimumHeight(100)
            widget.setMaximumHeight(190)
            widget.setTextElideMode(Qt.ElideRight)
        if isinstance(widget, QTabWidget):
            widget.tabBar().setExpanding(False)
            widget.tabBar().setElideMode(Qt.ElideRight)
            widget.currentChanged.connect(lambda *_: self.timer.start(0))
            for index in range(widget.count()):
                self.prepare(widget.widget(index))
        if isinstance(widget, QScrollArea) and widget.widget():
            self.prepare(widget.widget())
            widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            widget.setFrameShape(QScrollArea.NoFrame)
            self.nested.append(widget)
        layout = widget.layout()
        if layout:
            if not self.widget.property('settingsDesigned'):layout.setContentsMargins(6, 6, 6, 6)
            self.prepare_layout(layout)

    def prepare_layout(self, layout):
        if not self.widget.property('settingsDesigned'):layout.setSpacing(8)
        layout.setSizeConstraint(QLayout.SetNoConstraint)
        layout.setAlignment(Qt.AlignTop)
        if isinstance(layout, QBoxLayout) and layout.direction() in (QBoxLayout.LeftToRight, QBoxLayout.RightToLeft):
            self.rows.append((layout, layout.direction()))
        if isinstance(layout, QFormLayout):
            layout.setRowWrapPolicy(QFormLayout.WrapAllRows)
            layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item.widget():
                self.prepare(item.widget())
            elif item.layout():
                self.prepare_layout(item.layout())

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Resize, QEvent.Show, QEvent.LayoutRequest) and not self.timer.isActive():
            self.timer.start(0)
        return False

    def fit(self):
        if self.scroll.widget() is not self.widget:
            return
        self.prepared = {widget for widget in self.prepared if isValid(widget)}
        # Sub-editors and hardware rows may be added after the first visit.
        for child in self.widget.findChildren(QWidget):
            if child not in self.prepared: self.prepare(child)
        self.labels = [label for label in self.labels if isValid(label)]
        self.rows = [(layout,direction) for layout,direction in self.rows if isValid(layout)]
        self.checks = {check:value for check,value in self.checks.items() if isValid(check)}
        width = max(40, self.scroll.viewport().width())
        if hasattr(self.widget, "set_notch_width"):
            self.widget.set_notch_width(width)
        # Start from natural control widths, not the already compressed geometry.
        for layout, direction in self.rows:
            natural = sum(max(item.minimumSize().width(),
                              item.widget().minimumSizeHint().width() if item.widget() else 0)
                          for item in (layout.itemAt(i) for i in range(layout.count())))
            natural += max(0, layout.count()-1) * layout.spacing()
            layout.setDirection(QBoxLayout.TopToBottom if natural > width-28 else direction)
        self.widget.setFixedWidth(width)
        layout = self.widget.layout()
        if layout:
            layout.activate()
            for checkbox, (original, previous) in list(self.checks.items()):
                if checkbox.text() != previous:
                    original = checkbox.text()
                metrics = QFontMetrics(checkbox.font())
                indicator = checkbox.style().pixelMetric(QStyle.PM_IndicatorWidth,None,checkbox)
                available = max(40, min(width-28, checkbox.width()-indicator-16))
                lines = []
                for paragraph in original.split("\n"):
                    line = ""
                    for word in paragraph.split():
                        candidate = (line + " " + word).strip()
                        if line and metrics.horizontalAdvance(candidate.replace("&", "")) > available:
                            lines.append(line)
                            line = word
                        else:
                            line = candidate
                    lines.append(line)
                wrapped = "\n".join(lines)
                if checkbox.text() != wrapped:
                    checkbox.setText(wrapped)
                checkbox.setMinimumHeight(max(22, len(lines)*metrics.lineSpacing()+6))
                self.checks[checkbox] = (original, wrapped)
            for label in self.labels:
                if label.isVisibleTo(self.widget):
                    # A scroll area's resizable child can squeeze wrapped
                    # labels below their height-for-width. Preserve those lines
                    # and let the *page* scroll instead of drawing over them.
                    label.setMinimumHeight(max(0, label.heightForWidth(max(1, label.width()))))
            for nested in self.nested:
                content = nested.widget()
                content.setFixedWidth(max(40, nested.viewport().width()))
                if content.layout():
                    content.setMinimumHeight(max(content.layout().minimumSize().height(),
                                                 content.layout().heightForWidth(content.width())))
                    # Embedded forms share the island's vertical scroll area.
                    # Avoid a second tiny scrolling viewport inside the page.
                    nested.setMinimumHeight(content.minimumHeight()+2*nested.frameWidth())
            # Geometry setters already invalidate changed layouts. Doing it
            # unconditionally here would post another LayoutRequest and keep
            # this zero-delay fit timer running even when the page is idle.
            height = max(layout.minimumSize().height(), layout.heightForWidth(width))
            self.widget.setMinimumHeight(max(0, height))
            layout.activate()
