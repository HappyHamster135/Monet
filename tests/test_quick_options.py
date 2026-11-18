"""Quick Settings choices use fake services and never change the host's radios."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "linux/share/plasma/plasmoids/org.monet.quick/contents/ui"


class QuickActions(unittest.TestCase):
    def setUp(self): self.q = quick_helper()

    def test_invalid_choices_never_write_or_launch(self):
        for args in ([], ["wifi", "maybe"], ["night", "yes"], ["night-strength", "101"],
                     ["night-strength", "-1"], ["wifi-join", "ff"], ["wifi-join", "00"],
                     ["wifi-join", "41" * 33], ["bluetooth-device", "connect", "AA;rm -rf"], ["bluetooth-device", "forget", "AA:BB:CC:DD:EE:FF"]):
            with self.subTest(args=args), patch.object(self.q, "run") as run, patch.object(self.q, "kwrite") as write:
                self.assertFalse(self.q.quick_options(args)["ok"])
                run.assert_not_called(); write.assert_not_called()

    def test_wifi_names_and_passwords_are_literal_arguments(self):
        name, secret = "Café ;$(touch x)", "don't $expand this"
        with patch.object(self.q, "run", return_value="connected") as run, patch.object(self.q, "wifi_state", return_value=True):
            result = self.q.quick_options(["wifi-join", name.encode().hex(), secret.encode().hex()])
        self.assertTrue(result["ok"])
        self.assertEqual(run.call_args.args, ("nmcli", "--wait", "45", "device", "wifi", "connect", name, "password", secret))

    def test_off_or_missing_wifi_does_not_scan_or_show_a_connection_error(self):
        for state in (False, None):
            with self.subTest(state=state), patch.object(self.q, "wifi_state", return_value=state), patch.object(self.q, "run") as run:
                self.assertEqual(self.q.quick_options(["wifi-list"]), {"ok": True, "networks": [], "enabled": state})
                run.assert_not_called()

    def test_wifi_failure_is_not_success_and_switch_is_verified(self):
        with patch.object(self.q, "run", return_value=None), patch.object(self.q, "wifi_state", return_value=True):
            self.assertFalse(self.q.quick_options(["wifi-join", "486f6d65"])["ok"])
            self.assertFalse(self.q.quick_options(["wifi", "off"])["ok"])
        with patch.object(self.q, "run", return_value=""), patch.object(self.q, "wifi_state", return_value=True):
            self.assertFalse(self.q.quick_options(["wifi", "off"])["ok"])

    def test_disconnect_uses_an_active_wifi_uuid(self):
        ident = "12345678-1234-1234-1234-123456789012"
        with patch.object(self.q, "run", side_effect=[ident + ":802-11-wireless\n", ""]) as run, patch.object(self.q, "wifi_state", return_value=True):
            self.assertTrue(self.q.quick_options(["wifi", "disconnect"])["ok"])
            self.assertEqual(run.call_args.args, ("nmcli", "connection", "down", "uuid", ident))

    def test_bluez_snapshot_uses_one_read_and_filters_unpaired_devices(self):
        def prop(**values): return {key: {"data": value} for key, value in values.items()}
        objects = {"/adapter": {"org.bluez.Adapter1": prop(Powered=True)},
                   "/mouse": {"org.bluez.Device1": prop(Address="AA:BB:CC:DD:EE:FF", Alias="Mouse", Paired=True, Connected=True)},
                   "/near": {"org.bluez.Device1": prop(Address="11:22:33:44:55:66", Alias="Nearby", Paired=False, Connected=False)}}
        with patch.object(self.q, "busjson", return_value=[objects]) as read, patch.object(self.q, "run") as run:
            state = self.q.quick_options(["bluetooth-list"])
        self.assertTrue(state["ok"]); self.assertTrue(state["enabled"])
        self.assertEqual([d["name"] for d in state["devices"]], ["Mouse"])
        read.assert_called_once(); run.assert_not_called()

    def test_bluetooth_connection_needs_verified_device_state(self):
        with patch.object(self.q, "run", return_value=""), patch.object(self.q, "quick_bluetooth_state", return_value={"devices": [
                {"address": "AA:BB:CC:DD:EE:FF", "connected": False}]}):
            self.assertFalse(self.q.quick_options(["bluetooth-device", "connect", "AA:BB:CC:DD:EE:FF"])["ok"])

    def test_pairing_uses_native_wizard_without_settings(self):
        with patch.object(self.q.shutil, "which", return_value="/usr/bin/bluedevil-wizard"), \
                patch.object(self.q, "bluetooth_state", return_value=True), patch.object(self.q.subprocess, "Popen") as launch:
            self.assertTrue(self.q.quick_options(["bluetooth-pair"])["ok"])
        self.assertEqual(launch.call_args.args[0], ["/usr/bin/bluedevil-wizard"])

    def test_night_strength_is_persistent_and_write_failure_is_visible(self):
        with patch.object(self.q, "kwrite", return_value=True) as write, patch.object(self.q, "busctl", return_value=""), \
                patch.object(self.q, "quick_night_state", return_value={"enabled": True, "strength": 60}):
            self.assertTrue(self.q.quick_options(["night-strength", "60"])["ok"])
            write.assert_called_once_with("kwinrc", "NightColor", "NightTemperature", "3200")
        with patch.object(self.q, "kwrite", return_value=False), patch.object(self.q, "quick_night_state", return_value={"enabled": False,"strength":36}):
            self.assertFalse(self.q.quick_options(["night", "on"])["ok"])


try:
    from PySide6.QtCore import QObject, QPointF, QUrl, Qt, Slot
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlEngine, QQmlComponent, QQmlExpression, QJSValue
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    QT = True
except ImportError: QT = False


if QT:
    class Words(QObject):
        @Slot(str, result=str)
        @Slot(str, int, result=str)
        def i18n(self, text, number=None): return text.replace("%1", str(number)) if number is not None else text


@unittest.skipUnless(QT, "requires native Qt/Plasma runtime")
class QuickPanels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        root = Path(self.folder.name); (root / "ui").mkdir()
        shutil.copyfile(UI / "QuickOptions.qml", root / "ui/QuickOptions.qml")
        source = '''import QtQuick
import "ui" as Monet
Window {
    id: scene; width: 420; height: 500; visible: true
    property var commands: []; property var advanced: []; property var pending: ({})
    property string hold: ""; property int dismissed: 0
    property var powerState: ({mode:"automatic",activeMode:"balanced",modes:["automatic","power-saver","performance"],hasBattery:true,batterySaverAuto:true,batterySaverThreshold:20,batteryCriticalLevel:5})
    function answer(command, result, code) { const callback=pending[command]; delete pending[command]; callback(JSON.stringify(result), code) }
    QtObject {
        id: controller
        property var info: ({wifi:true, bluetooth:true, night:false, quiet:false, quietIndefinite:false, quietUntil:0})
        function refresh() {}
        function quietCaption() { return info.quiet ? "On" : "Off" }
        function openSettings(page) { scene.advanced=scene.advanced.concat([page]) }
        function askOptions(command, callback) {
            scene.commands=scene.commands.concat([command]);
            if (command===scene.hold) { scene.pending[command]=callback; return }
            let result={ok:true};
            if(command==="power") result=scene.powerState;
            if(command.indexOf("power-mode ")===0) {
                scene.powerState=Object.assign({},scene.powerState,{mode:command.split(" ").pop()}); result={ok:true,state:scene.powerState};
            }
            if(command.indexOf("battery-saver ")===0) {
                let next=Object.assign({},scene.powerState);
                if(command.indexOf("threshold ")>=0) next.batterySaverThreshold=Number(command.split(" ").pop());
                else next.batterySaverAuto=command.endsWith("automatic");
                scene.powerState=next; result={ok:true,state:next};
            }
            if(command.indexOf("wifi-list")>=0 || command.indexOf("wifi-scan")>=0) result={ok:true,enabled:true,networks:[
                {name:"Home",secure:true,known:true,active:false,signal:90},
                {name:"Café ;$(touch x)",secure:true,known:false,active:false,signal:70}]};
            if(command==="quick-options bluetooth-list") result={ok:true,enabled:true,devices:[{name:"Headphones",address:"AA:BB:CC:DD:EE:FF",connected:false}]};
            if(command==="quick-options night") result={ok:true,enabled:false,strength:36};
            if(command.indexOf("night-strength ")>=0) result={ok:true,enabled:true,strength:Number(command.split(" ").pop())};
            if(command.indexOf("quiet ")===0) result={ok:true,state:{quiet:true,quietIndefinite:false,quietUntil:1800000000}};
            callback(JSON.stringify(result),0);
        }
    }
    Monet.QuickOptions { id: options; objectName: "options"; anchors.fill: parent; anchors.margins:12; bridge:controller; page:"wifi"; onDismissed:scene.dismissed+=1 }
}'''
        self.engine = QQmlEngine(); self.words = Words(); self.errors = []
        self.engine.rootContext().setContextObject(self.words)
        self.engine.warnings.connect(lambda values: self.errors.extend(e.toString() for e in values))
        fixture = root / "fixture.qml"; fixture.write_text(source)
        self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(fixture)), QQmlComponent.Asynchronous)
        for _ in range(250):
            if not self.component.isLoading(): break
            QTest.qWait(20)
        self.assertTrue(self.component.isReady(), [e.toString() for e in self.component.errors()])
        self.window = self.component.create(); self.assertIsNotNone(self.window); QTest.qWait(60)
        self.pane = self.item("options")

    def tearDown(self):
        if hasattr(self, "window"): self.window.close()
        if hasattr(self, "window"): self.window.deleteLater()
        self.component.deleteLater(); self.engine.deleteLater(); QTest.qWait(20)
        self.assertEqual(self.errors, [])

    def js(self, text):
        expression = QQmlExpression(self.engine.contextForObject(self.window), self.window, text)
        result, _ = expression.evaluate(); self.assertFalse(expression.hasError(), expression.error().toString())
        return result.toVariant() if isinstance(result, QJSValue) else result

    def item(self, name):
        queue = [self.window.contentItem()]
        while queue:
            item = queue.pop()
            if item.objectName() == name: return item
            queue.extend(item.childItems())
        self.fail("Missing " + name)

    def click(self, name):
        item = self.item(name)
        point = item.mapToScene(QPointF(item.width()/2, item.height()/2)).toPoint()
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point); QTest.qWait(30)

    def page(self, value): self.pane.setProperty("page", value); QTest.qWait(40)

    def test_saved_wifi_joins_without_opening_settings(self):
        self.click("quickNetwork-Home")
        self.assertIn("quick-options wifi-join 486f6d65", self.js("commands"))
        self.assertEqual(self.js("advanced"), [])

    def test_saved_network_with_an_outdated_password_can_be_retried_inline(self):
        self.js('hold="quick-options wifi-join 486f6d65"')
        self.click("quickNetwork-Home")
        self.js('answer("quick-options wifi-join 486f6d65", {ok:false,enabled:true},1)')
        self.assertTrue(self.item("quickWifiPassword").isVisible())
        self.item("quickWifiPassword").setProperty("text", "new password")
        self.click("quickWifiJoin")
        self.assertIn("quick-options wifi-join 486f6d65 " + b"new password".hex(), self.js("commands"))
        self.assertEqual(self.js("advanced"), [])

    def test_password_form_encodes_unicode_clears_secret_and_goes_back(self):
        self.click("quickNetwork-Café ;$(touch x)")
        self.item("quickWifiPassword").setProperty("text", "secret '$()"); self.click("quickWifiJoin")
        command = "quick-options wifi-join " + "Café ;$(touch x)".encode().hex() + " " + "secret '$()".encode().hex()
        self.assertIn(command, self.js("commands")); self.assertEqual(self.item("quickWifiPassword").property("text"), "")
        self.assertEqual(self.js("advanced"), [])

    def test_bluetooth_connect_and_pair_are_available_in_the_panel(self):
        self.page("bluetooth"); self.click("quickBluetooth-AA:BB:CC:DD:EE:FF"); self.click("quickBluetoothPair")
        self.assertIn("quick-options bluetooth-device connect AA:BB:CC:DD:EE:FF", self.js("commands"))
        self.assertIn("quick-options bluetooth-pair", self.js("commands")); self.assertEqual(self.js("advanced"), [])

    def test_bluetooth_events_load_without_a_system_bus_or_periodic_poll(self):
        component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(UI / "BluetoothEvents.qml")), QQmlComponent.Asynchronous)
        for _ in range(250):
            if not component.isLoading(): break
            QTest.qWait(20)
        self.assertTrue(component.isReady(), [e.toString() for e in component.errors()])
        events = component.create(); self.assertIsNotNone(events)
        QTest.qWait(30); events.deleteLater(); component.deleteLater(); QTest.qWait(20)

    def test_power_mode_and_automatic_saver_stay_in_quick_settings(self):
        self.page("power")
        self.click("quickPower-power-saver")
        self.assertIn("power-mode power-saver", self.js("commands"))
        self.click("quickPower-automatic")
        self.assertIn("power-mode automatic", self.js("commands"))
        self.click("quickAutoBatterySaver")
        self.assertIn("battery-saver off", self.js("commands"))
        self.assertFalse(self.js("options.power.batterySaverAuto"))
        self.assertEqual(self.js("advanced"), [])

    def test_saver_threshold_can_be_changed_with_the_keyboard_and_custom_values_survive(self):
        self.page("power")
        choice = self.item("quickSaverThreshold"); choice.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Down); QTest.qWait(40)
        self.assertIn("battery-saver threshold 30", self.js("commands"))
        self.assertEqual(self.js("options.power.batterySaverThreshold"), 30)
        self.js('options.updateState({mode:"automatic",modes:["automatic","power-saver"],hasBattery:true,batterySaverAuto:true,batterySaverThreshold:15})')
        QTest.qWait(30)
        self.assertEqual(choice.property("currentValue"), 15)

    def test_quiet_durations_do_not_open_settings(self):
        self.page("quiet")
        for mode in ("hour", "four-hours", "tomorrow", "on", "off"):
            self.click("quickQuiet-" + mode)
            self.assertIn("quiet " + mode, self.js("commands"))
        self.assertEqual(self.js("advanced"), [])

    def test_back_clears_password_without_leaving_the_network_list(self):
        self.click("quickNetwork-Café ;$(touch x)")
        self.item("quickWifiPassword").setProperty("text", "private")
        self.click("quickOptionsBack")
        self.assertEqual(self.item("quickWifiPassword").property("text"), "")
        self.assertIsNone(self.pane.property("selectedNetwork"))
        self.assertEqual(self.window.property("dismissed"), 0)

    def test_new_strength_survives_an_older_inflight_write(self):
        self.page("night")
        self.js('hold="quick-options night-strength 60"; options.draftStrength=60; options.strengthDirty=true')
        self.item("quickNightStrength").moved.emit(); QTest.qWait(240)
        self.assertTrue(self.pane.property("busy"))
        self.js('options.draftStrength=80; options.strengthDirty=true')
        self.item("quickNightStrength").moved.emit(); QTest.qWait(240)
        self.js('answer("quick-options night-strength 60", {ok:true,enabled:true,strength:60},0)')
        QTest.qWait(260)
        self.assertIn("quick-options night-strength 80", self.js("commands"))
        self.assertEqual(self.pane.property("draftStrength"), 80)
        self.assertEqual(self.js("advanced"), [])

    def test_old_replies_cannot_replace_another_page(self):
        self.js('hold="quick-options wifi-scan"'); self.click("quickOptionsRefresh")
        self.page("bluetooth")
        self.js('answer("quick-options wifi-scan", {ok:true,enabled:false,networks:[]},0)')
        self.assertEqual(self.pane.property("page"), "bluetooth"); self.assertEqual(self.pane.property("error"), "")
        self.assertTrue(self.js("controller.info.wifi"))

    def test_failures_release_controls_and_show_an_error(self):
        self.js('hold="quick-options wifi-scan"'); self.click("quickOptionsRefresh")
        self.assertTrue(self.pane.property("busy"))
        self.js('answer("quick-options wifi-scan", {ok:false},1)')
        self.assertFalse(self.pane.property("busy")); self.assertNotEqual(self.pane.property("error"), "")

    def test_more_settings_is_explicit_and_back_stays_in_the_popup(self):
        self.page("night"); self.click("quickOptionsAdvanced")
        self.assertEqual(self.js("advanced"), ["display"])
        self.click("quickOptionsBack"); self.assertEqual(self.window.property("dismissed"), 1)


class NativeQuickApplet(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("MONET_QUICK_FIXTURE"), "requires the compiled Quick Settings applet fixture")
    def test_actual_chevrons_open_inline_panels_without_toggling(self):
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run([sys.executable, str(ROOT / 'tests/fixtures/quick-options-native.py'), folder],
                                    capture_output=True, text=True, timeout=50)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads((Path(folder) / 'result.json').read_text())['ok'])
