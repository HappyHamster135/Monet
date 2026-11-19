"""Apps (monet-games --apps): every app in the menu in a library of its own, as Games has games.
What it lists and leaves out, where each came from, and the window's Open, Store and Remove."""
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]
try:
    from PySide6.QtCore import QObject, QPointF, QTimer, QUrl, Signal, Slot, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401 (windows come back as Quick's)
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False


class Library(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.q = quick_helper()
        self.home = self.root / "home/applications"
        self.flatpak = self.root / "flatpak/exports/share/applications"
        self.system = self.root / "usr/applications"
        data_home = patch.object(self.q, "DATA_HOME", self.root / "home")
        data_home.start(); self.addCleanup(data_home.stop)

    def entry(self, folder, name, text):
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[Desktop Entry]\n" + ("" if "Type=" in text else "Type=Application\n") + text)
        return path

    def library(self, used=None):
        return {app["id"]: app for app in self.q.app_library([self.home, self.flatpak, self.system], used or {})}

    def test_what_it_lists_and_where_each_came_from(self):
        self.entry(self.flatpak, "app.zen_browser.zen.desktop", "Name=Zen Browser\nComment=Browse the web\n"
                   "Icon=app.zen_browser.zen\nCategories=Network;WebBrowser;\nX-Flatpak=app.zen_browser.zen\nExec=zen\n")
        self.entry(self.system, "org.kde.dolphin.desktop", "Name=Dolphin\nName[sv]=Filer\nGenericName=File Manager\n"
                   "Icon=system-file-manager\nCategories=Qt;KDE;System;FileTools;FileManager;\nExec=dolphin\n")
        self.entry(self.home, "monet-local-0123456789abcdef01234567.desktop", "Name=True Borders\nExec=/opt/tb\n")
        self.entry(self.home, "monet-program-cardwire.desktop", "Name=Cardwire\nComment=A Windows program\n"
                   "Exec=monet-quick program-start 00\nCategories=X-Monet-Windows-Programs;\n")
        with patch.dict("os.environ", {"LANGUAGE": "sv_SE"}):
            apps = self.library({"org.kde.dolphin.desktop": 1700000000})
        self.assertEqual(sorted(apps), ["app.zen_browser.zen.desktop", "monet-local-0123456789abcdef01234567.desktop",
                                        "monet-program-cardwire.desktop", "org.kde.dolphin.desktop"])
        zen = apps["app.zen_browser.zen.desktop"]
        self.assertEqual((zen["source"], zen["store"], zen["group"], zen["detail"], zen["removable"]),
                         ("store", "app.zen_browser.zen", "internet", "Browse the web", False))
        files = apps["org.kde.dolphin.desktop"]
        self.assertEqual((files["name"], files["source"], files["group"], files["detail"], files["last"]),
                         ("Filer", "system", "utilities", "File Manager", 1700000000))
        mine = apps["monet-local-0123456789abcdef01234567.desktop"]
        self.assertEqual((mine["source"], mine["removable"], mine["icon"]), ("mine", True, "application-x-executable"))
        self.assertEqual(apps["monet-program-cardwire.desktop"]["source"], "windows")

    def test_what_the_menu_leaves_out_and_games_launchers_add(self):
        self.entry(self.system, "hidden.desktop", "Name=Hidden\nNoDisplay=true\nExec=x\n")
        self.entry(self.system, "gnome-only.desktop", "Name=GNOME only\nOnlyShowIn=GNOME;\nExec=x\n")
        self.entry(self.system, "not-kde.desktop", "Name=Not here\nNotShowIn=KDE;\nExec=x\n")
        self.entry(self.system, "gone.desktop", "Name=Gone\nTryExec=/nonexistent/program\nExec=x\n")
        self.entry(self.system, "link.desktop", "Type=Link\nName=A link\nURL=https://example.org\n")
        self.entry(self.home, "Counter-Strike 2.desktop", "Name=Counter-Strike 2\nExec=steam steam://rungameid/730\n")
        self.entry(self.system, "org.kde.kpat.desktop", "Name=Patience\nCategories=Qt;KDE;Game;CardGame;\nExec=kpat\n")
        # Someone's own copy hides the system's, as in the menu.
        self.entry(self.home, "org.kde.kate.desktop", "Name=Kate\nNoDisplay=true\nExec=kate\n")
        self.entry(self.system, "org.kde.kate.desktop", "Name=Kate\nExec=kate\n")
        self.assertEqual(list(self.library()), ["org.kde.kpat.desktop"])
        self.assertEqual(self.library()["org.kde.kpat.desktop"]["group"], "games")

    def test_last_opened_is_what_kdes_menu_notes(self):
        database = self.root / "database"
        with sqlite3.connect(database) as db:
            db.execute("CREATE TABLE ResourceScoreCache (usedActivity TEXT, initiatingAgent TEXT, "
                       "targettedResource TEXT, scoreType INT, cachedScore REAL, firstUpdate INT, lastUpdate INT)")
            db.executemany("INSERT INTO ResourceScoreCache VALUES ('a', 'kicker', ?, 0, 1, 0, ?)",
                           [("applications:org.kde.dolphin.desktop", 100), ("applications:org.kde.dolphin.desktop", 300),
                            ("file:///home/a/notes.txt", 500)])
        self.assertEqual(self.q.last_opened(database), {"org.kde.dolphin.desktop": 300})
        self.assertEqual(self.q.last_opened(self.root / "none"), {})

    def test_only_a_shortcut_added_here_is_removed(self):
        mine = self.entry(self.home, "monet-local-0123456789abcdef01234567.desktop", "Name=Mine\nExec=x\n")
        other = self.entry(self.home, "org.example.Tool.desktop", "Name=Tool\nExec=x\n")
        self.assertFalse(self.q.app_remove("org.example.Tool.desktop", self.home))
        self.assertFalse(self.q.app_remove("../usr/applications/monet-local-0123456789abcdef01234567.desktop", self.home))
        self.assertTrue(self.q.app_remove(mine.name, self.home))
        self.assertFalse(mine.exists())
        self.assertTrue(other.exists())
        self.assertFalse(self.q.app_remove(mine.name, self.home))

    def test_the_store_opens_at_an_app_and_nothing_else(self):
        with patch.object(self.q.subprocess, "Popen") as start:
            self.q.main(["store-app", "app.zen_browser.zen"])
            self.q.main(["store-app", "--worker"])
            self.q.main(["store-app", "x; rm -rf ~"])
        self.assertEqual([c.args[0][1:] for c in start.call_args_list], [["app.zen_browser.zen"]])

    def test_its_menu_entry_and_window(self):
        entry = (ROOT / "linux/share/applications/monet-apps.desktop").read_text()
        self.assertIn("Exec=@LIBEXECDIR@/monet-games --apps\n", entry)
        host = (ROOT / "linux/libexec/monet-games").read_text()
        self.assertIn('apps = sys.argv[1:2] == ["--apps"]', host)
        self.assertIn('''engine.load(QUrl.fromLocalFile(f"{DATADIR}/monet/games/{'Apps' if apps else 'Games'}.qml"))''', host)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('put 644 "$SRC/share/applications/monet-apps.desktop" "$DATADIR/applications/monet-apps.desktop"', install)
        self.assertIn('"$PREFIX/share/applications/monet-apps.desktop"', (ROOT / "linux/uninstall.sh").read_text())


if QT:
    class Helper(QObject):
        """monet-games' helper, answering from a fixture and noting what the window asked."""
        done = Signal(int, str, int, str)
        wanted = Signal(str)

        def __init__(self, library):
            super().__init__()
            self.library, self.asked, self.ticket = library, [], 0

        @Slot("QVariantList", result=int)
        def run(self, command):
            self.ticket += 1
            ticket, command = self.ticket, [str(part) for part in command]
            self.asked.append(command)
            result = {"ok": True}
            if command[1:] == ["app-library"]: result = self.library
            elif command[1] == 'app-removal-review':
                flatpak = bytes.fromhex(command[2]).decode() == 'app.zen_browser.zen.desktop'
                result.update(kind='flatpak' if flatpak else 'shortcut', token='reviewed', eraseSupported=flatpak,
                              data=['/private/.var/app/app.zen_browser.zen'] if flatpak else [])
            elif command[1] == 'app-uninstall': result['removed'] = True
            out = json.dumps(result)
            QTimer.singleShot(0, lambda: self.done.emit(ticket, out, 0, ""))
            return ticket


@unittest.skipUnless(QT, "requires PySide6 and Kirigami")
class Window(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        loader = importlib.machinery.SourceFileLoader("apps_games", str(ROOT / "linux/libexec/monet-games"))
        cls.games = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(cls.games)

    def setUp(self):
        now = int(time.time())
        self.library = [
            {"id": "app.zen_browser.zen.desktop", "name": "Zen Browser", "detail": "Browse the web", "icon": "zen",
             "source": "store", "store": "app.zen_browser.zen", "group": "internet", "last": now - 60, "removable": False},
            {"id": "org.kde.dolphin.desktop", "name": "Files", "detail": "Your files", "icon": "system-file-manager",
             "source": "system", "store": "", "group": "utilities", "last": 0, "removable": False},
            {"id": "monet-local-0123456789abcdef01234567.desktop", "name": "True Borders", "detail": "",
             "icon": "application-x-executable", "source": "mine", "store": "", "group": "other", "last": 0,
             "removable": True}]
        self.helper = Helper(self.library)
        self.engine = QQmlApplicationEngine(); self.errors = []
        self.engine.warnings.connect(lambda values: self.errors.extend(v.toString() for v in values))
        self.words = self.games.Words()
        context = self.engine.rootContext(); context.setContextObject(self.words)
        for name, value in {"helper": self.helper, "blurBehind": False,
                            "art": (ROOT / "linux/share/monet/settings").as_uri() + "/",
                            "brush": (ROOT / "linux/share/monet/textures/brush.png").as_uri()}.items():
            context.setContextProperty(name, value)
        self.app.setOrganizationName("monet-app-library-tests")
        self.engine.load(QUrl.fromLocalFile(str(ROOT / "linux/share/monet/games/Apps.qml")))
        self.assertTrue(self.engine.rootObjects(), self.errors)
        self.window = self.engine.rootObjects()[0]
        self.window.setWidth(760); self.window.setHeight(520)
        QTest.qWait(200)

    def tearDown(self):
        self.window.close(); self.engine.deleteLater(); QTest.qWait(5)
        self.assertEqual([e for e in self.errors if "QSettings" not in e], [])

    def item(self, name):
        todo = [self.window.contentItem()]
        while todo:
            item = todo.pop()
            if item.objectName() == name:
                return item
            todo.extend(item.childItems())
        self.fail("Missing " + name)

    def press(self, name):
        item = self.item(name)
        parent = item.parentItem()
        while parent:
            if parent.property('contentY') is not None and parent.property('contentHeight') is not None:
                local = item.mapToItem(parent, QPointF(0, 0))
                parent.setProperty('contentY', max(0, min(parent.property('contentHeight') - parent.height(), parent.property('contentY') + local.y() - 40)))
                QTest.qWait(30)
            parent = parent.parentItem()
        point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.qWait(60)

    def test_sections_search_and_a_page_with_what_can_be_done(self):
        grid = self.item("appsGrid")
        self.assertEqual(grid.property("count"), 3)
        self.window.setProperty("section", "store"); QTest.qWait(50)
        self.assertEqual(grid.property("count"), 1)
        self.window.setProperty("section", "all"); self.window.setProperty("query", "files"); QTest.qWait(50)
        self.assertEqual(grid.property("count"), 1)
        self.window.setProperty("query", "")
        self.window.setProperty("pageId", "app.zen_browser.zen.desktop"); QTest.qWait(80)
        self.assertTrue(self.item("appPage").isVisible())
        self.assertTrue(self.item("appStore").isVisible())
        self.assertTrue(self.item("appRemove").isVisible())
        self.press("appOpen"); self.press("appStore")
        self.assertIn(["helper", "menu-app-open", "app.zen_browser.zen.desktop".encode().hex()], self.helper.asked)
        self.assertIn(["helper", "store-app", "app.zen_browser.zen"], self.helper.asked)

    def test_a_shortcut_added_here_is_removed_after_asking(self):
        self.window.setProperty("pageId", "monet-local-0123456789abcdef01234567.desktop"); QTest.qWait(80)
        self.assertFalse(self.item("appStore").isVisible())
        self.press("appRemove")
        self.assertFalse(any(c[1] == "app-remove" for c in self.helper.asked))
        self.press("appRemoveConfirm")
        self.assertIn(["helper", "app-remove", "monet-local-0123456789abcdef01234567.desktop".encode().hex()],
                      self.helper.asked)
        QTest.qWait(80)
        self.assertEqual(self.window.property("pageId"), "")

    def test_store_apps_uninstall_with_data_by_default_and_offer_keep_data(self):
        for keep in (False, True):
            self.window.setProperty('pageId', 'app.zen_browser.zen.desktop'); QTest.qWait(80)
            self.press('appRemove')
            self.assertTrue(self.item('eraseAppData').property('checked'))
            self.assertFalse(any(c[1] == 'app-uninstall' for c in self.helper.asked))
            if keep: self.press('eraseAppData')
            self.press('appUninstallConfirm')
            self.assertIn(['helper', 'app-uninstall', 'app.zen_browser.zen.desktop'.encode().hex(),
                           'reviewed', 'keep' if keep else 'erase'], self.helper.asked)
            self.helper.asked.clear()

    def test_the_icons_fit_a_small_window(self):
        grid = self.item("appsGrid")
        self.assertGreaterEqual(grid.property("columns"), 3)
        self.assertLessEqual(grid.property("cellWidth") * grid.property("columns"), grid.width() + 1)

    def test_opening_again_restores_a_maximized_window(self):
        self.window.showMaximized()
        QTest.qWait(30)
        self.window.showMinimized()
        QTest.qWait(30)
        self.helper.wanted.emit("")
        QTest.qWait(30)
        self.assertEqual(self.window.visibility(), QQuickWindow.Maximized)


if __name__ == "__main__":
    unittest.main()
