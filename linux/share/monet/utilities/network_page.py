"""Live network activity and an on-demand Internet speed test."""
from collections import deque
import time

from PySide6.QtCore import QEvent, QLocale, QPointF, QProcess, Qt, QTimer
from PySide6.QtGui import QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QApplication, QComboBox, QGridLayout, QHBoxLayout,
                               QLabel, QProgressBar, QPushButton, QTabWidget, QVBoxLayout, QWidget)

from actions import tr
from network_activity import SessionTotals, Traffic, connections, rate_text
from speed_test import SpeedTest


class TrafficGraph(QWidget):
    def __init__(self):
        super().__init__()
        self.samples = deque(maxlen=60)
        self.bits = False
        self.setAccessibleName(tr("Download and upload history"))
        self.setMinimumHeight(52)
        self.setMaximumHeight(96)

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect().adjusted(2, 3, -2, -3)
        painter.setPen(self.palette().mid().color())
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        if not self.samples:
            return
        maximum = max(1, max((max(pair) for pair in self.samples if pair), default=0))
        painter.setPen(self.palette().text().color())
        label = rate_text(maximum, self.bits)
        painter.drawText(rect, Qt.AlignLeft | Qt.AlignTop, label)
        rect.setTop(rect.top() + painter.fontMetrics().height() + 2)
        painter.setRenderHint(QPainter.Antialiasing)
        for i, style in ((0, Qt.SolidLine), (1, Qt.DashLine)):
            color = self.palette().link().color() if i == 0 else self.palette().text().color()
            if abs(color.lightnessF() - self.palette().window().color().lightnessF()) < .35:
                color = self.palette().text().color()
            painter.setPen(QPen(color, 2, style))
            path = QPainterPath()
            broken = True
            for column, pair in enumerate(self.samples, start=60-len(self.samples)):
                if pair is None:
                    broken = True
                    continue
                point = QPointF(rect.left() + column * rect.width()/59,
                                rect.bottom() - pair[i] * rect.height()/maximum)
                if broken:
                    path.moveTo(point)
                else:
                    path.lineTo(point)
                broken = False
            painter.drawPath(path)


