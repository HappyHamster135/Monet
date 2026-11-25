"""Copy recognized text in place or edit it in the Utilities catalog."""
import json
from pathlib import Path
import sys
import tempfile

from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout

from actions import tr
from screen_selection import ScreenSelection


class ScreenText(ScreenSelection):
    def __init__(self, owner):
        super().__init__(owner, "ocr")
        layout = QVBoxLayout(self)
        self.editor = QPlainTextEdit()
        self.editor.setAccessibleName(tr("Recognized text"))
        layout.addWidget(self.editor, 1)
        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        select = QPushButton(tr("Select area…"))
        select.clicked.connect(lambda: self.pick(True))
        buttons.addWidget(select)
        self.copy_button = QPushButton(tr("Copy"))
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_edited)
        buttons.addWidget(self.copy_button)
        self.editor.textChanged.connect(lambda: self.copy_button.setEnabled(not self.editor.document().isEmpty()))

    def capture(self):
        try:
            area = tempfile.TemporaryDirectory(prefix="monet-capture-")
        except OSError:
            self.finish(tr("Couldn’t start the screen capture."))
            return
        path = Path(area.name) / "selection.png"

        def failed(_):
            area.cleanup()
            self.finish(tr("Couldn’t read the selected area."))

        def recognized(output):
            area.cleanup()
            if self.closing or self.key in self.owner.hidden:
                self.finish("")
                return
            try:
                text = json.loads(output)
                if not isinstance(text, str):
                    raise ValueError
            except ValueError:
                self.finish(tr("Couldn’t read the selected area."))
                return
            if not text:
                self.finish(tr("No text or QR code was found."))
                return
            if self.return_to_page:
                self.editor.setPlainText(text)
            self.copy_result(text)

        def selected(_):
            if self.closing or self.key in self.owner.hidden or not path.is_file():
                area.cleanup()
                self.finish("")
                return
            self.owner.worker([sys.executable, Path(__file__).with_name("media.py"), "read", path],
                              recognized, failed)

        # A separate background instance keeps this selection independent of
        # any screenshot or recording already open in Spectacle.
        self.owner.worker(["spectacle", "--new-instance", "--background", "--region", "--nonotify",
                           "--release-capture", "--output", path], selected, failed)

    def copy_result(self, text):
        self.copy_text(text, tr("Text copied."), tr("Couldn’t copy the text."))

    def copy_edited(self):
        if not self.busy and not self.editor.document().isEmpty():
            self.busy = True
            self.closing = False
            self.setEnabled(False)
            self.copy_result(self.editor.toPlainText())
