"""Long notes stay inside the island; pad actions preserve saved and competing edits."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    from PySide6.QtCore import QObject, QPointF, QSettings, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickView
    from PySide6.QtQuickControls2 import QQuickStyle
    from PySide6.QtTest import QTest
except ImportError:
    QQuickView = None

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "linux/share/plasma/plasmoids/org.monet.notch/contents/ui"


@unittest.skipUnless(QQuickView, "requires Qt Quick")
class Notes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QQuickStyle.setStyle("org.kde.desktop")
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def scene(self, contents):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "Notes.qml"
        path.write_text('import QtQuick\nimport QtQuick.Controls as C\nimport "' + UI.as_uri() + '''" as Monet
C.Control {
    width: 432; height: 269
    function i18n(s, a) { return s.replace("%1", a) }
''' + contents + '\n}')
        view = QQuickView()
        warnings = []
        view.engine().warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
        view.setSource(QUrl.fromLocalFile(str(path)))
        self.assertEqual(view.status(), QQuickView.Ready, [e.toString() for e in view.errors()])
        view.show()
        QTest.qWait(60)
        self.addCleanup(view.close)
        self.addCleanup(lambda: self.assertFalse(warnings, warnings))
        return view, view.rootObject()

    def test_long_scratchpad_wraps_scrolls_edits_copies_and_undoes(self):
        view, root = self.scene('''
    Monet.Scratchpad {
        id: page; objectName: "page"; anchors.fill: parent
        pads: QtObject {
            id: pads; objectName: "pads"
            property int revision: 1; property bool switching: false; property string problem: ""
            property string ident: "one"; property var choices: [{id:"one",name:"A very long pad name that must fit"},{id:"two",name:"Two"}]
            property string draft: ""; property bool dirty: false; property var pending: null
            property string lastAction: ""; property int saves: 0
            function edit(s) { draft = s; dirty = true }
            function select(action, id) { lastAction = action; if (action === "select") { ident = id; draft = "Second pad" } }
            function manage(action, value) { lastAction = action }
            function flush() { saves++; dirty = false }
            function refresh() {}
        }
    }
''')
        page = root.findChild(QObject, 'page')
        pads = root.findChild(QObject, 'pads')
        editor = root.findChild(QObject, 'scratchpadText')
        viewport = root.findChild(QObject, 'scratchpadViewport')
        document = '\n\n'.join(f'Line {i} — café 日本語 ' + 'x' * 320 for i in range(70)) + '\nLAST LINE'
        pads.setProperty('draft', document)
        QTest.qWait(50)
        for width in (432, 288):
            root.setWidth(width)
            root.setHeight(220)
            QTest.qWait(30)
            self.assertTrue(viewport.property('clip'))
            self.assertLessEqual(viewport.y() + viewport.height(), root.height())
            self.assertLessEqual(editor.width(), viewport.width())
            editor.forceActiveFocus()
            QTest.keyClick(view, Qt.Key_End, Qt.ControlModifier)
            QTest.qWait(50)
            flick = viewport.property('contentItem')
            self.assertGreater(flick.property('contentY'), 100)
            self.assertLessEqual(flick.property('contentWidth'), viewport.width())
            # The caret, not just the editor's nominal width, remains visible.
            caret = editor.property('cursorRectangle')
            point = editor.mapToItem(viewport, QPointF(caret.x(), caret.y()))
            self.assertGreaterEqual(point.y(), -1)
            self.assertLessEqual(point.y() + caret.height(), viewport.height() + 1)
        for character in ' edited':
            QTest.keyClick(view, Qt.Key(ord(character.upper())))
        self.assertTrue(pads.property('draft').endswith('LAST LINE edited'))
        page.copyNote()
        self.assertEqual(self.app.clipboard().text(), pads.property('draft'))
        QTest.keyClick(view, Qt.Key_A, Qt.ControlModifier)
        QTest.keyClick(view, Qt.Key_Backspace)
        self.assertEqual(pads.property('draft'), '')
        QTest.keyClick(view, Qt.Key_Z, Qt.ControlModifier)
        self.assertEqual(pads.property('draft'), document + ' edited')
        QTest.keyClick(view, Qt.Key_S, Qt.ControlModifier)
        self.assertGreater(pads.property('saves'), 0)
        pads.select('select', 'two')
        QTest.qWait(30)
        self.assertEqual(editor.property('text'), 'Second pad')
        self.assertTrue(editor.hasActiveFocus())
        pads.setProperty('draft', 'İ — Find [this] and then [this]')
        QTest.keyClick(view, Qt.Key_F, Qt.ControlModifier)
        search = root.findChild(QObject, 'scratchpadFind')
        self.assertTrue(search.hasActiveFocus())
        search.setProperty('text', '[this]')
        page.find(False, True)
        self.assertEqual(editor.property('selectedText'), '[this]')
        first = editor.property('selectionStart')
        page.find(False, False)
        self.assertGreater(editor.property('selectionStart'), first)
        page.find(True, False)
        self.assertEqual(editor.property('selectionStart'), first)
        self.assertEqual(pads.property('draft'), 'İ — Find [this] and then [this]')
        self.assertTrue(page.property('editingEvent'))
        page.closeEditor()
        self.assertFalse(page.property('searching'))
        self.app.clipboard().clear()

    def test_day_note_dialog_stays_bounded_and_save_cancel_are_distinct(self):
        view, root = self.scene('''
    property string committed: "original"
    Monet.DayNoteDialog { id: dialog; objectName: "dialog"; parent: C.Overlay.overlay
        onSaved: (day, text) => committed = text }
    function showNote(text) { dialog.text = text; dialog.open() }
    function saveNote() { dialog.accept() }
    function cancelNote() { dialog.reject() }
''')
        document = ('A long day note ' + 'w' * 160 + '\n') * 100
        root.showNote(document)
        QTest.qWait(50)
        dialog = root.findChild(QObject, 'dialog')
        viewport = root.findChild(QObject, 'dayNoteViewport')
        self.assertLessEqual(dialog.property('height'), root.height() - 18)
        self.assertLessEqual(dialog.property('width'), root.width() - 26)
        self.assertTrue(viewport.property('clip'))
        editor = root.findChild(QObject, 'dayNoteText')
        editor.forceActiveFocus()
        QTest.keyClick(view, Qt.Key_End, Qt.ControlModifier)
        for character in 'end':
            QTest.keyClick(view, Qt.Key(ord(character.upper())))
        root.saveNote()
        self.assertEqual(root.property('committed'), document + 'end')
        root.showNote('discard this')
        QTest.qWait(30)
        root.cancelNote()
        self.assertEqual(root.property('committed'), document + 'end')

    @unittest.skipUnless(any(Path("/usr").glob("lib*/qt6/qml/org/kde/plasma/workspace/dbus/qmldir")),
                         "requires Plasma D-Bus QML")
    def test_real_pad_service_saves_before_switching_and_rejects_stale_delete(self):
        import subprocess
        import time
        from PySide6.QtDBus import QDBusConnection
        from tools.test import stop
        sys.path.insert(0, str(ROOT / 'linux/share/monet/utilities'))
        from scratchpads import Pads
        bus = QDBusConnection.sessionBus()
        self.assertTrue(bus.registerService('org.kde.plasmashell'))
        self.addCleanup(lambda: bus.unregisterService('org.kde.plasmashell'))
        service = subprocess.Popen([sys.executable, '-c',
            'import sys; sys.path.insert(0, sys.argv[1]); from window import main; '
            'raise SystemExit(main(["notes-test", "--pad-service"], "/usr/libexec"))',
            str(ROOT / 'linux/share/monet/utilities')], stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True)
        self.addCleanup(stop, service)
        def wait(condition):
            until = time.monotonic() + 5
            while not condition() and time.monotonic() < until:
                QTest.qWait(20)
            self.assertTrue(condition())
        wait(lambda: bus.interface().isServiceRegistered('org.monet.Utilities').value())
        view, root = self.scene('''
    Monet.PadModel { id: pads; objectName: "livePads"; shown: true }
    Monet.Scratchpad { anchors.fill: parent; pads: pads }
''')
        pads = root.findChild(QObject, 'livePads')
        wait(lambda: pads.property('revision') > 0)
        first = pads.property('ident')
        pads.edit('Words kept before changing tabs')
        pads.select('new', '')
        wait(lambda: pads.property('ident') != first and not pads.property('switching'))
        pads.select('select', first)
        wait(lambda: pads.property('ident') == first and not pads.property('switching'))
        self.assertEqual(pads.property('draft'), 'Words kept before changing tabs')
        pads.manage('rename', 'Studio')
        wait(lambda: any(row['name'] == 'Studio' for row in pads.property('choices').toVariant()))
        # A second editor commits while this editor still displays the earlier revision.
        other = Pads(QSettings('Monet', 'Utilities'))
        self.addCleanup(lambda: other.db.close())
        old = other.request('view', first)['pad']
        self.assertTrue(other.request('save', first, old['revision'], 'From the floating editor')['ok'])
        pads.manage('delete', '')
        wait(lambda: bool(pads.property('problem')))
        self.assertEqual(other.request('view', first)['pad']['body'], 'From the floating editor')
        self.assertEqual(pads.property('draft'), 'Words kept before changing tabs')
        pads.refresh()
        wait(lambda: pads.property('draft') == 'From the floating editor')
        self.assertFalse(pads.property('problem'))

    def test_notch_rename_delete_validate_revision_and_keep_last_pad(self):
        sys.path.insert(0, str(ROOT / 'linux/share/monet/utilities'))
        from scratchpads import Pads
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_DATA_HOME=directory):
            settings = QSettings(directory + '/pads.ini', QSettings.IniFormat)
            store = Pads(settings)
            first = store.request('view')['pad']
            def request(action, pad, value=''):
                return json.loads(store.for_notch(json.dumps(dict(action=action, id=pad['id'], revision=pad['revision'], value=value))))
            saved = request('save', first, 'Keep these words')['pad']
            renamed = request('rename', saved, 'Ideas')
            self.assertTrue(renamed['ok'])
            self.assertEqual(renamed['pad']['body'], 'Keep these words')
            self.assertEqual(renamed['pad']['name'], 'Ideas')
            self.assertFalse(request('delete', saved)['ok'])
            self.assertFalse(request('rename', renamed['pad'], ' \n ')['ok'])
            self.assertEqual(store.request('view')['pad']['body'], 'Keep these words')
            deleted = request('delete', renamed['pad'])
            self.assertTrue(deleted['ok'])
            self.assertEqual(len(deleted['pads']), 1)
            self.assertNotEqual(deleted['pad']['id'], saved['id'])
            self.assertEqual(deleted['pad']['body'], '')
            recovered = request('save', saved, 'A late edit from another window')
            self.assertTrue(recovered['recovered'])
            self.assertEqual(recovered['pad']['body'], 'A late edit from another window')
            store.db.close()
