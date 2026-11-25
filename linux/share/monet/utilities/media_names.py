"""Names for media copies, shared by the preview and atomic batch export."""
from datetime import datetime
from pathlib import Path
import re
from string import Formatter

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QMenu,
                               QTreeWidget, QTreeWidgetItem, QToolButton, QVBoxLayout)

from actions import tr


def name_parts(pattern):
    try:
        parts = list(Formatter().parse(pattern.strip() or "{name}-small"))
    except ValueError as error:
        raise ValueError(tr("Use matching braces around each field.")) from error
    for _, key, padding, conversion in parts:
        if key is None:
            continue
        if (key not in ("name", "date", "time", "datetime", "width", "height", "format", "ext", "index", "counter")
                or conversion is not None or (padding and (key not in ("index", "counter") or not re.fullmatch("0[2-6]", padding)))):
            raise ValueError(tr("Unknown filename field. Use Insert field to choose one."))
    return parts


def copy_base(pattern, source, index, date, size, suffix):
    parts = name_parts(pattern)
    values = {"name": source.stem, "date": date.strftime("%Y%m%d"), "time": date.strftime("%H%M%S"),
              "datetime": date.strftime("%Y%m%d-%H%M%S"), "width": str(size[0]), "height": str(size[1]),
              "format": suffix[1:], "ext": suffix[1:], "index": str(index), "counter": str(index)}
    chunks = []
    for literal, key, padding, _ in parts:
        chunks.append(literal)
        if key is not None:
            chunks.append(values[key].zfill(int(padding)) if padding else values[key])
    base = "".join(chunks).strip()
    if pattern.rstrip().lower().endswith((suffix, ".{ext}", ".{format}")) and base.lower().endswith(suffix):
        base = base[:-len(suffix)]
    base = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "-", base).strip(" .")
    return base or tr("Copy")


class CopyNames:
    def __init__(self, pattern, date=None):
        self.pattern = pattern
        self.date = date or datetime.now()
        self.counts = {}
        self.used = set()

    def candidate(self, base, suffix):
        # Leave room for the extension and collision number on the destination filesystem.
        plain = base.encode("utf-8", "replace")
        key = (plain[:255-len(suffix)].decode("utf-8", "ignore"), suffix)
        number = self.counts.get(key, 0)
        while True:
            number += 1
            ending = ("" if number == 1 else f" ({number})") + suffix
            candidate = plain[:255-len(ending)].decode("utf-8", "ignore") + ending
            if candidate not in self.used:
                self.counts[key] = number
                self.used.add(candidate)
                return candidate


class NameDialog(QDialog):
    def __init__(self, parent, pattern, samples):
        super().__init__(parent)
        self.setWindowTitle(tr("File names"))
        self.samples = samples
        self.date = datetime.now()
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        layout.addLayout(row)
        label = QLabel(tr("Pattern"))
        self.pattern = QLineEdit(pattern)
        self.pattern.setMaxLength(240)
        self.pattern.setPlaceholderText("{name}-small")
        label.setBuddy(self.pattern)
        row.addWidget(label)
        row.addWidget(self.pattern, 1)
        fields = QToolButton()
        fields.setText(tr("Insert field"))
        fields.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(fields)
        for key, title in (("name", tr("Original name")), ("index", tr("Sequence number")),
                           ("index:03", tr("Sequence number (001)")), ("date", tr("Date")), ("time", tr("Time")),
                           ("datetime", tr("Date and time")), ("width", tr("Width")), ("height", tr("Height")),
                           ("ext", tr("Output extension"))):
            menu.addAction(title, lambda checked=False, k=key: self.insert_field(k))
        fields.setMenu(menu)
        row.addWidget(fields)
        self.table = QTreeWidget()
        self.table.setAccessibleName(tr("Filename preview"))
        self.table.setHeaderLabels([tr("Original"), tr("New name")])
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        self.hint = QLabel()
        self.hint.setTextFormat(Qt.PlainText)
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(QDialogButtonBox.Reset).clicked.connect(self.pattern.clear)
        layout.addWidget(self.buttons)
        self.pattern.textChanged.connect(self.refresh)
        self.resize(490, 275)
        self.refresh()

    def insert_field(self, key):
        self.pattern.insert("{" + key + "}")
        self.pattern.setFocus()

    def refresh(self):
        self.table.clear()
        names = CopyNames(self.pattern.text(), self.date)
        samples = self.samples or [(Path(tr("Picture") + ".png"), (1600, 900), ".webp")]
        try:
            for i, (path, size, suffix) in enumerate(samples, 1):
                base = copy_base(names.pattern, path, i, names.date, size, suffix)
                name = names.candidate(base, suffix)
                item = QTreeWidgetItem([path.name, name])
                item.setToolTip(0, str(path))
                item.setToolTip(1, name)
                self.table.addTopLevelItem(item)
        except ValueError as error:
            self.hint.setText(str(error))
            self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)
            return
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(True)
        self.hint.setText(tr("The preview uses the requested dimensions. Batch names use the final dimensions. If a name is taken, the copy gets a number."))
