"""Exercise real wheel hit targets, keyboard selection, and the catalog entry points."""
from configparser import ConfigParser
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULES = Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"
sys.path.insert(0, str(MODULES))
from actions import ACTIONS, find_tools

try:
    from PySide6.QtCore import QPoint, QSettings, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from favorites_wheel import FavoritesWheel
    from window import Receiver, Window
except ImportError:
    FavoritesWheel = None


class WheelShortcut(unittest.TestCase):
    def test_global_shortcut_and_launcher_action_open_the_same_wheel(self):
        directory = MODULES.parents[1] / "applications"
        desktop = ConfigParser(interpolation=None)
        desktop.read(directory / "monet-utilities.desktop")
        shortcut = ConfigParser(interpolation=None)
        shortcut.read(directory / "org.monet.FavoritesWheel.desktop")
        entry = shortcut["Desktop Entry"]
        self.assertEqual(entry["Exec"], desktop["Desktop Action Wheel"]["Exec"] + " --shortcut")
        self.assertTrue(entry.getboolean("NoDisplay"))
        self.assertEqual(entry["X-KDE-Shortcuts"], "Meta+Alt+W")


@unittest.skipUnless(FavoritesWheel, "requires Qt widgets")
class Wheel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.settings = QSettings(folder + "/utilities.ini", QSettings.IniFormat)
        with patch("window.QSettings", return_value=self.settings):
            self.window = Window(folder)
        self.receiver = Receiver(self.window)
        self.addCleanup(self.cleanup_widgets)

    def cleanup_widgets(self):
        for widget in (self.window.favorites_wheel, self.window.quick_panel, self.window):
            if widget:
                widget.hide()
                widget.deleteLater()
        self.app.processEvents()

    def favorites(self, keys, hidden=()):
        self.settings.setValue("favorites", json.dumps(keys))
        self.settings.setValue("hidden", json.dumps(list(hidden)))
        self.settings.sync()

    def test_mouse_sectors_are_disjoint_from_center_and_activate_once(self):
        keys = ["shelf", "ports", "notes", "apps", "calendars", "downloads", "display", "files"]
        self.favorites(keys)
        self.window.Open(["wheel"])
        wheel = self.window.favorites_wheel
        self.assertFalse(self.window.isVisible())
        calls = []
        wheel.chosen.disconnect(self.window.open_favorite)
        wheel.chosen.connect(calls.append)
        for i, key in enumerate(keys):
            if i:
                self.window.Open(["wheel"])
            center = wheel.rect().center()
            self.assertFalse(any(button.hitButton(center) for button in wheel.buttons))
            angle = math.tau*i/len(keys) - math.pi/2
            x = round(center.x() + .36*wheel.width()*math.cos(angle))
            y = round(center.y() + .36*wheel.height()*math.sin(angle))
            point = QPoint(x, y)
            button = wheel.childAt(point)
            self.assertIs(button, wheel.buttons[i])
            self.assertEqual(button.accessibleName(), ACTIONS[key].name)
            self.assertEqual([b.key for b in wheel.buttons if b.hitButton(point)], [key])
            QTest.mouseClick(button, Qt.LeftButton, Qt.NoModifier, point)
            self.assertFalse(wheel.isVisible())
        self.assertEqual(calls, keys)

    def test_arrows_follow_hover_wrap_and_escape_dismisses(self):
        self.favorites(["shelf", "notes", "ports"])
        self.window.Open(["wheel"])
        wheel = self.window.favorites_wheel
        chosen = []
        wheel.chosen.disconnect(self.window.open_favorite)
        wheel.chosen.connect(chosen.append)
        wheel.highlight(wheel.buttons[1])
        self.assertEqual(wheel.label.text(), ACTIONS["notes"].name)
        QTest.keyClick(wheel.buttons[0], Qt.Key_Right)
        self.assertIs(wheel.current, wheel.buttons[2])
        QTest.keyClick(wheel.current, Qt.Key_Down)
        self.assertIs(wheel.current, wheel.buttons[0])
        QTest.keyClick(wheel.current, Qt.Key_Left)
        QTest.keyClick(wheel.current, Qt.Key_Return)
        self.assertEqual(chosen, ["ports"])
        self.window.Open(["wheel"])
        QTest.keyClick(wheel.current, Qt.Key_Escape)
        self.assertFalse(wheel.isVisible())
        self.assertEqual(chosen, ["ports"])
        self.assertFalse(self.window.isVisible())

    def test_reopens_with_current_favorites_and_rejects_stale_requests(self):
        self.favorites(["wheel", "notes", "shelf", "ports"], ["shelf"])
        self.window.Open(["wheel"])
        wheel = self.window.favorites_wheel
        self.assertEqual([b.key for b in wheel.buttons], ["notes", "ports"])
        self.window.Open(["wheel"])
        self.assertFalse(wheel.isVisible())
        self.favorites(["files"])
        self.window.Open(["wheel"])
        self.assertEqual([b.key for b in wheel.buttons], ["files"])
        self.assertTrue(wheel.buttons[0].hitButton(QPoint(wheel.width()//2, 10)))
        self.assertTrue(wheel.buttons[0].hitButton(QPoint(wheel.width()//2, wheel.height()-10)))
        self.window.Open(["wheel"])
        self.assertFalse(self.receiver.ShowWheel("old-request", "640"))
        self.assertFalse(self.receiver.ShowWheel("1", "-4"))
        self.favorites(["shelf"], ["wheel"])
        self.window.Open(["wheel"])
        self.assertFalse(wheel.isVisible())
        self.assertFalse(self.window.isVisible())

    def test_shortcut_defers_catalog_work_until_a_window_needs_it(self):
        self.favorites(["shelf", "notes"])
        with patch("window.QSettings", return_value=self.settings), patch("window.find_tools", wraps=find_tools) as search:
            window = Window(self.window.helpers, defer_catalog=True)
            self.addCleanup(window.deleteLater)
            window.Open(["wheel"])
            self.addCleanup(window.favorites_wheel.deleteLater)
            search.assert_not_called()
            self.assertFalse(window.isVisible())
            window.favorites_wheel.hide()
            window.Open(["shelf"])
            self.assertTrue(window.isVisible())
            window.home()
            self.assertGreater(window.catalog.count(), 1)
            window.close()

    def test_empty_favorites_open_the_existing_editor(self):
        self.favorites(["wheel"])
        self.window.Open(["wheel"])
        self.assertIsNone(self.window.favorites_wheel)
        self.assertFalse(self.window.isVisible())
        self.assertTrue(self.window.quick_panel.isVisible())
        self.assertEqual(self.window.quick_panel.stack.currentIndex(), 1)

    def test_floating_radial_uses_saved_slots_and_preserves_holes(self):
        self.favorites(['ports'],['snippets'])
        self.settings.setValue('notchRadial',json.dumps(['emoji','','text-tools','snippets','','','','']))
        self.window.Open(['radial'])
        wheel=self.window.favorites_wheel
        self.assertTrue(wheel.isVisible());self.assertFalse(self.window.isVisible())
        self.assertEqual(wheel.active_id,'radial');self.assertEqual(wheel.mode,'click')
        self.assertEqual([b.key for b in wheel.buttons],['emoji','','text-tools','','','','',''])
        self.assertEqual([b.isEnabled() for b in wheel.buttons],[True,False,True,False,False,False,False,False])
        chosen=[];wheel.chosen.disconnect(self.window.open_favorite);wheel.chosen.connect(chosen.append)
        QTest.keyClick(wheel.current,Qt.Key_2)
        self.assertTrue(wheel.isVisible());self.assertEqual(chosen,[])
        QTest.keyClick(wheel.current,Qt.Key_Right);self.assertIs(wheel.current,wheel.buttons[2])
        QTest.keyClick(wheel.current,Qt.Key_3)
        self.assertEqual(chosen,['text-tools']);self.assertFalse(wheel.isVisible())
        self.assertEqual(json.loads(self.settings.value('favorites')),['ports'])
        self.assertFalse(self.settings.contains('activeWheel'))

    def test_radial_can_toggle_escape_and_edit_without_a_notch(self):
        self.settings.setValue('notchRadial',json.dumps(['']*8))
        self.window.Open(['radial']);wheel=self.window.favorites_wheel
        self.assertTrue(wheel.isVisible());self.assertIsNone(wheel.current)
        with patch.object(self.window,'show_notch_settings') as settings:
            QTest.mouseClick(wheel.hub,Qt.LeftButton)
        settings.assert_called_once_with('radial');self.assertFalse(wheel.isVisible())
        self.window.Open(['radial']);self.assertTrue(wheel.isVisible())
        self.window.Open(['radial']);self.assertFalse(wheel.isVisible())
        self.window.Open(['radial']);QTest.keyClick(wheel,Qt.Key_Escape)
        self.assertFalse(wheel.isVisible());self.assertIsNone(self.window.quick_panel)

    def test_radial_child_buttons_do_not_clip_the_antialiased_rims(self):
        from PySide6.QtGui import QImage, QPainter
        from radial_art import RingGeometry, paint_ring
        self.window.Open(['radial']);wheel=self.window.favorites_wheel
        self.app.processEvents()
        wheel.highlight(wheel.buttons[5])
        actual=wheel.grab().toImage();scale=actual.devicePixelRatio()
        surface=QImage(actual.size(),QImage.Format_ARGB32_Premultiplied)
        surface.setDevicePixelRatio(scale);surface.fill(Qt.transparent)
        geometry=RingGeometry(wheel.rect())
        painter=QPainter(surface);paint_ring(painter,geometry,5,len(wheel.buttons));painter.end()
        # Input widgets must not erase or raster-clip the shared artwork. This
        # includes both sides of the hub and the translucent outer edge.
        for radius in (geometry.inner,geometry.radius):
            for degree in range(360):
                angle=math.radians(degree)
                for offset in (-1,0,1):
                    x=round((geometry.center.x()+(radius+offset)*math.cos(angle))*scale)
                    y=round((geometry.center.y()+(radius+offset)*math.sin(angle))*scale)
                    self.assertEqual(actual.pixelColor(x,y),surface.pixelColor(x,y),(radius,degree,offset))
        self.assertEqual(actual.pixelColor(0,0).alpha(),0)

    def test_radial_mouse_targets_follow_the_painted_slots(self):
        from radial_art import RingGeometry
        self.window.Open(['radial']);wheel=self.window.favorites_wheel
        chosen=[];wheel.chosen.disconnect(self.window.open_favorite);wheel.chosen.connect(chosen.append)
        expected=[button.key for button in wheel.buttons]
        geometry=RingGeometry(wheel.rect())
        for index,key in enumerate(expected):
            if index:self.window.Open(['radial'])
            point=geometry.point(index,.71).toPoint()
            button=wheel.childAt(point)
            self.assertIs(button,wheel.buttons[index])
            self.assertEqual([b.key for b in wheel.buttons if b.hitButton(point)],[key])
            self.assertFalse(any(b.hitButton(geometry.center.toPoint()) for b in wheel.buttons))
            QTest.mouseClick(button,Qt.LeftButton,Qt.NoModifier,point)
            if key=='emoji':
                self.assertTrue(wheel.emoji_picker.isVisible());wheel.hide()
            else:self.assertFalse(wheel.isVisible())
        self.assertEqual(chosen,[key for key in expected if key!='emoji'])

    def test_radial_emoji_browses_copies_and_returns_without_opening_utilities(self):
        from actions import stored
        self.window.Open(['radial']);wheel=self.window.favorites_wheel
        emoji=next(button for button in wheel.buttons if button.key=='emoji')
        wheel.highlight(emoji);emoji.setFocus();self.app.processEvents()
        with patch.object(self.window,'run_tool') as external,patch.object(self.window,'Open') as launch:
            wheel.choose(emoji.entry);self.app.processEvents()
            picker=wheel.emoji_picker;page=picker.page
            self.assertTrue(wheel.isVisible());self.assertFalse(self.window.isVisible())
            self.assertFalse(picker.isWindow());self.assertTrue(page.search.hasFocus())
            for index in range(page.category.count()):
                button=page.category.buttons[index]
                self.assertTrue(button.isVisibleTo(wheel))
                QTest.mouseClick(button,Qt.LeftButton);self.app.processEvents()
                if page.category.tabData(index)!='recent':self.assertGreater(page.grid.count(),0)
            page.search.setText('rocket')
            for _ in range(100):
                QTest.qWait(10)
                if not page.delay.isActive():break
            self.assertFalse(page.delay.isActive())
            self.assertGreater(page.grid.count(),0)
            copies=[]
            with patch('notch_pages.copy_text',side_effect=lambda host,text,done:(copies.append(text),done(True))):
                page.grid.setCurrentRow(0);page.grid.setFocus();QTest.keyClick(page.grid,Qt.Key_Return)
            self.assertEqual(copies,['🚀']);self.assertIn('copied',page.caption.text())
            self.assertEqual(stored(self.settings,'notchRecentEmoji',[]),['🚀'])
            self.assertTrue(picker.isVisible())
            page.search.clear();page.category.setCurrentIndex(2);self.app.processEvents()
            self.assertGreater(page.grid.verticalScrollBar().maximum(),0)
            page.grid.scrollToBottom();self.assertGreater(page.grid.verticalScrollBar().value(),0)
            QTest.keyClick(page.grid,Qt.Key_Escape)
            self.assertFalse(picker.isVisible());self.assertTrue(wheel.hub.isVisible())
            self.assertIs(wheel.current,emoji)
            wheel.choose(emoji.entry);picker.back.click()
            self.assertTrue(emoji.isVisible());self.assertFalse(picker.isVisible())
            QTest.keyClick(wheel,Qt.Key_Escape);self.assertFalse(wheel.isVisible())
            external.assert_not_called();launch.assert_not_called()

    def test_radial_emoji_fits_the_existing_surface_and_opens_cleanly_again(self):
        self.window.Open(['radial']);wheel=self.window.favorites_wheel
        items=tuple(button.entry for button in wheel.buttons)
        for size in (320,440):
            wheel.present(items,size);wheel.open_emoji(self.window);self.app.processEvents()
            picker=wheel.emoji_picker
            for widget in [picker.page.search,picker.page.grid,picker.back,picker.close,*picker.page.category.buttons]:
                top=widget.mapTo(wheel,widget.rect().topLeft())
                bottom=widget.mapTo(wheel,widget.rect().bottomRight())
                self.assertGreaterEqual(top.x(),0);self.assertGreaterEqual(top.y(),0)
                self.assertLess(bottom.x(),wheel.width());self.assertLess(bottom.y(),wheel.height())
            wheel.hide();self.window.Open(['radial'])
            self.assertFalse(picker.isVisible());self.assertTrue(wheel.hub.isVisible())

    def test_radial_long_names_stay_within_two_center_lines(self):
        names=['A very long custom name for my favorite screenshot action','UnbrokenName'*5]
        self.settings.setValue('notchRadial',json.dumps([{'action':'screenshot','name':name} for name in names]))
        self.window.Open(['radial']);wheel=self.window.favorites_wheel
        self.app.processEvents()
        for index,name in enumerate(names):
            wheel.highlight(wheel.buttons[index]);self.app.processEvents()
            lines=wheel.label.text().splitlines()
            self.assertLessEqual(len(lines),2)
            for line in lines:
                self.assertLessEqual(wheel.label.fontMetrics().horizontalAdvance(line),wheel.label.width())
            self.assertLessEqual(wheel.label.sizeHint().height(),wheel.label.height())
            self.assertEqual(wheel.hub.accessibleDescription(),name)

    def test_radial_shortcut_fast_dispatch_carries_activation_and_respects_hidden_tool(self):
        with patch.object(self.window,'wheel') as opened:
            self.receiver.OpenTool('radial','activation-token')
            self.app.processEvents()
        opened.assert_called_once_with('radial')
        self.assertNotIn('XDG_ACTIVATION_TOKEN',os.environ)
        self.receiver.OpenTool('radial','')
        self.app.processEvents()
        self.assertTrue(self.window.favorites_wheel.isVisible())
        self.receiver.OpenTool('radial','')
        self.app.processEvents()
        self.assertFalse(self.window.favorites_wheel.isVisible())
        self.favorites(['ports'],['wheel'])
        self.receiver.OpenTool('radial','')
        self.app.processEvents()
        self.assertFalse(self.window.favorites_wheel.isVisible())

    def test_submenus_restore_focus_and_hidden_tools_disappear_at_every_level(self):
        from wheel_profiles import Entry, Profile, save_profile
        self.favorites(["notes"], ["shelf"])
        ident = save_profile(self.settings, "", Profile("Study", (
            Entry("menu", name="Hidden", children=(Entry("tool", "shelf"),)),
            Entry("tool", "ports"),
            Entry("menu", name="Writing", children=(Entry("tool", "shelf"), Entry("tool", "notes"))))))
        self.settings.setValue("activeWheel", ident)
        self.window.Open(["wheel"])
        wheel = self.window.favorites_wheel
        self.assertEqual([b.text() for b in wheel.buttons], [ACTIONS["ports"].name, "Writing"])
        QTest.keyClick(wheel.current, Qt.Key_Right)
        QTest.keyClick(wheel.current, Qt.Key_Return)
        self.assertEqual([b.key for b in wheel.buttons], ["notes"])
        QTest.keyClick(wheel.current, Qt.Key_Escape)
        self.assertTrue(wheel.isVisible())
        self.assertEqual(wheel.current.text(), "Writing")
        QTest.keyClick(wheel.current, Qt.Key_Return)
        QTest.mouseClick(wheel.hub, Qt.LeftButton)
        self.assertEqual(wheel.current.text(), "Writing")
        QTest.keyClick(wheel.current, Qt.Key_Escape)
        self.assertFalse(wheel.isVisible())

    def test_named_shortcuts_switch_in_place_and_keep_the_shared_shortcut_selection(self):
        from wheel_profiles import Entry, Profile, save_profile
        self.favorites(["shelf"])
        work = save_profile(self.settings, "", Profile("Work", (Entry("tool", "ports"),)))
        play = save_profile(self.settings, "", Profile("Play", (Entry("tool", "notes"),)))
        self.settings.setValue("activeWheel", play)
        self.receiver.OpenTool("wheel", "", work)
        self.app.processEvents()
        wheel = self.window.favorites_wheel
        self.assertTrue(wheel.isVisible())
        self.assertEqual(wheel.current.key, "ports")
        self.window.Open(["wheel", "0" * 32])
        self.assertTrue(wheel.isVisible())
        self.assertEqual(wheel.active_id, work)
        self.window.Open(["wheel", play])
        self.assertIs(self.window.favorites_wheel, wheel)
        self.assertTrue(wheel.isVisible())
        self.assertEqual(wheel.current.key, "notes")
        self.window.Open(["wheel", play])
        self.assertFalse(wheel.isVisible())
        self.window.Open(["wheel", work])
        self.window.Open(["wheel"])
        self.assertFalse(wheel.isVisible())
        self.window.Open(["wheel"])
        self.assertEqual(wheel.active_id, play)
        self.assertEqual(self.settings.value("activeWheel"), play)

    def test_hold_requires_motion_and_chooses_a_submenu_only_once(self):
        from wheel_profiles import Entry, Profile, save_profile
        menu = Entry("menu", name="Project", children=(Entry("tool", "shelf"),))
        ident = save_profile(self.settings, "", Profile("Work", (menu, Entry("tool", "notes"))))
        self.settings.setValue("activeWheel", ident)
        mods = Qt.MetaModifier | Qt.AltModifier
        with patch("wheel_shortcuts.activation_modifiers", return_value=[mods]), patch.object(
                QApplication, "queryKeyboardModifiers", return_value=mods):
            self.receiver.OpenTool("wheel", "", "--shortcut")
            self.app.processEvents()
            self.app.processEvents()
            wheel = self.window.favorites_wheel
            self.assertEqual(wheel.required, mods)
            button = wheel.buttons[0]
            wheel.point_at(button, wheel.origin + QPoint(1, 0))
            self.assertIsNone(wheel.pointed)
            wheel.point_at(button, wheel.origin + QPoint(0, -80))
            self.assertIs(wheel.pointed, button)
            QTest.keyRelease(button, Qt.Key_Alt)
            QTest.keyRelease(wheel.current, Qt.Key_Meta)
            self.assertTrue(wheel.isVisible())
            self.assertEqual([b.key for b in wheel.buttons], ["shelf"])
            self.assertIsNone(wheel.pointed)
            self.assertEqual(wheel.required, Qt.NoModifier)

    def test_hold_only_still_supports_bare_shortcuts_and_opening_from_catalog(self):
        self.favorites(["notes", "shelf"])
        self.window.Open(["wheel-settings"])
        editor = self.window.pages["wheel-settings"]
        editor.activation.setCurrentIndex(editor.activation.findData("hold"))
        editor.refresh()
        self.assertEqual(editor.activation.currentData(), "hold")
        self.assertEqual(self.settings.value("wheelActivation"), "hold")
        with patch("wheel_shortcuts.activation_modifiers", return_value=[Qt.NoModifier]) as read:
            self.window.Open(["wheel"])
            self.app.processEvents()
            wheel = self.window.favorites_wheel
            self.assertTrue(wheel.isVisible())
            read.assert_not_called()
            wheel.hide()
            self.window.Open(["wheel", "--shortcut"])
            self.app.processEvents()
            self.assertTrue(wheel.isVisible())
            self.assertEqual(wheel.required, Qt.NoModifier)
            read.assert_called_once_with("")

    def test_editor_persists_profile_targets_order_and_reparenting(self):
        from wheel_profiles import Entry, profiles
        self.favorites(["notes"], ["shelf"])
        self.window.Open(["wheel-settings"])
        editor = self.window.pages["wheel-settings"]
        self.assertFalse(editor.add.isVisible())
        self.assertEqual(editor.root.child(0).data(0, Qt.UserRole).value, "notes")
        with patch.object(editor, "profile_name", return_value="Work"):
            editor.new_profile()
        key = editor.selector.currentData()
        self.assertEqual(self.settings.value("activeWheel"), key)
        menu = Entry("menu", name="Project")
        file = Entry("file", "/tmp/file with spaces", "Plan")
        with patch.object(editor, "choose_entry", side_effect=[menu, file]):
            editor.add_item("menu")
            editor.tree.setCurrentItem(editor.root)
            editor.add_item("file")
        editor.move_in()
        self.assertEqual(profiles(self.settings)[key].items[0].children, (file,))
        editor.move_out()
        editor.move(-1)
        self.assertEqual(profiles(self.settings)[key].items, (file, menu))
        editor.refresh()
        self.assertEqual([editor.root.child(i).text(0) for i in range(2)], ["Plan", "Project"])
        self.window.Open(["wheel"])
        wheel = self.window.favorites_wheel
        self.assertEqual([b.text() for b in wheel.buttons], ["Plan"])
        self.window.switch_wheel("")
        self.assertEqual([b.key for b in wheel.buttons], ["notes"])
        self.assertEqual(editor.selector.currentData(), "")
        self.assertEqual(profiles(self.settings)[key].items, (file, menu))
        wheel.hide()

    def test_full_submenu_rejects_moves_and_cannot_contain_itself(self):
        from wheel_profiles import Entry, Profile, save_profile
        group = Entry("menu", name="Full", children=(Entry("file", "/a"),) * 8)
        key = save_profile(self.settings, "", Profile("Work", (group, Entry("tool", "notes"))))
        self.settings.setValue("activeWheel", key)
        self.window.Open(["wheel-settings"])
        editor = self.window.pages["wheel-settings"]
        first, second = (editor.root.child(i) for i in range(2))
        editor.tree.setCurrentItem(first)
        self.assertFalse(editor.add.isEnabled())
        self.assertFalse(editor.tree.move_item(first, first, 0))
        self.assertFalse(editor.tree.move_item(second, first, 0))
        self.assertEqual(editor.root.childCount(), 2)
        self.assertEqual(first.childCount(), 8)

    def test_missing_target_offers_editor_and_keeps_other_entries(self):
        from wheel_profiles import Entry, Profile, save_profile, web_address
        key = save_profile(self.settings, "", Profile("Work", (Entry("file", "/missing-wheel-test-target", "Plan"),)))
        self.settings.setValue("activeWheel", key)
        self.window.Open(["wheel"])
        wheel = self.window.favorites_wheel
        QTest.keyClick(wheel.current, Qt.Key_Return)
        self.assertTrue(self.window.isVisible())
        self.assertEqual(self.window.stack.currentWidget(), self.window.pages["wheel-settings"])
        self.assertIn("Plan", self.window.status.currentMessage())
        self.assertEqual(web_address("file:///tmp/run"), "")
        self.assertEqual(web_address("https://example.org/a?x=2"), "https://example.org/a?x=2")
