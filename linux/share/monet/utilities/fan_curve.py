"""Temperature curves with linked pointer and keyboard editing."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPalette, QPen, QPolygonF
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
                               QSpinBox, QTableWidget, QVBoxLayout, QWidget)

from actions import tr
from fan_control import curve_points


class CurvePlot(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.drag = None
        self.setMinimumHeight(114)
        self.setAccessibleName(tr("Fan speed by temperature"))
        self.setToolTip(tr("Drag a point or edit its values in the table."))

    @property
    def editor(self):
        return self.parentWidget()

    def bounds(self):
        points = self.editor.points()
        sensor = self.editor.sensors.get(self.editor.sensor.currentData())
        low = max(sensor.minimum, 20) if sensor else 20
        high = min(sensor.maximum, 100) if sensor else 100
        return min([low] + [p[0] for p in points]), max([high, low + 1] + [p[0] for p in points])

    def area(self):
        return QRectF(46, 10, max(1, self.width() - 64), max(1, self.height() - 36))

    def position(self, point, limits):
        area = self.area()
        low, high = limits
        return QPointF(area.left() + (point[0] - low) / (high - low) * area.width(),
                       area.bottom() - point[1] / 100 * area.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        area = self.area()
        limits = self.drag[1] if self.drag else self.bounds()
        palette = self.palette()
        for value in (0, 50, 100):
            y = self.position((limits[0], value), limits).y()
            painter.setPen(palette.color(QPalette.Mid))
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            painter.setPen(palette.color(QPalette.WindowText))
            painter.drawText(QRectF(0, y - 10, area.left() - 6, 20), Qt.AlignRight | Qt.AlignVCenter, f"{value}%")
        for edge, alignment in zip(limits, (Qt.AlignLeft, Qt.AlignRight)):
            painter.drawText(QRectF(area.left(), area.bottom() + 2, area.width(), 22),
                             alignment | Qt.AlignVCenter, f"{edge:g} °C")
        vertices = [self.position(point, limits) for point in self.editor.points()]
        color = palette.color(QPalette.Highlight)
        background = palette.color(QPalette.Window)
        if abs(color.lightnessF() - background.lightnessF()) < .35:
            color = palette.color(QPalette.Link)
        if abs(color.lightnessF() - background.lightnessF()) < .35:
            color = palette.color(QPalette.WindowText)
        painter.setPen(QPen(color, 2))
        painter.drawPolyline(QPolygonF(vertices))
        for i, pt in enumerate(vertices):
            painter.setBrush(color if self.editor.table.currentRow() == i else palette.color(QPalette.Base))
            painter.drawEllipse(pt, 4.5, 4.5)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or not self.editor.sensor.currentData():
            return
        limits = self.bounds()
        for i, point in enumerate(self.editor.points()):
            if (self.position(point, limits) - event.position()).manhattanLength() <= 14:
                self.drag = i, limits
                self.editor.table.selectRow(i)
                self.update()
                return

    def mouseMoveEvent(self, event):
        if not self.drag:
            return
        i, (low, high) = self.drag
        area = self.area()
        points = self.editor.points()
        sensor = self.editor.sensors[self.editor.sensor.currentData()]
        t = round(low + (event.position().x() - area.left()) / area.width() * (high - low), 1)
        percent = round((area.bottom() - event.position().y()) / area.height() * 100)
        t_min = points[i - 1][0] + .1 if i else sensor.minimum
        t_max = points[i + 1][0] - .1 if i + 1 < len(points) else sensor.maximum
        if t_min <= t_max:
            self.editor.table.cellWidget(i, 0).setValue(max(t_min, min(t, t_max)))
        minimum = points[i - 1][1] if i else 0
        maximum = points[i + 1][1] if i + 1 < len(points) else 100
        self.editor.table.cellWidget(i, 1).setValue(max(minimum, min(percent, maximum)))

    def mouseReleaseEvent(self, event):
        self.drag = None
        self.update()


class CurveEditor(QDialog):
    def __init__(self, sensors, profile, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("Temperature curve"))
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(profile.get("name", ""))
        self.name.setMaxLength(50)
        form.addRow(tr("Curve name"), self.name)
        self.sensors = sensors
        self.sensor = QComboBox()
        for key, sensor in sensors.items():
            self.sensor.addItem(sensor.name, key)
        source = profile.get("temp_source") or {}
        if source:
            wanted = (source.get("device_uid"), source.get("temp_name"))
            index = next((i for i, key in enumerate(sensors) if key == wanted), -1)
            self.sensor.setCurrentIndex(index)
        form.addRow(tr("Temperature sensor"), self.sensor)
        layout.addLayout(form)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([tr("Temperature (°C)"), tr("Fan speed (%)")])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.plot = CurvePlot(self)
        layout.addWidget(self.plot)
        self.table.setMaximumHeight(200)
        self.table.setAccessibleName(tr("Curve points"))
        self.table.itemSelectionChanged.connect(self.plot.update)
        self.sensor.currentIndexChanged.connect(self.redraw)
        layout.addWidget(self.table)
        self.resize(490, 550)
        for temp, speed in profile.get("speed_profile") or [(35, 30), (60, 60), (80, 100)]:
            self.add(temp, speed)
        row = QHBoxLayout()
        row.addWidget(QPushButton(tr("Add point"), clicked=self.add_point))
        row.addWidget(QPushButton(tr("Remove point"), clicked=self.remove_point))
        row.addStretch()
        layout.addLayout(row)
        self.message = QLabel()
        self.message.setTextFormat(Qt.PlainText)
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def redraw(self):
        self.plot.update()

    def add(self, temp, speed, i=None):
        if i is None:
            i = self.table.rowCount()
        self.table.insertRow(i)
        t, s = QDoubleSpinBox(), QSpinBox()
        t.setRange(-273.1, 1000)
        t.setDecimals(2)
        t.setValue(temp)
        s.setRange(0, 100)
        s.setValue(speed)
        self.table.setCellWidget(i, 0, t)
        self.table.setCellWidget(i, 1, s)
        t.valueChanged.connect(self.redraw)
        s.valueChanged.connect(self.redraw)
        self.plot.update()

    def add_point(self):
        points = self.points()
        sensor = self.sensors.get(self.sensor.currentData())
        if sensor and len(points) < sensor.max_points:
            row = self.table.currentRow()
            if 0 <= row < len(points) - 1:
                t, s = points[row]
                t2, s2 = points[row + 1]
                self.add((t + t2) / 2, round((s + s2) / 2), row + 1)
                self.table.selectRow(row + 1)
            else:
                t, s = points[-1]
                self.add(t + 5, s)
                self.table.selectRow(len(points))

    def remove_point(self):
        sensor = self.sensors.get(self.sensor.currentData())
        if sensor and self.table.rowCount() > sensor.min_points and self.table.currentRow() >= 0:
            self.table.removeRow(self.table.currentRow())
            self.plot.update()

    def points(self):
        return [[self.table.cellWidget(i, j).value() for j in range(2)] for i in range(self.table.rowCount())]

    def validate(self):
        if not self.name.text().strip() or not self.sensor.currentData():
            self.message.setText(tr("Choose a name and a temperature sensor."))
            return
        try:
            curve_points(self.points(), self.sensors[self.sensor.currentData()])
        except ValueError as error:
            self.message.setText(str(error))
            return
        self.accept()
