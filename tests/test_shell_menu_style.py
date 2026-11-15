"""Native desktop menus use the shipped style, with normal keyboard actions."""
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from tests.test_look import ROOT
try:
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import QPalette, QColor, QIcon
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMenu, QStyleFactory
except ImportError:
    QApplication = None


@unittest.skipUnless(QApplication, 'Qt Widgets')
class ShellMenuStyle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.previous = {key: os.environ.get(key) for key in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'QT_STYLE_OVERRIDE')}
        cls.config = Path(cls.temp.name) / 'config'; cls.data = Path(cls.temp.name) / 'data'
        (cls.config / 'Kvantum').mkdir(parents=True)
        (cls.config / 'Kvantum/kvantum.kvconfig').write_text('[General]\ntheme=Monet\n')
        shutil.copytree(ROOT / 'linux/share/Kvantum/Monet', cls.config / 'Kvantum/Monet')
        os.environ.update(XDG_CONFIG_HOME=str(cls.config), XDG_DATA_HOME=str(cls.data), QT_STYLE_OVERRIDE='kvantum')
        cls.app = QApplication.instance() or QApplication([])
        if 'kvantum' not in QStyleFactory.keys(): raise unittest.SkipTest('Kvantum runtime')
        cls.app.setStyle('kvantum')
        palette = QPalette()
        for role, color in ((QPalette.Window, '#f3f1ec'), (QPalette.Base, '#fbfaf7'),
                            (QPalette.Text, '#1c1b19'), (QPalette.WindowText, '#1c1b19'),
                            (QPalette.ButtonText, '#1c1b19'), (QPalette.Highlight, '#357f72')):
            palette.setColor(role, QColor(color))
        cls.app.setPalette(palette)

    @classmethod
    def tearDownClass(cls):
        for key, value in cls.previous.items():
            if value is None: os.environ.pop(key, None)
            else: os.environ[key] = value
        cls.temp.cleanup()

    def test_shipped_menu_style_has_readable_rows_and_keeps_keyboard_activation(self):
        self.assertEqual(self.app.style().objectName(), 'kvantum')
        menu = QMenu()
        menu.addMenu(QIcon.fromTheme('document-new'), 'Create New')
        menu.addAction(QIcon.fromTheme('edit-paste'), 'Paste Clipboard Contents…', 'Ctrl+V')
        menu.addAction(QIcon.fromTheme('edit-undo'), 'Undo: Trash', 'Ctrl+Z')
        menu.addMenu(QIcon.fromTheme('view-grid'), 'Icons')
        menu.addSeparator()
        menu.addAction(QIcon.fromTheme('utilities-terminal'), 'Open Terminal')
        menu.addAction(QIcon.fromTheme('list-add'), 'Add or Manage Widgets…')
        menu.addAction(QIcon.fromTheme('view-group'), 'Desktop stacks'); menu.addSeparator()
        menu.addAction(QIcon.fromTheme('preferences-desktop-display'), 'Display settings')
        personalize = menu.addAction(QIcon.fromTheme('preferences-desktop-wallpaper'), 'Personalize')
        triggered = []; personalize.triggered.connect(lambda: triggered.append(True))
        menu.show(); QTest.qWait(60)
        for action in menu.actions():
            self.assertTrue(menu.rect().contains(menu.actionGeometry(action)))
        if os.environ.get('MONET_MENU_CAPTURE'): menu.grab().save(os.environ['MONET_MENU_CAPTURE'])
        menu.setActiveAction(personalize); QTest.keyClick(menu, Qt.Key_Return)
        self.assertEqual(triggered, [True]); self.assertFalse(menu.isVisible())
        menu.deleteLater(); QTest.qWait(10)

    def test_wallpaper_menu_compiles_with_native_plasma_actions(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'ui'
            shutil.copytree(ROOT / 'linux/share/plasma/wallpapers/org.monet.hours/contents/ui', folder)
            for source in (ROOT / 'linux/share/monet/widgets').glob('*.qml'):
                shutil.copy2(source, folder / source.name)
            engine = QQmlEngine()
            component = QQmlComponent(engine, QUrl.fromLocalFile(str(folder / 'main.qml')))
            for _ in range(30):
                if not component.isLoading(): break
                QTest.qWait(10)
            self.assertEqual(component.status(), QQmlComponent.Ready,
                             '\n'.join(error.toString() for error in component.errors()))
