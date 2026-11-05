"""Monet's optional app-support preferences; contains no credential operations."""
import sys
from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QDialogButtonBox
from app_support import AppSupport
from app_prompt import OfferDialog

N_ = lambda text: text  # Extract worker feedback; translate it on the UI thread.


class Worker(QThread):
    completed = Signal(object, str, object)
    def __init__(self, backend, change=None):
        super().__init__(); self.backend, self.change = backend, change
    def run(self):
        try:
            result = self.backend.change(*self.change) if self.change else None
            self.completed.emit(self.backend.listed(), '', result)
        except Exception as error:
            self.completed.emit([], str(error) if isinstance(error, ValueError) else N_('App support could not be changed. Try again.'), None)


class SupportDialog(QDialog):
    def __init__(self, backend=None):
        super().__init__()
        from app import tr
        self.tr, self.backend, self.worker = tr, backend or AppSupport(), None
        self.setWindowTitle(tr('App login support')); self.setWindowIcon(QIcon.fromTheme('preferences-desktop-user-password'))
        self.setMinimumSize(480, 500); self.resize(580, 560)
        box = QVBoxLayout(self); box.setContentsMargins(28, 26, 28, 26); box.setSpacing(18)
        title = QLabel(tr('Help apps share their sign-in fields')); title.setObjectName('title'); title.setWordWrap(True); box.addWidget(title)
        detail = QLabel(tr('Some sandboxed apps need accessibility support enabled. Choose an app, enable support, then reopen it. Monet still asks before saving or filling a login.'))
        detail.setWordWrap(True); box.addWidget(detail)
        self.apps = QListWidget(); self.apps.setAccessibleName(tr('Installed apps')); box.addWidget(self.apps, 1)
        self.feedback = QLabel(); self.feedback.setWordWrap(True); self.feedback.setTextFormat(Qt.PlainText); box.addWidget(self.feedback)
        note = QLabel(tr('Some apps still need their developer to add login support. Undo change restores the earlier setting while keeping other app preferences.'))
        note.setObjectName('muted'); note.setWordWrap(True); box.addWidget(note)
        buttons = QDialogButtonBox(); self.enable = buttons.addButton(tr('Enable support'), QDialogButtonBox.ActionRole)
        self.restore = buttons.addButton(tr('Undo change'), QDialogButtonBox.ActionRole)
        self.refresh = buttons.addButton(tr('Refresh'), QDialogButtonBox.ActionRole)
        self.close_button = buttons.addButton(tr('Close'), QDialogButtonBox.RejectRole); self.close_button.setDefault(True)
        for button in (self.enable, self.restore, self.refresh): button.setAutoDefault(False)
        box.addWidget(buttons); buttons.rejected.connect(self.reject)
        self.apps.itemSelectionChanged.connect(self.controls)
        self.enable.clicked.connect(lambda: self.change(True)); self.restore.clicked.connect(lambda: self.change(False))
        self.refresh.clicked.connect(lambda: self.load())
        OfferDialog.apply_theme(self)
        dark = QApplication.palette().color(QPalette.Window).lightness() < 128
        self.setStyleSheet(self.styleSheet() + 'QListWidget { border: 1px solid ' + ('#444c4b' if dark else '#d8dcd6') +
            '; border-radius: 8px; padding: 3px; } QListWidget::item { padding: 12px; margin: 3px; border-radius: 6px; } '
            'QListWidget::item:selected { background: ' + ('#34544f' if dark else '#d9e6e0') +
            '; color: ' + ('#eeeae2' if dark else '#252b29') + '; }')
        self.controls(); QTimer.singleShot(0, self.load)

    def controls(self):
        item = self.apps.currentItem(); row = item.data(Qt.UserRole) if item else {}
        self.enable.setEnabled(self.worker is None and bool(row) and not row['enabled'] and not row['managed'])
        self.restore.setEnabled(self.worker is None and bool(row.get('managed')))
        self.refresh.setEnabled(self.worker is None); self.apps.setEnabled(self.worker is None)
        self.close_button.setEnabled(self.worker is None)

    def load(self, change=None):
        if self.worker is not None: return
        self.worker = Worker(self.backend, change); self.worker.completed.connect(self.completed)
        self.worker.finished.connect(self.worker_finished)
        self.feedback.setText(self.tr('Checking app support…')); self.controls(); self.worker.start()

    def completed(self, rows, error, result):
        selected = self.apps.currentItem().data(Qt.UserRole)['id'] if self.apps.currentItem() else None
        self.apps.clear()
        for row in rows:
            suffix = self.tr('Support enabled') if row['enabled'] else self.tr('Default support')
            item = QListWidgetItem(row['name'] + '\n' + suffix); item.setData(Qt.UserRole, row); self.apps.addItem(item)
            if row['id'] == selected: self.apps.setCurrentItem(item)
        self.feedback.setText(self.tr(error) if error else self.tr('Your newer app setting was kept.') if result and result.get('preserved') else
                              self.tr('Support updated. Reopen the app to use the change.') if result and result.get('changed') else
                              self.tr('Choose an app to review its support.') if rows else self.tr('No supported sandboxed apps were found.'))

    def worker_finished(self):
        self.worker.deleteLater(); self.worker = None; self.controls()

    def change(self, enabled):
        item = self.apps.currentItem()
        if item: self.load((item.data(Qt.UserRole)['id'], enabled))

    def reject(self):
        if self.worker is None: super().reject()


def main():
    app = QApplication(sys.argv[:1]); app.setStyle('Fusion')
    dialog = SupportDialog(); dialog.show(); return app.exec()
