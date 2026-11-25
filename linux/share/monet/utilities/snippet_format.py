"""Choose how a date or time will appear in a snippet."""
from PySide6.QtCore import Qt, QTimeZone
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel

from actions import tr
from snippet_variables import expand


def choose_format(parent):
    editor = QDialog(parent)
    editor.setWindowTitle(tr("Custom date or time"))
    form = QFormLayout(editor)
    pattern = QComboBox()
    pattern.setEditable(True)
    pattern.addItems(["yyyy-MM-dd", "HH:mm", "yyyy-MM-dd HH:mm", "dddd, d MMMM yyyy"])
    form.addRow(tr("Date and time format"), pattern)
    zone = QComboBox()
    zone.setEditable(True)
    zone.setInsertPolicy(QComboBox.NoInsert)
    zone.addItem(tr("Local time zone"))
    zone.addItems(sorted(bytes(raw).decode("ascii") for raw in QTimeZone.availableTimeZoneIds()))
    form.addRow(tr("Time zone"), zone)
    sample = QLabel()
    sample.setTextFormat(Qt.PlainText)
    sample.setWordWrap(True)
    form.addRow(tr("Preview"), sample)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(editor.accept)
    buttons.rejected.connect(editor.reject)
    form.addRow(buttons)

    def token():
        fmt = pattern.currentText()
        if not fmt.strip() or len(fmt) > 128 or any(ch in fmt for ch in "{}\r\n"):
            return ""
        place = zone.currentText().strip()
        if place and place != zone.itemText(0):
            if zone.findText(place) < 1:
                return ""
            return "{{datetime-tz(" + place + "):" + fmt + "}}"
        return "{{datetime:" + fmt + "}}"

    def preview():
        value = token()
        sample.setText(expand(value) if value else "")
        buttons.button(QDialogButtonBox.Ok).setEnabled(bool(value))

    pattern.currentTextChanged.connect(preview)
    zone.currentTextChanged.connect(preview)
    preview()
    value = token() if editor.exec() == QDialog.Accepted else ""
    editor.deleteLater()
    return value
