"""Optional picture edits for the compression queue."""
import json
import os
from pathlib import Path
import signal
import sys
import tempfile

from PySide6.QtCore import QProcess, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QImageReader, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from actions import tr
from picture_edit import picture_geometry


class PictureOptions(QDialog):
    def __init__(self, parent, entry, suffix, options, edge):
        super().__init__(parent)
        self.setWindowTitle(tr("Picture options"))
        self.entry, self.suffix, self.edge = entry, suffix, edge
        self.temp = None
        self.job = None
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        sizes = self.form(tr("Size"))
        self.size_mode = self.combo(sizes, tr("Resize"), [
            ("", tr("Use longest edge")), ("width", tr("Set width")), ("height", tr("Set height")),
            ("exact", tr("Exact dimensions"))], options.get("size", ""))
        self.width_px = self.number(sizes, tr("Width"), 1, 32768, options.get("width", min(entry.info["width"], 32768)), " px")
        self.height_px = self.number(sizes, tr("Height"), 1, 32768, options.get("height", min(entry.info["height"], 32768)), " px")
        self.framing = self.combo(sizes, tr("Frame"), [
            ("fit", tr("Fit with padding")), ("fill", tr("Crop to fill")), ("stretch", tr("Stretch to fit"))],
            options.get("framing", "fit"))
        self.size_mode.currentIndexChanged.connect(lambda: self.update_size_rows(sizes))
        self.update_size_rows(sizes)
        marks = self.form(tr("Watermark"))
        self.text = QLineEdit(options.get("text", ""))
        self.text.setMaxLength(100)
        marks.addRow(tr("Text"), self.text)
        logo_row = QWidget()
        row = QHBoxLayout(logo_row)
        row.setContentsMargins(0, 0, 0, 0)
        self.logo = options.get("logo", "")
        self.logo_button = QPushButton()
        self.logo_button.clicked.connect(self.choose_logo)
        row.addWidget(self.logo_button, 1)
        self.clear_logo = QPushButton(tr("Remove"))
        self.clear_logo.clicked.connect(lambda: self.set_logo(""))
        row.addWidget(self.clear_logo)
        marks.addRow(tr("Logo"), logo_row)
        self.set_logo(self.logo)
        self.position = self.combo(marks, tr("Position"), [
            ("top-left", tr("Top left")), ("top-right", tr("Top right")), ("center", tr("Center")),
            ("bottom-left", tr("Bottom left")), ("bottom-right", tr("Bottom right"))], options.get("position", "bottom-right"))
        self.opacity = self.number(marks, tr("Opacity"), 1, 100, options.get("opacity", 55), "%")
        self.scale = self.number(marks, tr("Watermark width"), 1, 100, options.get("scale", 25), "%")
        self.margin = self.number(marks, tr("Margin"), 0, 4096, options.get("margin", 16), " px")
        self.preview_button = QPushButton(tr("Preview picture"))
        self.preview_button.clicked.connect(self.preview)
        layout.addWidget(self.preview_button)
        self.sample = QLabel()
        self.sample.setTextFormat(Qt.PlainText)
        self.sample.setAlignment(Qt.AlignCenter)
        self.sample.setWordWrap(True)
        self.preview_tab = self.tabs.addTab(self.sample, tr("Preview"))
        self.tabs.setTabVisible(self.preview_tab, False)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.reset_button = buttons.button(QDialogButtonBox.Reset)
        self.reset_button.clicked.connect(self.reset)
        layout.addWidget(buttons)
        self.finished.connect(self.stop_preview)
        for field in (self.size_mode, self.framing, self.position):
            field.currentIndexChanged.connect(self.hide_preview)
        for field in (self.width_px, self.height_px, self.opacity, self.scale, self.margin):
            field.valueChanged.connect(self.hide_preview)
        self.text.textChanged.connect(self.hide_preview)
        self.resize(max(360, self.sizeHint().width()), self.sizeHint().height())

    def form(self, label):
        page = QWidget()
        self.tabs.addTab(page, label)
        form = QFormLayout(page)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        return form

    def combo(self, form, label, choices, value):
        box = QComboBox()
        for key, text in choices:
            box.addItem(text, key)
        box.setCurrentIndex(max(0, box.findData(value)))
        form.addRow(label, box)
        return box

    def number(self, form, label, low, high, value, suffix):
        field = QSpinBox()
        field.setRange(low, high)
        field.setValue(value)
        field.setSuffix(suffix)
        form.addRow(label, field)
        return field

    def update_size_rows(self, form):
        mode = self.size_mode.currentData()
        form.setRowVisible(self.width_px, mode in ("exact", "width"))
        form.setRowVisible(self.height_px, mode in ("exact", "height"))
        form.setRowVisible(self.framing, mode == "exact")

    def choose_logo(self):
        filename, _ = QFileDialog.getOpenFileName(self, tr("Choose a watermark image"))
        if filename:
            self.set_logo(filename)

    def set_logo(self, path):
        self.logo = path
        label = self.logo_button.fontMetrics().elidedText(Path(path).name, Qt.ElideMiddle, 220) if path else tr("Choose image…")
        self.logo_button.setText(label)
        self.logo_button.setToolTip(path)
        self.clear_logo.setVisible(bool(path))
        if hasattr(self, "sample"):
            self.hide_preview()

    def reset(self):
        self.size_mode.setCurrentIndex(0)
        self.framing.setCurrentIndex(0)
        self.width_px.setValue(self.entry.info["width"])
        self.height_px.setValue(self.entry.info["height"])
        self.text.clear()
        self.set_logo("")
        self.position.setCurrentIndex(self.position.findData("bottom-right"))
        self.opacity.setValue(55)
        self.scale.setValue(25)
        self.margin.setValue(16)

    def values(self):
        mode = self.size_mode.currentData()
        options = {}
        if mode:
            options.update(size=mode)
            if mode in ("exact", "width"):
                options["width"] = self.width_px.value()
            if mode in ("exact", "height"):
                options["height"] = self.height_px.value()
            if mode == "exact":
                options["framing"] = self.framing.currentData()
        if self.text.text().strip() or self.logo:
            options.update(text=self.text.text().strip(), logo=self.logo, position=self.position.currentData(),
                           margin=self.margin.value(), scale=self.scale.value(), opacity=self.opacity.value())
        return options

    def hide_preview(self):
        self.tabs.setTabVisible(self.preview_tab, False)

    def error(self, message):
        self.sample.setText(message)
        self.tabs.setTabVisible(self.preview_tab, True)
        self.tabs.setCurrentIndex(self.preview_tab)

    def accept(self):
        try:
            picture_geometry((self.entry.info["width"], self.entry.info["height"]), self.values(), self.edge)
            if self.logo and not Path(self.logo).is_file():
                raise ValueError(tr("Choose an available watermark image."))
        except ValueError as error:
            self.error(str(error))
            return
        super().accept()

    def preview(self):
        if self.job:
            return
        self.temp = tempfile.TemporaryDirectory(prefix="monet-picture-preview-")
        target = Path(self.temp.name) / ("preview" + self.suffix)
        job = QProcess(self)
        self.job = job
        job.setUnixProcessParameters(QProcess.UnixProcessFlag.CreateNewSession)
        self.preview_button.setEnabled(False)
        self.reset_button.setEnabled(False)
        self.tabs.setEnabled(False)
        self.error(tr("Preparing preview…"))
        def finish(ok):
            if self.job is not job:
                return
            self.job = None
            self.preview_button.setEnabled(True)
            self.reset_button.setEnabled(True)
            self.tabs.setEnabled(True)
            reader = QImageReader(str(target), b"png")
            image = reader.read() if ok else None
            if image and not image.isNull():
                self.sample.setText("")
                self.show_picture(image)
            else:
                self.error(bytes(job.readAllStandardError()).decode(errors="replace").strip() or tr("Couldn’t preview this picture."))
            self.temp.cleanup()
            self.temp = None
            job.deleteLater()
        job.finished.connect(lambda code, status: finish(code == 0 and status == QProcess.NormalExit))
        job.errorOccurred.connect(lambda e: finish(False) if e == QProcess.FailedToStart else None)
        worker = Path(__file__).with_name("media_compress.py")
        job.start("nice", ["-n", "12", sys.executable, str(worker), "preview", str(self.entry.path),
                          str(target), "1", str(self.edge), "0", "0", "--source-info"])
        job.write(json.dumps(dict(self.entry.info, picture_options=self.values())).encode())
        job.closeWriteChannel()

    def show_picture(self, image):
        bounds = QSize(min(400, max(150, self.width() - 28)), 180)
        size = image.size().scaled(bounds, Qt.KeepAspectRatio).expandedTo(QSize(1, 1))
        ratio = self.devicePixelRatioF()
        pixmap = QPixmap(size * ratio)
        pixmap.setDevicePixelRatio(ratio)
        base = self.palette().color(QPalette.Base)
        pixmap.fill(base)
        painter = QPainter(pixmap)
        if image.hasAlphaChannel():
            tile = QPixmap(16, 16)
            tile.fill(base)
            ink = QColor(self.palette().color(QPalette.Text))
            ink.setAlpha(32)
            checker = QPainter(tile)
            checker.fillRect(0, 0, 8, 8, ink)
            checker.fillRect(8, 8, 8, 8, ink)
            checker.end()
            painter.fillRect(0, 0, size.width(), size.height(), QBrush(tile))
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawImage(QRectF(0, 0, size.width(), size.height()), image)
        painter.end()
        self.sample.setPixmap(pixmap)

    def stop_preview(self):
        job = self.job
        if job:
            self.job = None
            try:
                if job.processId():
                    os.killpg(job.processId(), signal.SIGKILL)
            except ProcessLookupError:
                pass
            job.kill()
            job.waitForFinished(2000)
            job.deleteLater()
        if self.temp:
            self.temp.cleanup()
            self.temp = None
