"""Manage packages in the user's own Homebrew installation."""
import os
import shlex
import signal
import time
from PySide6.QtCore import (QAbstractTableModel, QModelIndex, QProcess, QProcessEnvironment, Qt, QTimer, QUrl)
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QFileDialog, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
                               QTabBar, QTableView, QToolButton, QVBoxLayout, QWidget)
from actions import tr
from brew_packages import Package, TOKEN, locate, package_info, search_results


class PackageTable(QAbstractTableModel):
    def __init__(self, parent):
        super().__init__(parent)
        self.rows = []
        self.columns = (tr("Package"), tr("Installed"), tr("Available"))

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columns)

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.columns[section]
        return None

    def data(self, index, role):
        if not index.isValid():
            return None
        p = self.rows[index.row()]
        if role == Qt.DisplayRole:
            return (p.name, p.installed, p.available)[index.column()]
        if role == Qt.ToolTipRole:
            return p.description or p.name
        return None

    def replace(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()


class BrewPage(QWidget):
    def __init__(self, home):
        super().__init__()
        self.home = home
        self.cli = ""
        self.job = None
        self.applying_action = False
        self.inventory = {}
        self.hits = {}
        self.query = None
        self.loaded = False
        self.last_command = ""
        self.last_scan = 0
        self.view_text = ["", ""]
        self.view_filter = [0, 0]
        self.old_view = 0
        self.log_tail = bytearray()
        self.log_timer = QTimer(self, interval=140, singleShot=True)
        self.log_timer.timeout.connect(self.paint_log)
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.view = QTabBar()
        self.view.addTab(tr("Installed packages"))
        self.view.addTab(tr("Find packages"))
        self.view.setExpanding(False)
        header.addWidget(self.view)
        self.filter = QComboBox()
        header.addWidget(self.filter)
        header.addStretch()
        self.options = QToolButton()
        self.options.setText(tr("Options"))
        self.options.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.options)
        menu.addAction(tr("Choose Homebrew executable…"), self.choose_brew)
        menu.addAction(tr("Use detected Homebrew"), lambda: self.configure(""))
        menu.addSeparator()
        menu.addAction(tr("Homebrew installation guide"), self.guide)
        self.options.setMenu(menu)
        header.addWidget(self.options)
        layout.addLayout(header)
        search = QHBoxLayout()
        self.text = QLineEdit()
        self.text.setClearButtonEnabled(True)
        search.addWidget(self.text, 1)
        self.find = QPushButton(tr("Search"), clicked=self.search)
        search.addWidget(self.find)
        layout.addLayout(search)
        self.model = PackageTable(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in (1, 2):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Interactive)
            self.table.setColumnWidth(i, 100)
        layout.addWidget(self.table, 1)
        self.detail = QLabel()
        self.detail.setTextFormat(Qt.PlainText)
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)
        actions = QHBoxLayout()
        self.install = QPushButton(tr("Install"), clicked=lambda: self.change("install"))
        self.upgrade = QPushButton(tr("Update"), clicked=lambda: self.change("upgrade"))
        self.remove = QPushButton(tr("Remove…"), clicked=lambda: self.change("uninstall"))
        self.info = QPushButton(tr("Details"), clicked=self.details)
        for button in (self.install, self.upgrade, self.remove, self.info):
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        footer = QHBoxLayout()
        self.refresh = QPushButton(tr("Refresh list"), clicked=self.reload)
        self.update = QPushButton(tr("Update Homebrew"), clicked=lambda: self.change("update"))
        self.update.setToolTip(tr("Update Homebrew and its package catalog, then check installed versions."))
        self.all = QPushButton(tr("Update all…"), clicked=lambda: self.change("all"))
        for button in (self.refresh, self.update, self.all):
            footer.addWidget(button)
        footer.addStretch()
        layout.addLayout(footer)
        self.status = QLabel()
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        controls = QHBoxLayout()
        self.setup = QPushButton(tr("Homebrew installation guide"), clicked=self.guide)
        self.show_log = QPushButton(tr("Operation log"))
        self.show_log.setCheckable(True)
        self.copy = QPushButton(tr("Copy command"), clicked=lambda: QApplication.clipboard().setText(self.last_command))
        self.stop = QPushButton(tr("Cancel operation"), clicked=self.cancel)
        for button in (self.setup, self.show_log, self.copy, self.stop):
            controls.addWidget(button)
        controls.addStretch()
        layout.addLayout(controls)
        self.log = QPlainTextEdit(readOnly=True)
        self.log.setMaximumBlockCount(160)
        self.log.setMaximumHeight(95)
        self.log.hide()
        layout.addWidget(self.log)
        self.show_log.toggled.connect(self.log.setVisible)
        self.show_log.toggled.connect(self.paint_log)
        self.table.selectionModel().currentChanged.connect(self.selection)
        self.table.doubleClicked.connect(self.details)
        self.view.currentChanged.connect(self.mode)
        self.filter.currentIndexChanged.connect(self.apply_filter)
        self.text.textChanged.connect(self.apply_filter)
        self.text.returnPressed.connect(self.search)
        self.mode()

    def guide(self):
        QDesktopServices.openUrl(QUrl("https://docs.brew.sh/Homebrew-on-Linux"))

    def choose_brew(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Choose Homebrew executable"), self.cli)
        if path:
            self.configure(path)

    def configure(self, path):
        if self.job:
            return
        self.home.settings.setValue("brewExecutable", path)
        self.home.settings.sync()
        self.loaded = False
        self.hits.clear()
        self.query = None
        self.open()

    def open(self):
        if self.job:
            return
        cli, why = locate(self.home.settings.value("brewExecutable", ""))
        if cli != self.cli:
            self.last_command = ""
            self.log_tail.clear()
            self.log.clear()
            self.show_log.setChecked(False)
            self.loaded = False
            self.inventory.clear()
            self.hits.clear()
            self.query = None
        self.cli = cli
        self.setup.setVisible(not cli)
        for widget in (self.view, self.filter, self.text, self.table, self.refresh, self.update, self.all):
            widget.setVisible(bool(cli))
        self.find.setVisible(bool(cli) and self.view.currentIndex() == 1)
        if cli and (not self.loaded or time.monotonic() - self.last_scan > 60):
            self.reload()
        elif not cli:
            self.status.setText(tr("This Homebrew installation is incomplete. Choose a working installation or open the setup guide.")
                                if why == "incomplete" else tr("Homebrew was not found. Choose its executable or open the setup guide."))
        self.apply_filter()

    def mode(self, *_):
        current = self.view.currentIndex()
        if current != self.old_view:
            self.view_text[self.old_view] = self.text.text()
            self.view_filter[self.old_view] = self.filter.currentIndex()
            self.old_view = current
        browsing = self.view.currentIndex() == 1
        self.filter.blockSignals(True)
        self.filter.clear()
        if not browsing:
            for label, key in ((tr("All packages"), "all"), (tr("Updates available"), "updates"), (tr("Dependencies"), "deps")):
                self.filter.addItem(label, key)
        self.filter.addItem(tr("Formulae"), "formula")
        self.filter.addItem(tr("Casks"), "cask")
        self.filter.setCurrentIndex(max(0, self.view_filter[current]))
        self.filter.blockSignals(False)
        self.text.setText(self.view_text[current])
        self.text.setPlaceholderText(tr("Search by package name") if browsing else tr("Filter installed packages"))
        self.find.setVisible(bool(self.cli) and browsing)
        self.apply_filter()

    def selected(self):
        index = self.table.currentIndex()
        return self.model.rows[index.row()] if index.isValid() and index.row() < len(self.model.rows) else None

    def apply_filter(self, *_):
        selected = self.selected()
        text = self.text.text().strip().casefold()
        kind = self.filter.currentData()
        if self.view.currentIndex() == 1:
            rows = self.hits.values() if self.query == (kind, text) else []
        else:
            rows = (p for p in self.inventory.values() if text in p.name.lower()
                    and (kind == "all" or kind == p.kind or (kind == "updates" and p.outdated)
                         or (kind == "deps" and p.dependency)))
        rows = sorted(rows, key=lambda p: (not p.upgradable, p.name.casefold(), p.kind))
        self.model.replace(rows)
        if rows:
            row = next((i for i, p in enumerate(rows) if selected and selected.key == p.key), 0)
            self.table.selectRow(row)
        self.selection()

    def selection(self, *_):
        p = self.selected()
        idle = self.job is None
        usable = bool(self.cli) and idle
        self.find.setEnabled(usable and bool(self.text.text().strip()))
        self.options.setEnabled(idle)
        self.refresh.setEnabled(usable)
        self.update.setEnabled(usable)
        self.all.setEnabled(usable and self.loaded and any(pkg.upgradable for pkg in self.inventory.values()))
        self.install.setVisible(bool(p and not p.installed))
        self.remove.setVisible(bool(p and p.installed))
        self.upgrade.setVisible(bool(p and p.outdated))
        self.info.setVisible(bool(p))
        self.install.setEnabled(usable and self.loaded)
        self.remove.setEnabled(usable and self.loaded)
        self.upgrade.setEnabled(usable and self.loaded and bool(p and p.upgradable))
        self.info.setEnabled(usable)
        self.copy.setVisible(bool(self.last_command))
        self.show_log.setVisible(bool(self.last_command))
        self.stop.setVisible(self.applying_action)
        self.stop.setEnabled(self.applying_action and not getattr(self, "cancelled", False))
        parts = []
        if p:
            parts.append(tr("Formula") if p.kind == "formula" else tr("Cask"))
            if p.pinned:
                parts.append(tr("Pinned"))
            if p.dependency:
                parts.append(tr("Installed as a dependency"))
            if p.outdated:
                parts.append(tr("Update available"))
        self.detail.setText(" · ".join(parts) + ("\n" + p.description if p and p.description else ""))

    def reload(self, message=""):
        self.run(["info", "--json=v2", "--installed"], "inventory", message if isinstance(message, str) else "")

    def search(self):
        if self.view.currentIndex() != 1 or self.job:
            return
        term = self.text.text().strip()
        kind = self.filter.currentData()
        if not term or len(term) > 200 or term.startswith(("-", "/")) or any(not c.isprintable() for c in term):
            self.status.setText(tr("Enter a package name to search."))
            return
        self.run(["search", "--" + kind, term], "search", (kind, term.casefold()))

    def details(self, *_):
        p = self.selected()
        if p and not self.job:
            self.run(["info", "--json=v2", "--" + p.kind, p.name], "details", p.key)

    def change(self, verb):
        if self.job or not self.cli or (verb != "update" and not self.loaded):
            return
        if verb == "update":
            args = ["update"]
        elif verb == "all":
            if not any(p.upgradable for p in self.inventory.values()):
                return
            if QMessageBox.question(self, tr("Update all Homebrew packages?"),
                    tr("Homebrew will upgrade outdated packages and any dependencies it needs. Pinned formulae stay pinned."),
                    QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) != QMessageBox.Yes:
                return
            args = ["upgrade"]
        else:
            p = self.selected()
            if not p or not TOKEN.fullmatch(p.name) or p.kind not in ("formula", "cask"):
                return
            if (verb == "install" and p.installed) or (verb == "upgrade" and not p.upgradable) or (verb == "uninstall" and not p.installed):
                return
            args = [verb, "--" + p.kind, p.name]
            if verb == "uninstall":
                multiple = p.kind == "formula" and ", " in p.installed and not p.pinned
                prompt = (tr("Remove all installed versions of %1 using Homebrew?") if multiple
                          else tr("Remove %1 using Homebrew?"))
                if QMessageBox.question(self, tr("Remove Homebrew package?"), prompt.replace("%1", p.name),
                        QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) != QMessageBox.Yes:
                    return
                if multiple:
                    args.insert(1, "--force")
        self.run(args, "change")

    def cancel(self):
        if self.applying_action and self.job and self.job.processId() > 0:
            pid = self.job.processId()
            try:
                if os.getpgid(pid) == pid:
                    os.killpg(pid, signal.SIGINT)
                    self.cancelled = True
                    self.status.setText(tr("Cancelling the Homebrew operation…"))
                    self.selection()
            except ProcessLookupError:
                pass

    def paint_log(self, *_):
        if not self.show_log.isChecked():
            return
        scroll = self.log.verticalScrollBar()
        position = scroll.value()
        at_end = position == scroll.maximum()
        self.log.setPlainText(self.log_tail.decode("utf-8", "replace").replace("\r", "\n"))
        scroll.setValue(scroll.maximum() if at_end else position)

    def run(self, args, purpose, context=None):
        if self.job or not self.cli:
            return
        job = QProcess(self)
        self.job = job
        self.applying_action = purpose == "change"
        self.cancelled = False
        self.home.running.add(job)
        job.setUnixProcessParameters(QProcess.UnixProcessFlag.CreateNewSession)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("HOMEBREW_NO_COLOR", "1")
        env.insert("HOMEBREW_NO_ENV_HINTS", "1")
        if not self.applying_action:
            env.insert("HOMEBREW_NO_AUTO_UPDATE", "1")
        job.setProcessEnvironment(env)
        job.setStandardInputFile(QProcess.nullDevice())
        if self.applying_action:
            job.setProcessChannelMode(QProcess.MergedChannels)
            self.last_command = shlex.join([self.cli, *args])
            self.log_tail = bytearray((self.last_command + "\n").encode())
            self.paint_log()
        self.selection()
        if purpose == "change":
            self.status.setText({"install": tr("Installing %1…"), "uninstall": tr("Removing %1…"),
                                 "upgrade": tr("Updating %1…"), "update": tr("Updating Homebrew…")
                                 }[args[0]].replace("%1", args[-1] if len(args) > 1 else tr("packages")))
        else:
            self.status.setText(tr("Reading Homebrew packages…"))
        raw, errors = bytearray(), bytearray()
        oversized = False
        def read():
            nonlocal oversized
            chunk = bytes(job.readAllStandardOutput())
            if purpose == "change":
                self.log_tail.extend(chunk)
                del self.log_tail[:-48000]
                if self.isVisible() and self.show_log.isChecked() and not self.log_timer.isActive():
                    self.log_timer.start()
                return
            if len(raw) + len(chunk) <= 64 * 1024 * 1024:
                raw.extend(chunk)
            else:
                oversized = True
            errors.extend(bytes(job.readAllStandardError()))
            del errors[:-12000]
        job.readyReadStandardOutput.connect(read)
        job.readyReadStandardError.connect(read)
        def finish(ok, start_error=""):
            if self.job is not job:
                return
            read()
            if start_error:
                (self.log_tail if purpose == "change" else errors).extend(start_error.encode("utf-8", "replace"))
            self.home.running.discard(job)
            self.job = None
            self.applying_action = False
            job.deleteLater()
            if purpose == "change":
                self.paint_log()
                message = (tr("Homebrew operation cancelled.") if self.cancelled else
                           tr("Homebrew operation completed.") if ok else tr("Homebrew could not finish. See the operation log."))
                if not ok and not self.cancelled:
                    self.show_log.setChecked(True)
                if getattr(self.home, "close_after_process_action", False) and not self.home.isVisible():
                    self.home.close()
                    return
                self.home.close_after_process_action = False
                self.loaded = False
                self.reload(message)
                return
            if not ok or oversized:
                error = errors.decode("utf-8", "replace").strip()
                if purpose == "inventory":
                    self.loaded = False
                if purpose == "search":
                    self.query, self.hits = context, {}
                if purpose == "search" and "No formulae or casks found" in error:
                    self.status.setText(tr("No matching packages."))
                else:
                    self.status.setText(tr("Homebrew returned too much data.") if oversized else (error[-650:] or tr("Could not read Homebrew packages.")))
                self.apply_filter()
                return
            try:
                self.receive(purpose, context, raw)
            except (ValueError, TypeError, KeyError, AttributeError):
                if purpose == "inventory":
                    self.loaded = False
                self.status.setText(tr("Homebrew returned unreadable package information."))
            self.apply_filter()
        job.finished.connect(lambda code, state: finish(code == 0 and state == QProcess.NormalExit))
        job.errorOccurred.connect(lambda error: finish(False, job.errorString()) if error == QProcess.FailedToStart else None)
        job.start(self.cli, args)

    def receive(self, purpose, context, raw):
        if purpose == "inventory":
            self.inventory = {k: p for k, p in package_info(raw).items() if p.installed}
            self.loaded = True
            self.last_scan = time.monotonic()
            # Search rows can belong to a package which was just removed.
            self.hits = {k: self.inventory.get(old.key) or Package(*old.key) for k, old in self.hits.items()}
            self.status.setText(context or tr("%1 installed packages.").replace("%1", str(len(self.inventory))))
        elif purpose == "search":
            self.query = context
            self.hits = search_results(raw, context[0], self.inventory)
            self.status.setText(tr("%1 matching packages.").replace("%1", str(len(self.hits))) if self.hits else tr("No matching packages."))
        else:
            found = package_info(raw)
            pkg = found.get(context) or (next(iter(found.values())) if len(found) == 1 else None)
            if not pkg or pkg.kind != context[0]:
                raise ValueError("No matching package details")
            if context in self.hits:
                self.hits[context] = pkg
            lines = [pkg.description, tr("Installed") + "  " + pkg.installed if pkg.installed else "",
                     tr("Available") + "  " + pkg.available if pkg.available else "",
                     tr("Dependencies") + "  " + ", ".join(pkg.dependencies) if pkg.dependencies else ""]
            box = QMessageBox(QMessageBox.Information, pkg.name, "\n\n".join(filter(None, lines)) or pkg.name, QMessageBox.Ok, self)
            box.setTextFormat(Qt.PlainText)
            box.exec()
            self.status.clear()
