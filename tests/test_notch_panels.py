"""Native island controls route actions; tool filters keep their labels and keyboard behavior."""
from pathlib import Path
import tempfile
import unittest

try:
    from PySide6.QtCore import QObject, QPoint, QPointF, Qt, QUrl
    from PySide6.QtGui import QGuiApplication, QWheelEvent
    from PySide6.QtQuick import QQuickView
    from PySide6.QtQuickControls2 import QQuickStyle
    from PySide6.QtTest import QTest
except ImportError:
    QQuickView = None

UI = Path(__file__).resolve().parents[1] / 'linux/share/plasma/plasmoids/org.monet.notch/contents/ui'


@unittest.skipUnless(QQuickView, 'requires Qt Quick')
class Panels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QQuickStyle.setStyle("org.kde.desktop")
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def scene(self, body):
        self.app = QGuiApplication.instance() or QGuiApplication([])
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        source = Path(folder.name) / 'Panel.qml'
        source.write_text('import QtQuick\nimport "' + UI.as_uri() + '" as Monet\n' + body)
        view = QQuickView()
        errors = []
        view.engine().warnings.connect(lambda values: errors.extend(e.toString() for e in values))
        view.setSource(QUrl.fromLocalFile(str(source)))
        self.assertEqual(view.status(), QQuickView.Ready, [e.toString() for e in view.errors()])
        view.show()
        QTest.qWait(80)
        self.addCleanup(view.close)
        self.addCleanup(lambda: self.assertFalse(errors, errors))
        return view, view.rootObject()

    def test_controls_offer_real_shortcuts_without_audio_or_brightness_devices(self):
        view, page = self.scene('''Monet.IslandControls {
            width: 288; height: 264; soundAvailable: false; brightnessAvailable: false
            function i18n(s) { return s }
            property string chosen: ""
            shortcuts: [{key:"notes",label:"Notes",icon:"document-edit",color:"white"},
                {key:"time",label:"Time",icon:"chronometer",color:"white"},
                {key:"awake",label:"Keep awake",icon:"preferences-system-power-management",color:"white"}]
            onSelected: key => chosen = key
        }''')
        self.assertTrue(page.property('hasControls'))
        # Repeater delegates are visual children, not necessarily QObject children.
        pending, buttons = [page], {}
        while pending:
            item = pending.pop()
            if item.objectName().startswith('notch-control-'):
                buttons[item.objectName().removeprefix('notch-control-')] = item
            pending.extend(item.childItems())
        self.assertEqual(set(buttons), {'notes', 'time', 'awake'})
        for key, item in buttons.items():
            point = item.mapToScene(QPointF(item.width()/2, item.height()/2)).toPoint()
            QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, point)
            self.assertEqual(page.property('chosen'), key)
        page.setProperty('shortcuts', [])
        QTest.qWait(30)
        self.assertFalse(page.property('hasControls'))

    def test_tools_search_category_popup_and_keyboard_selection(self):
        view, page = self.scene('''Monet.ToolDirectory {
            width: 288; height: 264
            function i18n(s) { return s }
            rows: [{key:"notes",label:"Scratchpad",terms:"notes",group:"text",icon:"document-edit"},
                   {key:"shelf",label:"File shelf",terms:"files",group:"files",icon:"folder"}]
            groups: [{key:"all",label:"All tools"},{key:"text",label:"Text"},{key:"files",label:"Files"}]
            hidden: []; favorites: []; group: "all"; query: ""
            property string chosen: ""
            onFilterChanged: (g,q) => { group=g; query=q }
            onSelected: key => chosen=key
        }''')
        category = page.findChild(QObject, 'notchToolCategory')
        category.forceActiveFocus()
        QTest.keyClick(view, Qt.Key_Space)
        QTest.qWait(250)
        self.assertTrue(page.property('menuOpen'))
        QTest.keyClick(view, Qt.Key_Down)
        QTest.keyClick(view, Qt.Key_Return)
        QTest.qWait(50)
        self.assertEqual(page.property('group'), 'text')
        self.assertEqual(category.property('displayText'), 'Text')
        page.focusSearch()
        search = page.findChild(QObject, 'notchToolSearch')
        search.forceActiveFocus()
        for character in 'files':
            QTest.keyClick(view, Qt.Key(ord(character.upper())))
        QTest.keyClick(view, Qt.Key_Return)
        self.assertEqual(page.property('chosen'), 'shelf')
        self.assertEqual(page.property('matches').toVariant()[0]['key'], 'shelf')
        page.closeEditor()
        self.assertEqual(page.property('query'), '')
        self.assertFalse(page.property('editingEvent'))

    def test_tools_grid_reaches_later_columns_and_keeps_long_labels_inside_tiles(self):
        view, page = self.scene('''Monet.ToolDirectory {
            width: 288; height: 264
            function i18n(s) { return s }
            rows: Array.from({length: 35}, (_,i) => ({key:"tool-"+i,
                label:"Tool " + String(i).padStart(2,"0") + " with a very long title", terms:"",group:"all",icon:"document-edit"}))
            groups: [{key:"all",label:"All tools"}]
            hidden: ["tool-3"]; favorites: ["tool-9"]; group: "all"; query: ""
            property string chosen: ""
            onFilterChanged: (g,q) => { group=g; query=q }
            onSelected: key => chosen=key
        }''')
        grid = page.findChild(QObject, 'notchToolGrid')
        self.assertGreater(grid.property('contentWidth'), grid.width())
        matches = page.property('matches').toVariant()
        self.assertEqual(matches[0]['key'], 'tool-9')
        self.assertNotIn('tool-3', [row['key'] for row in matches])
        grid.forceActiveFocus()
        QTest.keyClick(view, Qt.Key_End)
        QTest.keyClick(view, Qt.Key_Return)
        QTest.qWait(250)
        self.assertEqual(page.property('chosen'), matches[-1]['key'])
        self.assertGreater(grid.property('contentX'), 0)
        pending = [page]
        buttons = []
        while pending:
            item = pending.pop()
            if item.objectName().startswith('notch-tool-'):
                buttons.append(item)
            pending.extend(item.childItems())
        self.assertTrue(buttons)
        for button in buttons:
            for child in button.childItems():
                for label in child.childItems():
                    if label.metaObject().className() == 'QQuickText':
                        self.assertLessEqual(label.x() + label.width(), button.width() + 1)
                        self.assertLessEqual(label.y() + label.height(), button.height() + 1)

    def test_tool_page_dots_snap_to_distinct_pages_and_filter_resets_the_last_page(self):
        view, page = self.scene('''Monet.ToolDirectory {
            width: 414; height: 257
            function i18n(s) { return s }
            rows: Array.from({length: 74}, (_,i) => ({key:"tool-"+i,
                label:"Tool " + String(i).padStart(2,"0"), terms:"",group:"all",icon:"document-edit"}))
            groups: [{key:"all",label:"All tools"},{key:"favorites",label:"Favorites"}]
            hidden: []; favorites: ["tool-3","tool-9"]; group: "all"; query: ""
            onFilterChanged: (g,q) => { group=g; query=q }
        }''')
        grid = page.findChild(QObject, 'notchToolGrid')
        dots = page.findChild(QObject, 'notchToolPageDots')

        def items():
            pending, found = [page], []
            while pending:
                item = pending.pop()
                found.append(item)
                pending.extend(item.childItems())
            return found

        def keys_in_view():
            return {item.objectName() for item in items()
                    if item.objectName().startswith('notch-tool-tool-') and item.isVisible()
                    and -0.1 <= item.mapToItem(grid, QPointF()).x() < grid.width() - 0.1}

        capacity = grid.property('capacity')
        self.assertGreater(dots.property('count'), 1)
        # GridView batches geometry changes while its capacity settles on open.
        grid.forceLayout()
        first = keys_in_view()
        self.assertEqual(len(first), capacity)
        dot = next(item for item in items() if item.objectName() == 'notch-tool-dot-1')
        QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier,
                         dot.mapToScene(QPointF(dot.width()/2,dot.height()/2)).toPoint())
        QTest.qWait(220)
        self.assertEqual(grid.property('currentPage'), 1)
        self.assertAlmostEqual(grid.property('contentX'), grid.width(), delta=0.1)
        self.assertTrue(first.isdisjoint(keys_in_view()))
        self.assertEqual(len(keys_in_view()), capacity)

        # A wheel step moves a whole page and keeps the indicator in sync.
        position = grid.mapToScene(QPointF(grid.width()/2,grid.height()/2))
        wheel = QWheelEvent(position, position, QPoint(), QPoint(0,-120),
                            Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
        QGuiApplication.sendEvent(view, wheel)
        QTest.qWait(220)
        self.assertEqual(grid.property('currentPage'), 2)
        self.assertEqual(dots.property('currentIndex'), 2)
        QTest.keyClick(view, Qt.Key_End)
        QTest.qWait(220)
        last = grid.property('pageCount') - 1
        self.assertAlmostEqual(grid.property('contentX'), last * grid.width(), delta=0.1)
        self.assertEqual(len(keys_in_view()), 74 - last * capacity)

        page.setProperty('group', 'favorites')
        QTest.qWait(100)
        self.assertEqual(grid.property('currentPage'), 0)
        self.assertAlmostEqual(grid.property('contentX'), 0, delta=0.1)
        self.assertEqual(keys_in_view(), {'notch-tool-tool-3','notch-tool-tool-9'})
        self.assertFalse(dots.isVisible())

    def test_continuous_trackpad_scroll_tracks_pixels_and_wheel_bursts_retarget(self):
        view, page = self.scene('''Monet.ToolDirectory {
            width: 414; height: 313
            function i18n(s) { return s }
            rows: Array.from({length:74},(_,i)=>({key:"tool-"+i,label:"Tool "+i,terms:"",group:"all",icon:"document-edit"}))
            groups: [{key:"all",label:"All tools"}]
            hidden: []; favorites: []; group:"all"; query:""
        }''')
        grid = page.findChild(QObject, 'notchToolGrid')
        self.assertEqual(grid.property('columns'), 4)
        self.assertEqual(grid.property('rowsVisible'), 3)
        point = grid.mapToScene(QPointF(grid.width()/2, grid.height()/2))

        def wheel(pixels=0, angle=0, phase=Qt.NoScrollPhase):
            event = QWheelEvent(point, point, QPoint(pixels,0), QPoint(0,angle),
                                Qt.NoButton, Qt.NoModifier, phase, False)
            QGuiApplication.sendEvent(view, event)
            QTest.qWait(10)

        # Every update (including momentum) follows the fingers immediately.
        wheel(-60, phase=Qt.ScrollBegin)
        self.assertAlmostEqual(grid.property('contentX'), 60, delta=0.1)
        wheel(-60, phase=Qt.ScrollUpdate)
        self.assertAlmostEqual(grid.property('contentX'), 120, delta=0.1)
        wheel(-60, phase=Qt.ScrollMomentum)
        self.assertAlmostEqual(grid.property('contentX'), 180, delta=0.1)
        wheel(-500, phase=Qt.ScrollUpdate)
        wheel(phase=Qt.ScrollEnd)
        QTest.qWait(250)
        self.assertAlmostEqual(grid.property('contentX'), grid.width()*2, delta=0.1)

        # Retarget rapid discrete steps, including a reversal, without dropping
        # input or waiting for a separate animation to finish for every tick.
        for _ in range(3):
            wheel(angle=-120)
            QTest.qWait(15)
        wheel(angle=120)
        QTest.qWait(250)
        self.assertEqual(grid.property('currentPage'), 4)
        page.setProperty('query', 'does not exist')
        QTest.qWait(100)
        self.assertAlmostEqual(grid.property('contentX'), 0, delta=0.1)
