"""Preview copied-link cleanup and choose the rules used by both clipboard actions."""
from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget)

from actions import tr
from clipboard_text import copy_text
from links import DEFAULTS, clean_link, effective_rules, read_rules, rule_name, set_rule, site_name


class LinkRules(QDialog):
    def __init__(self, edits, parent):
        super().__init__(parent)
        self.edits = edits
        self.setWindowTitle(tr("Link cleanup rules"))
        self.resize(460, 460)
        layout = QVBoxLayout(self)
        sites = QHBoxLayout()
        layout.addLayout(sites)
        self.site = QComboBox()
        self.site.setAccessibleName(tr("Website"))
        self.site.addItem(tr("All websites"), "")
        for site in sorted((set(DEFAULTS) | set(edits)) - {""}):
            self.site.addItem(site, site)
        sites.addWidget(self.site, 1)
        add_site = QPushButton(tr("Add website…"))
        sites.addWidget(add_site)
        add_site.clicked.connect(self.add_site)
        hint = QLabel(tr("Checked parameters are removed. Website rules also apply to subdomains."))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.names = QListWidget()
        self.names.setAccessibleName(tr("Parameters to remove"))
        layout.addWidget(self.names, 1)
        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        add = QPushButton(tr("Add parameter…"))
        buttons.addWidget(add)
        add.clicked.connect(self.add_parameter)
        self.reset = QPushButton(tr("Use default"))
        buttons.addWidget(self.reset)
        self.reset.clicked.connect(lambda: self.save(self.names.currentItem().text(), None))
        self.message = QLabel()
        self.message.setTextFormat(Qt.PlainText)
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.accept)
        layout.addWidget(close)
        self.names.itemChanged.connect(self.toggled)
        self.names.currentItemChanged.connect(self.update_reset)
        self.site.currentIndexChanged.connect(self.show_names)
        self.show_names()

    def show_names(self, *_):
        selected = self.names.currentItem()
        self.fill(selected.text() if selected else "")

    def fill(self, selected):
        self.names.blockSignals(True)
        self.names.clear()
        for name, enabled in sorted(effective_rules(self.site.currentData(), self.edits).items()):
            item = QListWidgetItem(name, self.names)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if enabled else Qt.Unchecked)
            if name == selected:
                self.names.setCurrentItem(item)
        self.names.blockSignals(False)
        self.update_reset()

    def update_reset(self, *_):
        selection = self.names.currentItem()
        group = self.edits.get(self.site.currentData(), {})
        self.reset.setEnabled(selection is not None and selection.text() in group)

    def add_site(self):
        text, ok = QInputDialog.getText(self, tr("Add website…"), tr("Website name"))
        if not ok:
            return
        try:
            site = site_name(text)
        except ValueError:
            self.message.setText(tr("Enter a website name such as example.com."))
            return
        index = self.site.findData(site)
        if index < 0:
            self.site.addItem(site, site)
            index = self.site.count() - 1
        self.site.setCurrentIndex(index)
        self.message.clear()

    def add_parameter(self):
        text, ok = QInputDialog.getText(self, tr("Add parameter…"), tr("Parameter name"))
        if not ok:
            return
        try:
            name = rule_name(text)
        except ValueError:
            self.message.setText(tr("Enter a parameter name such as ref or utm_source."))
            return
        self.save(name, True)

    def toggled(self, item):
        name = item.text()
        if not self.write(name, item.checkState() == Qt.Checked):
            active = effective_rules(self.site.currentData(), self.edits)
            self.names.blockSignals(True)
            item.setCheckState(Qt.Checked if active.get(name) else Qt.Unchecked)
            self.names.blockSignals(False)
        self.update_reset()

    def save(self, name, enabled):
        self.write(name, enabled)
        self.fill(name)

    def write(self, name, enabled):
        try:
            self.edits = set_rule(self.site.currentData(), name, enabled)
            self.message.clear()
            return True
        except (OSError, ValueError):
            self.message.setText(tr("Couldn’t save the link rules."))
            return False


class LinkSettings(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.rules = {}
        layout = QVBoxLayout(self)
        self.switch = QCheckBox(tr("Clean copied links automatically"))
        layout.addWidget(self.switch)
        detail = QLabel(tr("Remove common tracking parameters when you copy a plain web address. Formatted text, files and recognized signed links keep their original contents."))
        detail.setWordWrap(True)
        layout.addWidget(detail)
        edit = QPushButton(tr("Edit cleanup rules…"))
        layout.addWidget(edit, 0, Qt.AlignLeft)
        edit.clicked.connect(self.edit)
        form = QFormLayout()
        layout.addLayout(form)
        self.source = QLineEdit()
        self.source.setClearButtonEnabled(True)
        self.source.setPlaceholderText(tr("Paste a web link to preview"))
        self.output = QLineEdit()
        self.output.setReadOnly(True)
        form.addRow(tr("Web link"), self.source)
        form.addRow(tr("Cleaned link"), self.output)
        self.status = QLabel()
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.copy = QPushButton(tr("Copy cleaned link"))
        layout.addWidget(self.copy, 0, Qt.AlignLeft)
        self.copy.clicked.connect(self.copy_preview)
        self.source.textChanged.connect(self.preview)
        self.switch.clicked.connect(self.toggle)
        layout.addStretch()
        self.preview()

    def preview(self):
        url = self.source.text().strip()
        cleaned = ""
        message = ""
        if url:
            try:
                cleaned, removed = clean_link(url, self.rules)
                message = (tr("Removed %1").replace("%1", ", ".join(removed)) if removed
                           else tr("No parameters removed."))
            except ValueError:
                message = (tr("Couldn’t read the saved link rules.") if self.rules is None
                           else tr("Enter a valid web link."))
        self.output.setText(cleaned)
        self.output.setCursorPosition(0)
        self.copy.setEnabled(bool(cleaned))
        self.status.setText(message)

    def copy_preview(self):
        copy_text(self.owner, self.output.text(), lambda ok: self.owner.issue(
            tr("Link copied.") if ok else tr("Couldn’t copy the link.")))

    def edit(self):
        try:
            edits = read_rules()
        except ValueError:
            self.owner.issue(tr("Couldn’t read the saved link rules."))
            return
        LinkRules(edits, self).exec()
        self.reload_rules()

    def reload_rules(self):
        try:
            self.rules = read_rules()
        except ValueError:
            self.rules = None
        self.preview()

    def refresh(self):
        def show(result):
            self.switch.setChecked(result.strip() == "on")
            self.switch.setEnabled(True)
        self.switch.setEnabled(False)
        self.owner.worker([sys.executable, Path(__file__).with_name("clipboard_links.py"), "status"], show)
        self.reload_rules()

    def toggle(self, on):
        self.switch.setEnabled(False)
        def failed(message):
            self.owner.issue(message)
            self.refresh()
        self.owner.worker([sys.executable, Path(__file__).with_name("clipboard_links.py"), "on" if on else "off"],
                          lambda _: self.refresh(), failed)
