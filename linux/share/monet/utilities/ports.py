"""On-demand local port and process inspection for Monet Utilities."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QTableView, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from actions import tr
from local_ports import Listener, Process, selected_branch

import local_ports
WORKER = [sys.executable, str(Path(local_ports.__file__))]


def table(headers):
    view = QTreeWidget()
    view.setHeaderLabels(headers)
    view.setEditTriggers(QAbstractItemView.NoEditTriggers)
    view.setAlternatingRowColors(True)
    view.setUniformRowHeights(True)
    view.setAllColumnsShowFocus(True)
    view.header().setStretchLastSection(False)
    return view


class ProcessDialog(QDialog):
    def __init__(self, page, listener, members):
        super().__init__(page)
        self.listener = listener
        self.members = members
        self.apps = {}
        self.page = page
        self.setWindowTitle(tr("Process tree"))
        self.resize(480, 340)
        layout = QVBoxLayout(self)
        if listener:
            endpoint = QLabel(f"{listener.protocol}   {listener.address}   ·   {tr('Port')} {listener.port}")
            endpoint.setTextFormat(Qt.PlainText)
            layout.addWidget(endpoint)
        self.tree = table([tr("Process"), tr("PID")])
        self.tree.setAccessibleName(tr("Process tree"))
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        items = {}
        for member in members:
            item = QTreeWidgetItem(items.get(member.parent, self.tree))
            item.setText(0, member.name)
            item.setData(1, Qt.DisplayRole, member.pid)
            item.setData(0, Qt.UserRole, member)
            items[member.pid] = item
        self.tree.expandToDepth(1)
        layout.addWidget(self.tree)
        self.children = QCheckBox(tr("Include child processes"))
        layout.addWidget(self.children)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self.restart = buttons.addButton(tr("Restart app…"), QDialogButtonBox.ActionRole)
        self.restart.setToolTip(tr("Available for an app with a matching launcher."))
        self.end = buttons.addButton(tr("End process…"), QDialogButtonBox.ActionRole)
        self.force = buttons.addButton(tr("Force quit…"), QDialogButtonBox.ActionRole)
        buttons.rejected.connect(self.reject)
        self.end.clicked.connect(lambda: self.confirm("end"))
        self.force.clicked.connect(lambda: self.confirm("force"))
        self.restart.clicked.connect(lambda: self.confirm("restart"))
        for button in (self.end, self.force, self.restart):
            button.setAutoDefault(False)
        layout.addWidget(buttons)
        self.tree.currentItemChanged.connect(self.selection_changed)
        self.children.toggled.connect(self.selection_changed)
        self.tree.setCurrentItem(items[members[0].pid])
        close = buttons.button(QDialogButtonBox.Close)
        close.setText(tr("Close"))
        close.setDefault(True)

    def selection_changed(self, *_):
        item = self.tree.currentItem()
        if not item:
            return
        selected = item.data(0, Qt.UserRole)
        self.children.setEnabled(item.childCount() > 0)
        branch = selected_branch(self.members, selected, self.children.isChecked())
        allowed = all(p.pid not in (1, os.getpid()) and p.uid == os.getuid() for p in branch)
        self.restart.setEnabled(selected.pid in self.apps and allowed and not (self.children.isEnabled() and self.children.isChecked()))
        for button in (self.end, self.force):
            button.setEnabled(allowed)
            button.setToolTip("" if allowed else tr("This selection includes a protected process or a process owned by another user."))

    def confirm(self, action):
        restart = action == "restart"
        force = action == "force"
        selected = self.tree.currentItem().data(0, Qt.UserRole)
        include = self.children.isEnabled() and self.children.isChecked()
        targets = selected_branch(self.members, selected, include)
        question = QMessageBox(self)
        question.setIcon(QMessageBox.Warning if force else QMessageBox.Question)
        question.setTextFormat(Qt.PlainText)
        verb = tr("Restart app") if restart else (tr("Force quit") if force else tr("End process"))
        question.setWindowTitle(verb)
        text = tr("Force quit %1 (PID %2)?") if force else tr("Ask %1 (PID %2) to quit?")
        if restart:
            text = tr("Quit and reopen %1 (PID %2)?")
        question.setText(text.replace("%2", str(selected.pid)).replace("%1", selected.name))
        details = []
        if len(targets) > 1:
            details.append(tr("This applies to %1 processes, including children.").replace("%1", str(len(targets))))
        if restart:
            details.append(tr("Monet will reopen the app from its launcher after this process exits."))
        if force:
            details.append(tr("The selected processes will stop immediately. Unsaved work can be lost."))
        else:
            details.append(tr("Save any work you want to keep before continuing."))
        question.setInformativeText("\n".join(details))
        question.addButton(QMessageBox.Cancel).setText(tr("Cancel"))
        proceed = question.addButton(verb, QMessageBox.DestructiveRole)
        question.setDefaultButton(QMessageBox.Cancel)
        def confirmed(_):
            if question.clickedButton() is proceed:
                self.accept()
                self.page.apply_action(self.listener, self.members, selected, include, action, self.apps.get(selected.pid))
        from inline_dialogs import present_dialog
        present_dialog(question,self,finished=confirmed)


class ProcessTable(QAbstractTableModel):
    # Store search text once per snapshot. Qt only requests cells in view.
    before_change = Signal()
    after_change = Signal()

    def __init__(self, ports, parent):
        super().__init__(parent)
        self.ports = ports
        self.headers = ([tr("Port"), tr("Protocol"), tr("Local address"), tr("Process"), tr("PID")]
                        if ports else [tr("Process"), tr("PID")])
        self.entries = []
        self.filtered = []
        self.words = []
        self.column = 0
        self.descending = False

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.filtered)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.headers)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole and 0 <= section < len(self.headers):
            return self.headers[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid() and role in (Qt.DisplayRole, Qt.ToolTipRole, Qt.UserRole):
            entry, cells, _ = self.filtered[index.row()]
            return entry if role == Qt.UserRole else cells[index.column()]
        return None

    def replace(self, raw):
        self.entries = []
        unknown = tr("Owner unavailable")
        for row in raw:
            if self.ports:
                item = Listener.from_json(row)
                name = item.owner.name if item.owner else unknown
                cells = (item.port, item.protocol, item.address, name, item.owner.pid if item.owner else None)
            else:
                item = Process(**row)
                cells = (item.name, item.pid)
            search = " ".join(str(value) for value in cells if value is not None).casefold()
            self.entries.append((item, cells, search))
        self.sort(self.column, Qt.DescendingOrder if self.descending else Qt.AscendingOrder)

    def sort(self, column, order=Qt.AscendingOrder):
        if not 0 <= column < len(self.headers):
            return
        self.column, self.descending = column, order == Qt.DescendingOrder
        def key(row):
            value = row[1][column]
            return value is None, value.casefold() if isinstance(value, str) else value
        self.entries = sorted(self.entries, key=key, reverse=self.descending)
        self.filter(self.words)

    def filter(self, words):
        self.before_change.emit()
        self.beginResetModel()
        self.words = words
        self.filtered = ([row for row in self.entries if all(w in row[2] for w in words)]
                         if words else self.entries)
        self.endResetModel()
        self.after_change.emit()


class ProcessBrowser(QWidget):
    def __init__(self, home, ports):
        super().__init__()
        self.home = home
        self.ports = ports
        self.applying_action = False
        self.loading = False
        self.detail = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText(tr("Find a port, address or process…") if ports else tr("Find a process by name or PID…"))
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self.filter_rows)
        top.addWidget(self.filter, 1)
        self.reload = QPushButton(tr("Refresh"), clicked=self.refresh)
        top.addWidget(self.reload)
        layout.addLayout(top)
        self.model = ProcessTable(ports, self)
        self.rows = QTableView()
        self.rows.setAccessibleName(tr("Listening ports") if ports else tr("Running processes"))
        self.rows.setModel(self.model)
        self.rows.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.rows.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.rows.setSelectionMode(QAbstractItemView.SingleSelection)
        self.rows.setAlternatingRowColors(True)
        self.rows.setShowGrid(False)
        self.rows.verticalHeader().hide()
        header = self.rows.horizontalHeader()
        header.setResizeContentsPrecision(35)
        for col in range(self.model.columnCount()):
            stretches = col in (2, 3) if ports else col == 0
            header.setSectionResizeMode(col, QHeaderView.Stretch if stretches else QHeaderView.ResizeToContents)
        self.rows.sortByColumn(0, Qt.AscendingOrder)
        self.rows.setSortingEnabled(True)
        self.rows.selectionModel().selectionChanged.connect(self.selection_changed)
        self.rows.activated.connect(lambda *_: self.inspect())
        layout.addWidget(self.rows)
        bottom = QHBoxLayout()
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        bottom.addWidget(self.status, 1)
        self.manage = QPushButton(tr("Manage process…"), clicked=self.inspect)
        bottom.addWidget(self.manage)
        layout.addLayout(bottom)
        self.model.before_change.connect(self.remember_selection)
        self.model.after_change.connect(self.restore_selection)
        self.selection_changed()

    def selection(self):
        rows = self.rows.selectionModel().selectedRows()
        return rows[0].data(Qt.UserRole) if rows else None

    def remember_selection(self):
        self.previous = self.selection()

    def restore_selection(self):
        if self.previous:
            for index, (entry, _, _) in enumerate(self.model.filtered):
                if entry == self.previous:
                    self.rows.selectRow(index)
                    break
        self.selection_changed()

    def selection_changed(self):
        listener = self.selection()
        self.manage.setEnabled(not self.loading and listener is not None and (not self.ports or listener.owner is not None))

    def refresh(self):
        if self.loading:
            return
        self.loading = True
        self.reload.setEnabled(False)
        self.selection_changed()
        self.status.setText(tr("Reading listening ports…") if self.ports else tr("Reading processes…"))
        def loaded(result):
            self.model.replace(json.loads(result))
            self.loading = False
            self.reload.setEnabled(True)
            self.selection_changed()
            self.update_status()
        def failed(error):
            self.loading = False
            self.model.replace([])
            self.reload.setEnabled(True)
            self.selection_changed()
            self.status.setText(tr("Could not read listening ports.") if self.ports else tr("Could not read processes."))
            self.status.setToolTip(error)
        self.home.worker([*WORKER, "list" if self.ports else "processes"], loaded, failed)

    def filter_rows(self):
        self.model.filter(self.filter.text().casefold().split())
        self.update_status()

    def update_status(self):
        if self.loading:
            return
        self.status.setToolTip("")
        if self.model.rowCount():
            self.status.clear()
        elif self.model.entries:
            self.status.setText(tr("No matching ports.") if self.ports else tr("No matching processes."))
        else:
            self.status.setText(tr("No listening ports.") if self.ports else tr("No running processes found."))

    def inspect(self):
        entry = self.selection()
        owner = entry.owner if entry and self.ports else entry
        if not owner or self.loading or self.detail is not None:
            return
        self.loading = True
        self.reload.setEnabled(False)
        self.selection_changed()
        def ready():
            self.loading = False
            self.reload.setEnabled(True)
            self.selection_changed()
        def failed(_):
            ready()
            self.home.issue(tr("The process or port changed. The list has been refreshed."))
            self.refresh()
        def loaded(result):
            members = [Process(**raw) for raw in json.loads(result)]
            if not members or (self.ports and not entry.current()):
                failed("")
                return
            ready()
            if self.isVisible():
                self.detail = ProcessDialog(self, entry if self.ports else None, members)
                self.detail.finished.connect(self.close_detail)
                self.find_apps(self.detail)
                from inline_dialogs import present_dialog
                present_dialog(self.detail,self)
        self.home.worker([*WORKER, "tree", str(owner.pid), str(owner.start)], loaded, failed)

    def find_apps(self, dialog):
        pids = [m.pid for m in dialog.members if m.uid == os.getuid() and m.pid not in (1, os.getpid())]
        if not pids:
            return
        def loaded(result):
            if self.detail is dialog:
                dialog.apps = {int(pid): app for pid, app in json.loads(result).items()}
                dialog.selection_changed()
        job = self.home.worker([*WORKER, "apps", self.home.helpers], loaded, lambda _: None)
        job.write(json.dumps(pids).encode())
        job.closeWriteChannel()

    def close_detail(self):
        self.detail.deleteLater()
        self.detail = None

    def apply_action(self, entry, members, selected, children, action, app):
        force = action == "force"
        self.applying_action = True
        self.loading = True
        self.reload.setEnabled(False)
        self.selection_changed()
        self.status.setText(tr("Waiting for the app to restart…") if action == "restart" else tr("Sending the quit request…"))
        def finish(message):
            self.applying_action = False
            self.home.issue(message)
            self.loading = False
            if getattr(self.home, "close_after_process_action", False) and not self.home.isVisible():
                self.home.close()
            else:
                self.home.close_after_process_action = False
                self.refresh()
        def done(result):
            if action == "restart":
                messages = {"launched": tr("The app was relaunched."),
                            "still-running": tr("The app is still running. Check it for a save or quit prompt."),
                            "unavailable": tr("The app’s launcher is unavailable."),
                            "launch-failed": tr("The process exited, but its app could not be reopened.")}
                finish(messages[json.loads(result)])
                return
            sent, missed = json.loads(result)
            if sent == 1:
                message = tr("Sent the force-quit request.") if force else tr("Asked the process to quit.")
            else:
                message = tr("Sent force-quit requests to %1 processes.") if force else tr("Asked %1 processes to quit.")
                message = message.replace("%1", str(sent))
            if missed:
                message += " " + tr("%1 could no longer be reached.").replace("%1", str(missed))
            finish(message)
        cmd = ["restart", self.home.helpers] if action == "restart" else ["end"]
        job = self.home.worker([*WORKER, *cmd], done,
                               lambda _: finish(tr("The process changed or could not be stopped. Review the refreshed list.")))
        request = dict(listener=asdict(entry) if entry else None, app=app, members=[asdict(member) for member in members],
                       selected=asdict(selected), children=children, force=force)
        job.write(json.dumps(request).encode("utf-8"))
        job.closeWriteChannel()
