"""Monitor reported speeds and change one controller channel at a time."""
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, Qt, QThreadPool, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog,
                               QFormLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from actions import tr
from fan_control import AccessNeeded, Controller, ControllerError, Offline, cooling_status, hardware_fans
from fan_curve import CurveEditor


class FanUpdates(QObject):
    completed = Signal(object, object)
    measured = Signal(int, object)


class Fans(QWidget):
    def __init__(self, controller=None, sensors=hardware_fans):
        super().__init__()
        self.api = controller or Controller()
        self.read_hw = sensors
        self.channels, self.sensors, self.profiles, self.names = {}, {}, {}, {}
        self.connected = self.busy = False
        self.applied_mode, self.applied_duty = "", None
        self.updates = FanUpdates()
        self.updates.completed.connect(self.finish, Qt.QueuedConnection)
        self.updates.measured.connect(self.finish_readings, Qt.QueuedConnection)
        self.reading = False
        self.generation = 0
        box = QVBoxLayout(self)
        self.table = QTableWidget(0, 5)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalHeaderLabels([tr("Fan"), tr("Speed"), tr("Target RPM"), tr("Driver mode"), tr("Fan duty")])
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        box.addWidget(self.table)
        self.controls = QWidget()
        form = QFormLayout(self.controls)
        form.setContentsMargins(0, 0, 0, 0)
        self.fan = QComboBox()
        self.fan.currentIndexChanged.connect(self.select_fan)
        form.addRow(tr("Control fan"), self.fan)
        self.mode = QComboBox()
        self.mode.currentIndexChanged.connect(self.editing)
        form.addRow(tr("Cooling mode"), self.mode)
        self.duty = QSpinBox()
        self.duty.setSuffix("%")
        self.duty.valueChanged.connect(self.editing)
        self.duty_line = QLabel(tr("Fan speed"))
        form.addRow(self.duty_line, self.duty)
        buttons = QHBoxLayout()
        self.apply = QPushButton(tr("Apply"), clicked=self.apply_setting)
        self.new = QPushButton(tr("New curve…"), clicked=self.new_curve)
        self.edit = QPushButton(tr("Edit curve…"), clicked=self.change_curve)
        for button in (self.apply, self.new, self.edit):
            buttons.addWidget(button)
        buttons.addStretch()
        form.addRow(buttons)
        box.addWidget(self.controls)
        self.controls.hide()
        self.message = QLabel()
        self.message.setTextFormat(Qt.PlainText)
        self.message.setWordWrap(True)
        box.addWidget(self.message)
        footer = QHBoxLayout()
        self.retry = QPushButton(tr("Refresh"), clicked=self.reload)
        self.unlock = QPushButton(tr("Use access token…"), clicked=self.enter_token)
        self.guide = QPushButton(tr("Set up fan control…"), clicked=self.open_controller)
        for button in (self.retry, self.unlock, self.guide):
            footer.addWidget(button)
        footer.addStretch()
        box.addLayout(footer)
        box.addStretch()
        self.unlock.hide()
        self.poll = QTimer(self, interval=3000)
        self.poll.timeout.connect(self.readings)

    def showEvent(self, event):
        super().showEvent(event)
        self.poll.start()
        self.reload()

    def hideEvent(self, event):
        self.generation += 1
        self.poll.stop()
        super().hideEvent(event)

    def task(self, read, done):
        if self.busy:
            return
        self.busy = True
        self.generation += 1
        self.controls.setEnabled(False)
        self.retry.setEnabled(False)
        self.unlock.setEnabled(False)
        def work():
            try:
                value = read()
            except Exception as error:
                value = error
            self.updates.completed.emit(done, value)
        QThreadPool.globalInstance().start(work)

    @Slot(object, object)
    def finish(self, done, value):
        self.busy = False
        self.controls.setEnabled(True)
        self.retry.setEnabled(True)
        self.unlock.setEnabled(True)
        if isinstance(value, Exception):
            if isinstance(value, (Offline, AccessNeeded)):
                self.disconnected(value)
            else:
                self.message.setText(str(value))
            return
        done(value)

    def disconnected(self, error):
        self.connected = False
        self.controls.hide()
        self.unlock.setVisible(isinstance(error, AccessNeeded))
        self.guide.setText(tr("Open CoolerControl") if isinstance(error, AccessNeeded) else tr("Set up fan control…"))
        text = str(error)
        if isinstance(error, Offline):
            flag = Path("/sys/module/thinkpad_acpi/parameters/fan_control")
            try:
                firmware = flag.read_text().strip() == "N"
            except OSError:
                firmware = False
            text = (tr("This ThinkPad uses firmware cooling. Its driver reports fan control is disabled.")
                    if firmware else tr("For adjustable fans, connect a local CoolerControl service."))
        self.message.setText(text)

    def reload(self):
        def load():
            hw = self.read_hw()
            try:
                return hw, self.api.catalog()
            except (ControllerError, ValueError, KeyError) as error:
                return hw, error
        def loaded(data):
            hw, catalog = data
            self.show_rows(hw)
            if isinstance(catalog, Exception):
                self.disconnected(catalog)
                return
            self.connected = True
            self.unlock.hide()
            self.guide.setText(tr("Open CoolerControl"))
            last = self.fan.currentData()
            self.channels, self.sensors, self.profiles, self.names = catalog
            self.fan.blockSignals(True)
            self.fan.clear()
            for key, (name, lo, hi) in self.channels.items():
                self.fan.addItem(name, key)
            self.fan.setCurrentIndex(next((i for i, key in enumerate(self.channels) if key == last), 0))
            self.fan.blockSignals(False)
            self.controls.setVisible(bool(self.channels))
            self.message.setText("" if self.channels else tr("CoolerControl reports no adjustable fans."))
            self.select_fan()
        self.task(load, loaded)

    def readings(self):
        if self.reading or self.busy or not self.isVisible() or self.window().isMinimized():
            return
        self.reading = True
        generation, connected = self.generation, self.connected
        channels, names = self.channels, self.names
        def read():
            try:
                hardware = self.read_hw()
                result = cooling_status(self.api, channels, names, hardware) if connected else hardware
            except Exception as error:
                result = error
            self.updates.measured.emit(generation, result)
        QThreadPool.globalInstance().start(read)

    @Slot(int, object)
    def finish_readings(self, generation, result):
        self.reading = False
        if self.generation != generation or not self.isVisible():
            return
        if isinstance(result, (Offline, AccessNeeded)):
            self.disconnected(result)
        elif isinstance(result, Exception):
            self.message.setText(str(result))
        else:
            self.show_rows(result)

    def show_rows(self, fans):
        self.table.setColumnHidden(2, all(f.target_rpm is None for f in fans))
        self.table.setColumnHidden(3, not any(f.mode for f in fans))
        self.table.setColumnHidden(4, all(f.duty is None for f in fans))
        self.table.clearSpans()
        self.table.setRowCount(len(fans))
        for row, fan in enumerate(fans):
            values = (fan.name, tr("{value} RPM").format(value=fan.rpm) if fan.rpm is not None else "—",
                      str(fan.target_rpm) if fan.target_rpm is not None else "—", fan.mode or "—",
                      f"{fan.duty}%" if fan.duty is not None else "—")
            for col, value in enumerate(values):
                cell = self.table.item(row, col)
                if cell is None:
                    self.table.setItem(row, col, QTableWidgetItem(value))
                elif cell.text() != value:
                    cell.setText(value)
        if not fans:
            self.table.setRowCount(1)
            cell = QTableWidgetItem(tr("No fan speed sensors reported."))
            self.table.setItem(0, 0, cell)
            self.table.setSpan(0, 0, 1, self.table.columnCount())

        height = self.table.horizontalHeader().height() + self.table.frameWidth() * 2
        self.table.setFixedHeight(height + sum(self.table.rowHeight(i) for i in range(min(5, self.table.rowCount()))))

    def select_fan(self):
        key = self.fan.currentData()
        if not key or self.busy:
            return
        self.mode.clear()
        self.editing()

        def selected(setting):
            _, low, high = self.channels[key]
            self.duty.setRange(max(0, low), min(100, high))
            self.mode.blockSignals(True)
            self.mode.clear()
            self.mode.addItem(tr("Hardware default"), "default")
            self.mode.addItem(tr("Fixed speed"), "fixed")
            for uid, profile in self.profiles.items():
                if profile.get("p_type") != "Default":
                    self.mode.addItem(profile["name"], "profile/" + uid)
            current = setting.get("speed_fixed")
            selected = "default"
            uid = setting.get("profile_uid")
            if current is not None:
                selected = "fixed"
            elif uid and self.profiles.get(uid, {}).get("p_type") != "Default":
                selected = "profile/" + uid
            self.applied_mode, self.applied_duty = selected, current
            self.mode.setCurrentIndex(self.mode.findData(selected))
            self.duty.setValue(current if current is not None else max(low, min(50, high)))
            self.mode.blockSignals(False)
            self.editing()
            self.readings()
        self.task(lambda: self.api.settings(key), selected)

    def editing(self):
        mode = self.mode.currentData() or ""
        fixed = mode == "fixed"
        self.duty.setVisible(fixed)
        self.duty_line.setVisible(fixed)
        self.edit.setVisible(self.profiles.get(mode.removeprefix("profile/"), {}).get("p_type") == "Graph")
        self.new.setEnabled(bool(self.sensors))
        self.apply.setEnabled(bool(mode) and (mode != self.applied_mode or (fixed and self.duty.value() != self.applied_duty)))

    def apply_setting(self):
        key, mode = self.fan.currentData(), self.mode.currentData()
        if not key or not mode:
            return
        kind, _, uid = mode.partition("/")
        value = self.duty.value() if kind == "fixed" else uid
        def applied(_):
            self.message.setText(tr("Fan setting applied."))
            self.select_fan()
        self.task(lambda: self.api.apply(key, kind, value), applied)

    def new_curve(self):
        self.edit_curve(False)

    def change_curve(self):
        self.edit_curve(True)

    def edit_curve(self, existing):
        uid = (self.mode.currentData() or "").removeprefix("profile/")
        old = self.profiles[uid] if existing else {}
        dialog = CurveEditor(self.sensors, old, self)
        try:
            if dialog.exec() != QDialog.Accepted:
                return
            source, temp = dialog.sensor.currentData()
            graph = dict(old, uid=old.get("uid", str(uuid4())), name=dialog.name.text().strip(), p_type="Graph",
                         function_uid=old.get("function_uid", "0"), speed_profile=dialog.points(),
                         temp_source={"device_uid": source, "temp_name": temp})
        finally:
            dialog.deleteLater()
        if existing and QMessageBox.question(self, tr("Update temperature curve"),
                tr("Save changes for every fan using this curve?")) != QMessageBox.Yes:
            return

        def save():
            live = self.api.request("GET", "/profiles")["profiles"]
            if existing:
                if next((p for p in live if p["uid"] == uid), None) != old:
                    raise ControllerError(tr("This curve changed. Refresh before editing it again."))
            elif any(p["name"].casefold() == graph["name"].casefold() for p in live):
                raise ControllerError(tr("A profile with this name already exists. Refresh to see it."))
            self.api.request("PUT" if existing else "POST", "/profiles", graph)
            profiles = self.api.request("GET", "/profiles")["profiles"]
            profile = next((p for p in profiles if p["uid"] == graph["uid"]), None)
            if profile is None:
                raise ControllerError(tr("This curve changed. Refresh before editing it again."))
            return profile
        def saved(profile):
            new_uid = profile["uid"]
            self.profiles[new_uid] = profile
            index = self.mode.findData("profile/" + new_uid)
            if index < 0:
                self.mode.addItem(graph["name"], "profile/" + new_uid)
                index = self.mode.count() - 1
            self.mode.setItemText(index, graph["name"])
            self.mode.setCurrentIndex(index)
            self.message.setText(tr("Curve updated.") if existing else tr("Curve saved. Choose Apply to use it on this fan."))
        self.task(save, saved)

    def enter_token(self):
        token, ok = QInputDialog.getText(self, tr("Connect to CoolerControl"),
                tr("Enter an access token from CoolerControl → Access Protection."), QLineEdit.Password)
        if ok and token.strip() and token.strip().isascii() and token.strip().isprintable():
            self.api.token = token.strip()
            self.reload()

    def open_controller(self):
        import shutil
        from PySide6.QtCore import QProcess
        path = shutil.which("coolercontrol")
        if path and QProcess.startDetached(path, [])[0]:
            return
        url = ("http://127.0.0.1:11987/" if self.connected or self.unlock.isVisible()
               else "https://docs.coolercontrol.org/installation/fedora")
        QDesktopServices.openUrl(QUrl(url))