class NetworkPage(QWidget):
    def __init__(self, window, *, interfaces=connections, speed=None):
        super().__init__()
        self.owner = window
        self.interfaces = interfaces
        self.speed = speed or SpeedTest(self)
        self.traffic = Traffic()
        self.session = SessionTotals()
        self.links = []
        self.rates = {}
        self.graph_device = None
        self.poll = QTimer(self)
        self.poll.setInterval(1000)
        self.poll.timeout.connect(self.sample)
        self.tabs = QTabWidget()
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        activity = QWidget()
        box = QVBoxLayout(activity)
        controls = QHBoxLayout()
        self.interface = QComboBox()
        self.interface.setAccessibleName(tr("Network interface"))
        self.interface.currentIndexChanged.connect(self.choose)
        self.units = QComboBox()
        self.units.setAccessibleName(tr("Traffic speed units"))
        self.units.addItem(tr("Bytes per second"), False)
        self.units.addItem(tr("Bits per second"), True)
        self.units.setCurrentIndex(int(window.settings.value("network/bits", False, type=bool)))
        self.units.currentIndexChanged.connect(self.change_units)
        controls.addWidget(self.interface, 1)
        controls.addWidget(self.units)
        box.addLayout(controls)
        grid = QGridLayout()
        self.down = self.metric(grid, 0, tr("Download"))
        self.up = self.metric(grid, 1, tr("Upload"))
        box.addLayout(grid)
        self.graph = TrafficGraph()
        self.graph.setToolTip(tr("Last minute. Download is solid and upload is dashed."))
        box.addWidget(self.graph, 1)
        self.totals = QLabel()
        self.totals.setWordWrap(True)
        ledger = QHBoxLayout()
        self.period = QComboBox()
        self.period.addItem(tr("This session"), "session")
        self.period.addItem(tr("Since device started"), "device")
        self.period.setAccessibleName(tr("Traffic totals period"))
        self.period.setToolTip(tr("Session totals start with the first reading in this login."))
        self.period.currentIndexChanged.connect(self.render_totals)
        ledger.addWidget(self.period)
        ledger.addWidget(self.totals, 1)
        self.reset = QPushButton(tr("Reset totals"))
        self.reset.clicked.connect(self.reset_totals)
        ledger.addWidget(self.reset)
        box.addLayout(ledger)
        addresses = QHBoxLayout()
        self.address = QComboBox()
        self.address.setAccessibleName(tr("Local IP addresses"))
        self.copy = QPushButton(tr("Copy IP"))
        self.copy.clicked.connect(self.copy_address)
        addresses.addWidget(self.address, 1)
        addresses.addWidget(self.copy)
        box.addLayout(addresses)
        manager = QPushButton(tr("Open Task Manager"))
        manager.setToolTip(tr("The Applications page shows download and upload speeds for each app."))
        manager.clicked.connect(self.open_manager)
        box.addWidget(manager, 0, Qt.AlignRight)
        self.tabs.addTab(activity, tr("Traffic"))

        test = QWidget()
        form = QVBoxLayout(test)
        hint = QLabel(tr("Measure this PC’s connection to Cloudflare. The test can transfer up to 100 MB in each direction and uses the system’s network route."))
        hint.setWordWrap(True)
        form.addWidget(hint)
        readings = QGridLayout()
        self.measures = {key: self.metric(readings, column, title) for column, (key, title) in enumerate((
            ("latency", tr("HTTP latency")), ("download", tr("Download speed")), ("upload", tr("Upload speed"))))}
        form.addSpacing(12)
        form.addLayout(readings)
        self.progress = QProgressBar()
        self.progress.setRange(0, 3)
        self.progress.setTextVisible(False)
        self.progress.setAccessibleName(tr("Speed test"))
        form.addWidget(self.progress)
        actions = QHBoxLayout()
        self.notice = QLabel()
        self.notice.setWordWrap(True)
        self.notice.setTextFormat(Qt.PlainText)
        actions.addWidget(self.notice, 1)
        self.test_button = QPushButton()
        self.test_button.clicked.connect(self.toggle_test)
        actions.addWidget(self.test_button)
        form.addLayout(actions)
        form.addStretch()
        self.tabs.addTab(test, tr("Speed test"))
        self.speed.changed.connect(self.test_changed)
        self.test_changed()
        self.tabs.currentChanged.connect(self.sync_activity)
        window.installEventFilter(self)

    @staticmethod
    def metric(grid, column, title):
        grid.addWidget(QLabel(title), 0, column)
        value = QLabel("—")
        font = value.font()
        font.setPointSizeF(font.pointSizeF() * 1.35)
        font.setBold(True)
        value.setFont(font)
        value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        value.setAccessibleName(title)
        grid.addWidget(value, 1, column)
        grid.setColumnStretch(column, 1)
        return value

    def open_manager(self):
        ok, _ = QProcess.startDetached("plasma-systemmonitor", ["--page-id", "monet-applications.page"])
        if not ok:
            self.owner.issue(tr("Could not open Task Manager."))

    def change_units(self):
        self.owner.settings.setValue("network/bits", self.units.currentData())
        self.render()

    def choose(self):
        self.owner.settings.setValue("network/interface", self.interface.currentData() or "")
        self.render()

    def copy_address(self):
        if self.address.currentData():
            QApplication.clipboard().setText(self.address.currentData())
            self.owner.issue(tr("IP address copied."))

    def showEvent(self, event):
        super().showEvent(event)
        self.sync_activity()

    def hideEvent(self, event):
        self.stop_poll()
        self.speed.cancel()
        super().hideEvent(event)

    def eventFilter(self, obj, event):
        if obj is self.owner and event.type() == QEvent.WindowStateChange:
            self.sync_activity()
        return super().eventFilter(obj, event)

    def stop_poll(self):
        self.poll.stop()
        self.session.save()
        self.traffic.last.clear()
        self.graph.samples.clear()
        self.graph_device = None

    def sync_activity(self):
        visible = self.isVisible() and not self.owner.isMinimized()
        if not visible or self.tabs.currentIndex() == 0:
            self.speed.cancel()
        if visible and self.tabs.currentIndex() == 0:
            if not self.poll.isActive():
                self.sample()
                self.poll.start()
        else:
            self.stop_poll()

    def sample(self):
        self.links = self.interfaces()
        self.session.sample(self.links)
        self.rates = self.traffic.sample(self.links, time.monotonic())
        preferred = self.owner.settings.value("network/interface", "") or ""
        items = [(tr("Automatic · {interface}").format(interface=self.links[0].title) if self.links else tr("No active connection"), "")]
        items += [(link.title, link.name) for link in self.links]
        if preferred and not any(name == preferred for _, name in items):
            items.append((tr("{interface} · disconnected").format(interface=preferred), preferred))
        if items != [(self.interface.itemText(i), self.interface.itemData(i)) for i in range(self.interface.count())]:
            self.interface.blockSignals(True)
            self.interface.clear()
            for title, name in items:
                self.interface.addItem(title, name)
            self.interface.setCurrentIndex(self.interface.findData(preferred))
            self.interface.blockSignals(False)
        self.render(append=True)

    def selected_link(self):
        preferred = self.interface.currentData()
        if preferred:
            return next((item for item in self.links if item.name == preferred), None)
        return next(iter(self.links), None)

    def reset_totals(self):
        link = self.selected_link()
        if link and link.received is not None and link.sent is not None:
            self.session.reset(link)
            self.render_totals()

    def render_totals(self):
        link = self.selected_link()
        session = self.period.currentData() == "session"
        self.reset.setVisible(session)
        available = link is not None and link.received is not None and link.sent is not None
        self.reset.setEnabled(available)
        if available:
            rx, tx = self.session.devices[link.name][-2:] if session else (link.received, link.sent)
            locale = QLocale()
            self.totals.setText(tr("{down} received · {up} sent").format(
                down=locale.formattedDataSize(rx), up=locale.formattedDataSize(tx)))
        else:
            self.totals.setText(tr("Traffic totals are unavailable."))

    def render(self, append=False):
        link = self.selected_link()
        key = (link.name, link.index) if link else None
        if key != self.graph_device:
            self.graph.samples.clear()
            self.graph_device = key
        rate = self.rates.get(link.name) if link else None
        self.down.setText(rate_text(rate[0] if rate else None, self.units.currentData()))
        self.up.setText(rate_text(rate[1] if rate else None, self.units.currentData()))
        if append:
            self.graph.samples.append(rate)
        self.graph.bits = self.units.currentData()
        self.graph.update()
        self.render_totals()
        ips = list(link.addresses) if link else []
        if ips != [self.address.itemData(i) for i in range(self.address.count()) if self.address.itemData(i)] or not self.address.count():
            selected = self.address.currentData()
            self.address.clear()
            for ip in ips:
                self.address.addItem(ip, ip)
            if not ips:
                self.address.addItem(tr("No local IP address"), "")
            self.address.setCurrentIndex(max(0, self.address.findData(selected or "")))
        self.address.setEnabled(bool(ips))
        self.copy.setEnabled(bool(ips))

    def toggle_test(self):
        if self.speed.running:
            self.speed.cancel()
        else:
            self.speed.start()

    def test_changed(self):
        s = self.speed
        messages = {"idle": "", "latency": tr("Measuring latency…"), "download": tr("Measuring download speed…"),
                    "upload": tr("Measuring upload speed…"), "done": tr("Test complete."), "failed": s.error,
                    "cancelled": tr("Test cancelled.")}
        self.notice.setText(messages[s.phase])
        self.progress.setVisible(s.running or s.phase == "done")
        self.progress.setValue({"latency": 0, "download": 1, "upload": 2, "done": 3}.get(s.phase, 0))
        self.test_button.setText(tr("Cancel test") if s.running else tr("Run speed test"))
        for key, label in self.measures.items():
            result = s.results.get(key)
            value = "—"
            if result is not None:
                value = QLocale().toString(result, "f", 1) + (" ms" if key == "latency" else " Mbit/s")
            label.setText(value)
