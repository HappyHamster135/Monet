"""Position and time one overlay against a frame from the user's recording."""
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                               QSizePolicy, QSpinBox, QVBoxLayout, QWidget)

from actions import tr
from recording_layers import composed, read_image


class Placement(QWidget):
    def __init__(self, dialog, frame, source_size):
        super().__init__()
        self.editor = dialog
        self.source_size = source_size
        self.frame = frame.scaled(920, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.drag = None
        self.setMinimumSize(200, 100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(tr("Overlay position and size"))
        self.setAccessibleDescription(tr("Arrow keys move the overlay. Shift and arrow keys resize it."))

    def area(self):
        size = self.source_size.scaled(self.size(), Qt.KeepAspectRatio)
        return QRectF((self.width() - size.width()) / 2, (self.height() - size.height()) / 2,
                      size.width(), size.height())

    def box(self):
        area = self.area()
        x, y, w, h = self.editor.layer.box
        return QRectF(area.left() + x * area.width(), area.top() + y * area.height(),
                      w * area.width(), h * area.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#202020"))
        area = self.area()
        idx = self.editor.index
        layers = [layer for i, layer in enumerate(self.editor.layers)
                  if i == idx or layer.start <= self.editor.position < layer.end]
        size = area.size().toSize().boundedTo(QSize(1000, 600)).expandedTo(QSize(1, 1))
        image = composed(self.frame, size, layers, self.source_size)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawImage(area, image)
        box = self.box()
        painter.setPen(QPen(Qt.black, 3))
        painter.drawRect(box)
        painter.setPen(QPen(Qt.white, 1))
        painter.drawRect(box)
        painter.fillRect(QRectF(box.bottomRight() - QPointF(5, 5), QSize(9, 9)), Qt.white)
        painter.end()

    def change(self, x, y, w, h):
        w, h = max(.02, min(1., w)), max(.02, min(1., h))
        x, y = max(0., min(1. - w, x)), max(0., min(1. - h, y))
        self.editor.layer.box = (x, y, w, h)
        self.update()

    def mousePressEvent(self, event):
        point = event.position()
        if event.button() != Qt.LeftButton or not self.area().contains(point):
            return
        self.setFocus()
        x, y, w, h = self.editor.layer.box
        corner = self.box().bottomRight()
        resizing = abs(corner.x() - point.x()) < 10 and abs(corner.y() - point.y()) < 10
        if not resizing and not self.box().contains(point):
            area = self.area()
            self.change((point.x()-area.x())/area.width() - w/2, (point.y()-area.y())/area.height() - h/2, w, h)
        self.drag = (point, self.editor.layer.box, resizing)
        event.accept()

    def mouseMoveEvent(self, event):
        if not self.drag:
            return
        point, (x, y, w, h), resize = self.drag
        delta = event.position() - point
        dx, dy = delta.x()/self.area().width(), delta.y()/self.area().height()
        if resize:
            self.change(x, y, min(1-x, w+dx), min(1-y, h+dy))
        else:
            self.change(x+dx, y+dy, w, h)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.drag:
            self.mouseMoveEvent(event)
            self.drag = None
            event.accept()

    def keyPressEvent(self, event):
        step = {Qt.Key_Left: (-.01, 0), Qt.Key_Right: (.01, 0),
                Qt.Key_Up: (0, -.01), Qt.Key_Down: (0, .01)}.get(event.key())
        if not step:
            return super().keyPressEvent(event)
        x, y, w, h = self.editor.layer.box
        dx, dy = step
        if event.modifiers() & Qt.ShiftModifier:
            self.change(x, y, min(1-x, w+dx), min(1-y, h+dy))
        else:
            self.change(x+dx, y+dy, w, h)
        event.accept()


class LayerDialog(QDialog):
    def __init__(self, parent, layers, index, frame, source_size, position, duration, existing):
        super().__init__(parent)
        self.setWindowTitle(tr("Edit recording overlay"))
        self.layers = list(layers)
        self.index = index
        self.position = position
        self.layers[index] = replace(layers[index])
        self.removed = False
        self.resize(580, 470)
        layout = QVBoxLayout(self)
        self.canvas = Placement(self, frame, source_size)
        layout.addWidget(self.canvas, 1)
        help_text = QLabel(tr("Drag the box to move it. Drag its lower-right corner to resize."))
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        form = QFormLayout()
        layout.addLayout(form)
        if self.layer.kind == "text":
            self.text = QPlainTextEdit(self.layer.text)
            self.text.setMaximumHeight(58)
            form.addRow(tr("Caption"), self.text)
            self.color = QComboBox()
            for label, color in ((tr("White"), "#ffffff"), (tr("Yellow"), "#ffe164"),
                                 (tr("Pink"), "#ffc4d5"), (tr("Light blue"), "#a6ddff")):
                self.color.addItem(label, color)
            self.color.setCurrentIndex(max(0, self.color.findData(self.layer.color)))
            form.addRow(tr("Text color"), self.color)
            self.text.textChanged.connect(self.art_changed)
            self.color.currentIndexChanged.connect(self.art_changed)
        else:
            if self.layer.kind == "image":
                self.pick = QPushButton(self.layer.text or tr("Choose image…"), clicked=self.choose_image)
                form.addRow(tr("Image"), self.pick)
            self.amount = QSpinBox()
            self.amount.setRange(1, 100)
            self.amount.setSuffix("%")
            self.amount.setValue(self.layer.amount)
            form.addRow(tr("Opacity") if self.layer.kind == "image" else tr("Blur strength"), self.amount)
            self.amount.valueChanged.connect(self.art_changed)
        if len(self.layers) > 1:
            order = QHBoxLayout()
            self.back = QPushButton(tr("Send backward"), clicked=lambda: self.move_layer(-1))
            self.front = QPushButton(tr("Bring forward"), clicked=lambda: self.move_layer(1))
            for button in (self.back, self.front):
                order.addWidget(button)
            order.addStretch()
            form.addRow(tr("Layer order"), order)
            self.update_order_buttons()
        time_row = QHBoxLayout()
        for key, label, value in (("start", tr("Start"), self.layer.start), ("end", tr("End"), self.layer.end)):
            field = QDoubleSpinBox()
            field.setDecimals(3)
            field.setRange(.001 if key == "end" else 0, (duration if key == "end" else duration-1)/1000)
            field.setKeyboardTracking(False)
            field.setSingleStep(.1)
            field.setValue(value/1000)
            field.setSuffix(tr(" s"))
            field.setAccessibleName(label)
            setattr(self, key, field)
            time_row.addWidget(QLabel(label))
            time_row.addWidget(field)
            field.valueChanged.connect(self.timing_changed)
        time_row.addStretch()
        layout.addLayout(time_row)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        if existing:
            self.buttons.addButton(tr("Remove overlay"), QDialogButtonBox.DestructiveRole).clicked.connect(self.remove)
        layout.addWidget(self.buttons)
        self.validate()
        if self.layer.kind == "text":
            self.text.setFocus()
            self.text.selectAll()

    @property
    def layer(self):
        return self.layers[self.index]

    def update_order_buttons(self):
        self.back.setEnabled(self.index > 0)
        self.front.setEnabled(self.index < len(self.layers) - 1)

    def move_layer(self, direction):
        target = self.index + direction
        if 0 <= target < len(self.layers):
            self.layers.insert(target, self.layers.pop(self.index))
            self.index = target
            self.update_order_buttons()
            self.canvas.update()

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Choose overlay image"), "",
                                              tr("Images (*.png *.jpg *.jpeg *.webp)"))
        if not path:
            return
        image = read_image(path)
        if image.isNull():
            self.status.setText(tr("Choose a readable PNG, JPEG or WebP image."))
            return
        self.layers[self.index] = replace(self.layer, image=image, text=Path(path).name)
        self.pick.setText(self.layer.text)
        self.art_changed()

    def art_changed(self, *_):
        if self.layer.kind == "text":
            self.layers[self.index] = replace(self.layer, text=self.text.toPlainText(), color=self.color.currentData())
        else:
            self.layers[self.index] = replace(self.layer, amount=self.amount.value())
        self.validate()
        self.canvas.update()

    def timing_changed(self, *_):
        self.layer.start = round(self.start.value()*1000)
        self.layer.end = round(self.end.value()*1000)
        self.validate()

    def validate(self):
        message = ""
        if self.layer.start >= self.layer.end:
            message = tr("The end must be later than the start.")
        elif self.layer.kind == "text" and not self.layer.text.strip():
            message = tr("Enter the caption to show in the recording.")
        elif self.layer.kind == "image" and self.layer.image.isNull():
            message = tr("Choose an image to place on the recording.")
        self.status.setText(message)
        self.status.setVisible(bool(message))
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(not message)

    def remove(self):
        self.removed = True
        self.accept()
