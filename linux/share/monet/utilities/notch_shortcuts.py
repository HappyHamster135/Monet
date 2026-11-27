"""Persistent desktop shortcuts for the floating radial menu and the notch."""
import json
from pathlib import Path
import re

import dbus
from PySide6.QtCore import QIODevice, QSaveFile, QStandardPaths, Qt
from PySide6.QtDBus import QDBusConnection, QDBusMessage
from PySide6.QtGui import QCursor, QKeySequence
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout
from actions import tr
from wheel_shortcuts import registry

LAUNCHER = None
SHORTCUTS = {'radial': ('org.monet.NotchRadial.desktop', 'Radial menu'),
             'toggle': ('org.monet.NotchToggle.desktop', 'Open or close the notch')}


def details(key):
    filename, title = SHORTCUTS[key]
    return [filename, '_launch', tr(title), tr(title)]


def path_for(key):
    return Path(QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation)) / 'kglobalaccel' / SHORTCUTS[key][0]


def current(key):
    keys = registry().shortcutKeys(details(key), timeout=2)
    return QKeySequence(*(int(code) for code in keys[0][0])) if keys and keys[0][0] else QKeySequence()


def write_launcher(key, helpers):
    from gi.repository import GLib
    program = str(LAUNCHER or helpers / 'monet-utilities').replace('%', '%%')
    quoted = re.sub(r'(["`$\\])', lambda match: '\\' + match[0], program)
    entry = GLib.KeyFile()
    command = 'radial' if key == 'radial' else f'notch-shortcut {key}'
    for name, value in (('Type', 'Application'), ('Name', tr(SHORTCUTS[key][1])), ('Icon', 'view-more'),
                        ('Exec', f'"{quoted}" {command}'), ('StartupNotify', 'false')):
        entry.set_string('Desktop Entry', name, value)
    data = entry.to_data()[0].encode()
    path = path_for(key); path.parent.mkdir(parents=True, exist_ok=True)
    file = QSaveFile(str(path))
    if not file.open(QIODevice.WriteOnly) or file.write(data) != len(data) or not file.commit():
        raise OSError(file.errorString())


def assign(key, helpers, sequence):
    api = registry(); action = details(key); path = path_for(key)
    previous = api.shortcutKeys(action, timeout=2)
    if sequence.isEmpty():
        if previous: api.unregister(action[0], action[1], timeout=2)
        path.unlink(missing_ok=True)
        return
    chord = sequence[0]
    if sequence.count() != 1 or (chord.key() < Qt.Key_Escape and not chord.keyboardModifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)):
        raise ValueError(tr('Use a single shortcut with Ctrl, Alt or Super.'))
    wanted = dbus.Struct((dbus.Array([chord.toCombined(), 0, 0, 0], signature='i'),), signature='ai')
    owned = wanted in previous and api.actionList(wanted, timeout=2)[:2] == action[:2]
    if not owned and not api.globalShortcutAvailable(wanted, action[0], timeout=2):
        raise ValueError(tr('That shortcut is already in use. Choose another.'))
    old_file = path.read_bytes() if path.exists() else None
    try:
        write_launcher(key, helpers)
        api.doRegister(action, timeout=2)
        actual = api.setShortcutKeys(action, dbus.Array([wanted], signature='(ai)'), dbus.UInt32(6), timeout=2)
        if not actual or api.actionList(wanted, timeout=2)[:2] != action[:2]:
            raise ValueError(tr('The desktop could not assign that shortcut. Try another.'))
    except (OSError, ValueError, dbus.DBusException):
        try:
            if previous: api.setShortcutKeys(action, previous, dbus.UInt32(6), timeout=2)
            else: api.unregister(action[0], action[1], timeout=2)
        finally:
            if old_file is None: path.unlink(missing_ok=True)
            else: path.write_bytes(old_file)
        raise


def trigger(owner, key):
    """Open the floating radial menu, or toggle the notch on the pointer's display."""
    if key not in SHORTCUTS: return
    if key == 'radial':
        # Also honor bindings created by the earlier notch-only launcher.
        owner.wheel('radial')
        return
    try:
        shell = dbus.SessionBus().get_object('org.kde.plasmashell', '/PlasmaShell')
        script = '''print(JSON.stringify(panels().reduce((rows,p) => {
            var r = screenGeometry(p.screen);
            p.widgets("org.monet.notch").forEach(w => rows.push({id:String(w.id),x:r.x,y:r.y,w:r.width,h:r.height}));
            return rows;
        }, [])));'''
        rows = json.loads(str(shell.evaluateScript(script, dbus_interface='org.kde.PlasmaShell', timeout=2)))
        point = QCursor.pos()
        target = next((row for row in rows if row['x'] <= point.x() < row['x'] + row['w']
                       and row['y'] <= point.y() < row['y'] + row['h']), rows[0] if rows else None)
        if not target:
            owner.show_notch_settings('overview')
            return
        message = QDBusMessage.createSignal('/NotchShortcuts', 'org.monet.Utilities', 'NotchShortcut')
        message.setArguments([target['id'], key])
        QDBusConnection.sessionBus().send(message)
        owner.panelDismissed.emit()
    except (dbus.DBusException, ValueError, KeyError, TypeError):
        owner.issue(tr('Could not reach the notch. Open Notch & Tools and try again.'))


