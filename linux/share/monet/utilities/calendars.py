"""Choose calendars for the notch without signing the desktop in to another account."""
from gettext import translation
from pathlib import Path
from urllib.parse import urlsplit

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget)

import agenda

tr = translation("monet", localedir=str(Path(__file__).resolve().parents[2] / "locale"), fallback=True).gettext


class Calendars(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        hint = QLabel(tr("Choose the appointments shown in the notch. Linked files follow changes on disk. Subscriptions refresh when you open the agenda."))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.list = QListWidget()
        self.list.setAccessibleName(tr("Calendars in the notch"))
        layout.addWidget(self.list)
        self.status = QLabel()
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        self.files = QPushButton(tr("Link file…"), clicked=self.link_file)
        self.subscribe = QPushButton(tr("Subscribe…"), clicked=self.subscription)
        self.forget = QPushButton(tr("Remove"), clicked=self.remove)
        self.forget.setToolTip(tr("Remove this source and its saved copy from the agenda. Your original calendar is kept."))
        for button in (self.files, self.subscribe, self.forget):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.list.currentRowChanged.connect(lambda row: self.forget.setEnabled(row >= 0))
        self.reload()

    def reload(self, selected=None):
        self.list.clear()
        try:
            rows = agenda.sources()
        except (ValueError, OSError):
            self.status.setText(tr("Could not read your calendar list."))
            self.forget.setEnabled(False)
            return
        self.status.setText("" if rows else tr("No calendars added yet."))
        for row in rows:
            origin = Path(row["location"]).name if row["kind"] == "file" else urlsplit(row["location"]).hostname
            item = QListWidgetItem(row["name"] + " · " + origin)
            item.setData(Qt.UserRole, row["id"])
            self.list.addItem(item)
            if row["id"] == selected:
                self.list.setCurrentItem(item)
        self.forget.setEnabled(self.list.currentRow() >= 0)

    def link_file(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Link calendar file"), "", tr("iCalendar (*.ics *.ICS);;All files (*)"))
        if path:
            try:
                self.reload(agenda.add("file", path))
            except (ValueError, OSError):
                self.status.setText(tr("Could not link this file. Choose a readable iCalendar file up to 5 MiB."))

    def subscription(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Subscribe to a calendar"))
        form = QFormLayout(dialog)
        url, name = QLineEdit(), QLineEdit()
        url.setPlaceholderText("https://…")
        name.setPlaceholderText(tr("Optional"))
        form.addRow(tr("&Calendar link"), url)
        form.addRow(tr("&Name"), name)
        error = QLabel()
        error.setWordWrap(True)
        form.addRow(error)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(tr("Subscribe"))
        form.addRow(buttons)
        def accept():
            try:
                ident = agenda.add("url", url.text(), name.text())
            except ValueError:
                error.setText(tr("Enter an HTTPS or webcal calendar subscription link."))
                url.setFocus()
                return
            except OSError:
                error.setText(tr("Could not save this calendar."))
                return
            self.reload(ident)
            dialog.accept()
        buttons.accepted.connect(accept)
        buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def remove(self):
        item = self.list.currentItem()
        if item:
            try:
                row = self.list.currentRow()
                agenda.remove(item.data(Qt.UserRole))
                self.reload()
                self.list.setCurrentRow(min(row, self.list.count() - 1))
            except (OSError, ValueError):
                self.status.setText(tr("Could not remove this calendar."))