class ShortcutCard(QFrame):
    def __init__(self, owner, key):
        super().__init__(); self.owner = owner; self.key = key; self.loaded = False; self.recorder = None
        self.setObjectName('settingsCard')
        box = QVBoxLayout(self); box.setContentsMargins(18,16,18,16); box.setSpacing(10)
        top = QHBoxLayout(); box.addLayout(top)
        title = QLabel(tr(SHORTCUTS[key][1])); title.setWordWrap(True); title.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        font = title.font(); font.setBold(True); title.setFont(font); top.addWidget(title, 1)
        self.value = QPushButton(tr('Set shortcut')); self.value.clicked.connect(self.edit); top.addWidget(self.value)
        self.editor = QFrame(); self.editor.setVisible(False); self.editor_box = QVBoxLayout(self.editor); self.editor_box.setContentsMargins(0,0,0,0)
        box.addWidget(self.editor)
        self.message = QLabel(''); self.message.setWordWrap(True); self.message.setProperty('muted',True)
        self.message.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred); box.addWidget(self.message)
        self.refresh()

    def refresh(self):
        if self.editor.isVisible(): return
        try:
            self.sequence = current(self.key); self.loaded = True
            self.value.setText(self.sequence.toString(QKeySequence.NativeText).replace('Meta','Super') or tr('Set shortcut'))
            self.message.setText(tr('Works anywhere on your desktop. Click the shortcut to change it.'))
        except dbus.DBusException:
            self.loaded = False; self.message.setText(tr('Shortcut service unavailable. Click to retry.'))

    def edit(self):
        if not self.loaded:
            self.refresh()
            if not self.loaded: return
        if self.recorder is None:
            from PySide6.QtQuickWidgets import QQuickWidget
            self.recorder = QQuickWidget()
            self.recorder.setInitialProperties({'checkForConflictsAgainst':0,'multiKeyShortcutsAllowed':False,
                'showClearButton':False,'showCancelButton':True})
            self.recorder.setResizeMode(QQuickWidget.SizeRootObjectToView)
            self.recorder.loadFromModule('org.kde.kquickcontrols','KeySequenceItem')
            if not self.recorder.rootObject():
                self.message.setText(tr('Shortcut recorder unavailable.')); self.recorder.deleteLater(); self.recorder = None; return
            self.recorder.setMinimumWidth(0); self.recorder.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
            self.recorder.setFixedHeight(max(40,round(self.recorder.rootObject().implicitHeight())))
            self.recorder.setClearColor(self.palette().window().color()); self.editor_box.addWidget(self.recorder)
            buttons = QHBoxLayout(); self.editor_box.addLayout(buttons)
            for label, callback in ((tr('Clear'),self.clear),(tr('Cancel'),self.cancel),(tr('Save shortcut'),self.save)):
                button = QPushButton(label); button.clicked.connect(callback); buttons.addWidget(button)
                if callback == self.save: button.setProperty('primary',True)
        self.recorder.rootObject().setProperty('keySequence',self.sequence)
        self.editor.show(); self.value.hide()
        self.message.setText(tr('Click the recorder, then press your shortcut. Save to apply.'))

    def clear(self): self.recorder.rootObject().setProperty('keySequence',QKeySequence())
    def hideEvent(self,event):
        if self.recorder is not None:self.cancel()
        super().hideEvent(event)
    def cancel(self):
        # Destroy the recorder so an unfinished capture always releases inhibition.
        self.recorder.deleteLater(); self.recorder = None
        while self.editor_box.count():
            item = self.editor_box.takeAt(0)
            if item.layout():
                while item.layout().count(): item.layout().takeAt(0).widget().deleteLater()
                item.layout().deleteLater()
        self.editor.hide(); self.value.show(); self.refresh()
    def save(self):
        try: assign(self.key,self.owner.helpers,self.recorder.rootObject().property('keySequence'))
        except (ValueError,OSError) as error: self.message.setText(str(error)); return
        except dbus.DBusException: self.message.setText(tr('Could not save the shortcut. Your previous binding is kept.')); return
        self.cancel(); self.message.setText(tr('Shortcut saved.') if not self.sequence.isEmpty() else tr('Shortcut cleared.'))
