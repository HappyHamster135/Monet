"""Choosing where sound plays and records lands on the device picked, however PipeWire has
numbered it since the list was drawn, and is said done only once it's seen to be."""
import json
from pathlib import Path
from tests.settings_support import settings_source
from tests.settings_support import qml_source
import unittest
from unittest.mock import patch

from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]
PLASMOIDS = ROOT / "linux/share/plasma/plasmoids"


def key(name):
    return name.encode().hex()


class FakePipeWire:
    """Answers wpctl and pactl as a PC's sound server would, and changes as they ask it to."""

    def __init__(self):
        self.sinks = {65: "alsa_output.pci-0000_00_1f.3.analog-stereo", 73: "alsa_output.usb-Sony_WH-1000XM4-00.analog-stereo",
                      85: "alsa_output.pci-0000_01_00.1.hdmi-stereo"}
        self.names = {"alsa_output.pci-0000_00_1f.3.analog-stereo": "Speakers",
                      "alsa_output.usb-Sony_WH-1000XM4-00.analog-stereo": "WH-1000XM4",
                      "alsa_output.pci-0000_01_00.1.hdmi-stereo": "HDMI / DisplayPort",
                      "alsa_input.usb-Focusrite_Scarlett_2i2_USB-00.HiFi__Mic1__source": "",
                      "alsa_input.usb-Focusrite_Scarlett_2i2_USB-00.HiFi__Mic2__source": "",
                      "alsa_input.pci-0000_00_1f.3.analog-stereo": "Built-in Microphone"}
        self.sources = {57: "alsa_input.pci-0000_00_1f.3.analog-stereo",
                        74: "alsa_input.usb-Focusrite_Scarlett_2i2_USB-00.HiFi__Mic1__source",
                        76: "alsa_input.usb-Focusrite_Scarlett_2i2_USB-00.HiFi__Mic2__source"}
        self.sink = self.sinks[65]
        self.source = self.sources[57]
        self.muted = set()
        self.obeys = True  # WirePlumber makes a change it's asked for
        self.changes = []

    def renumber(self, sinks=None, sources=None):
        """WirePlumber started again, or a device came or went: the same devices, other numbers."""
        self.sinks = sinks if sinks is not None else self.sinks
        self.sources = sources if sources is not None else self.sources

    def node(self, ident):
        return self.sinks.get(ident) or self.sources.get(ident)

    def status(self):
        def row(ident, name, default, kind):
            mark = "*" if name == default else " "
            listed = self.names[name] or name  # wpctl calls a split input by its node.name
            return f" │  {mark}   {ident}. {listed} [{kind}]" if kind else f" │  {mark}   {ident}. {listed} [vol: 0.50]"
        lines = ["Audio", " ├─ Sinks:"]
        lines += [row(i, n, self.sink, "") for i, n in sorted(self.sinks.items())]
        lines += [" │", " ├─ Sources:"]
        lines += [row(i, n, self.source, "") for i, n in sorted(self.sources.items()) if "__" not in n]
        lines += [" │", " ├─ Filters:"]
        lines += [row(i, n, self.source, "Audio/Source") for i, n in sorted(self.sources.items()) if "__" in n]
        lines += [" │", " └─ Streams:", ""]
        return "\n".join(lines)

    def pulse(self, nodes, kind):
        found = []
        for ident, name in nodes.items():
            props = {"object.id": str(ident), "node.name": name, "media.class": kind}
            if "__Mic" in name:
                number = int(name.split("__Mic")[1][0])
                props.update({"api.alsa.split.position": f"[AUX{number - 1}]", "api.alsa.split.name": "alsa_input.hw_USB_0"})
            found.append({"index": 4000 + ident, "name": name, "description": self.names[name], "properties": props,
                          "active_port": None, "ports": []})
        return json.dumps(found)

    def run(self, *args, timeout=10):
        if args == ("wpctl", "status"):
            return self.status()
        if args[:3] == ("pactl", "--format=json", "list"):
            return {"sinks": lambda: self.pulse(self.sinks, "Audio/Sink"),
                    "sources": lambda: self.pulse(self.sources, "Audio/Source")}.get(args[3], lambda: "[]")()
        if args[:2] == ("wpctl", "inspect"):
            name = self.node(int(args[2]))
            return name and f'id {args[2]}, type PipeWire:Interface:Node\n  * node.name = "{name}"\n'
        if args[:2] == ("wpctl", "get-volume"):
            name = self.node(int(args[2]))
            return name and "Volume: 0.50" + (" [MUTED]" if name in self.muted else "") + "\n"
        if args[:2] in (("wpctl", "set-default"), ("wpctl", "set-mute")):
            self.changes.append(args)
            name = self.node(int(args[2]))
            if name is None:
                return None
            if self.obeys and args[1] == "set-default":
                if name in self.sinks.values():
                    self.sink = name
                else:
                    self.source = name
            elif self.obeys:
                (self.muted.add if args[3] == "1" else self.muted.discard)(name)
            return ""
        return None


class SoundChoices(unittest.TestCase):
    def setUp(self):
        self.q = quick_helper()
        self.pw = FakePipeWire()
        self.said = []
        for name, value in (("run", self.pw.run), ("emit", self.said.append)):
            patcher = patch.object(self.q, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        waiting = patch.object(self.q.time, "sleep")
        self.wait = waiting.start()
        self.addCleanup(waiting.stop)

    def ask(self, *words):
        code = self.q.main(list(words))
        return self.said.pop() if self.said else code

    def test_lists_say_each_device_by_its_stable_name(self):
        outputs = self.ask("outputs")
        self.assertEqual([(o["id"], o["key"]) for o in outputs], [(i, key(n)) for i, n in sorted(self.pw.sinks.items())])
        mics = self.ask("microphones")
        self.assertEqual({m["name"]: m["key"] for m in mics}, {
            "Built-in Microphone": key(self.pw.sources[57]),
            "Focusrite Scarlett 2i2 USB · Input 1": key(self.pw.sources[74]),
            "Focusrite Scarlett 2i2 USB · Input 2": key(self.pw.sources[76])})
        sound = self.ask("sound")
        self.assertEqual(sound["microphone"]["key"], key(self.pw.sources[57]))
        # PipeWire's stand-in for no speakers is never a choice, so it has no key to choose it by.
        with patch.object(self.q, "pulse_nodes", return_value={}):
            self.pw.sinks = {53: "auto_null"}; self.pw.names["auto_null"] = "Dummy Output"; self.pw.sink = "auto_null"
            self.assertEqual(self.ask("outputs"), [{"id": 53, "name": "Dummy Output", "default": True, "none": True}])

    def test_a_renumbered_output_is_found_by_its_name(self):
        headphones = next(o for o in self.ask("outputs") if o["name"] == "WH-1000XM4")
        # Plugged in elsewhere, WirePlumber again: the headphones are 91 now, and 73 is the screen.
        self.pw.renumber(sinks={65: self.pw.sinks[65], 73: self.pw.sinks[85], 91: self.pw.sinks[73]})
        result = self.ask("output", str(headphones["id"]), headphones["key"])
        self.assertTrue(result["ok"])
        self.assertEqual(self.pw.changes, [("wpctl", "set-default", "91")])
        self.assertEqual(self.pw.sink, "alsa_output.usb-Sony_WH-1000XM4-00.analog-stereo")
        self.assertEqual([o["name"] for o in result["outputs"] if o["default"]], ["WH-1000XM4"])
        self.assertNotIn("problem", result)

    def test_an_output_that_has_gone_is_not_replaced_by_whatever_took_its_number(self):
        headphones = next(o for o in self.ask("outputs") if o["name"] == "WH-1000XM4")
        self.pw.renumber(sinks={65: self.pw.sinks[65], 73: self.pw.sinks[85]})  # unplugged; 73 is the screen's
        result = self.ask("output", "73", headphones["key"])
        self.assertEqual((result["ok"], result["problem"]), (False, "gone"))
        self.assertEqual(self.pw.changes, [])
        self.assertEqual(self.pw.sink, self.pw.sinks[65])

    def test_a_default_that_does_not_change_is_reported_after_a_short_wait(self):
        headphones = next(o for o in self.ask("outputs") if o["name"] == "WH-1000XM4")
        self.pw.obeys = False
        result = self.ask("output", "73", headphones["key"])
        self.assertEqual((result["ok"], result["problem"]), (False, "unchanged"))
        self.assertEqual(self.pw.changes, [("wpctl", "set-default", "73")])  # asked once, never again
        self.assertEqual([o["name"] for o in result["outputs"] if o["default"]], ["Speakers"])
        waited = [call.args[0] for call in self.wait.call_args_list]
        self.assertTrue(waited)
        self.assertLessEqual(sum(waited), 2)

    def test_a_renumbered_microphone_input_is_found_by_its_name(self):
        second = next(m for m in self.ask("microphones") if m["name"].endswith("Input 2"))
        self.pw.renumber(sources={57: self.pw.sources[57], 76: self.pw.sources[74], 80: self.pw.sources[76]})
        result = self.ask("input", str(second["id"]), second["key"])
        self.assertTrue(result["ok"])
        self.assertEqual(self.pw.changes, [("wpctl", "set-default", "80")])
        self.assertEqual(result["sound"]["microphone"]["name"], "Focusrite Scarlett 2i2 USB · Input 2")
        # Unplugged, then asked again (Try again): said so, and nothing else is chosen.
        self.pw.renumber(sources={57: self.pw.sources[57]})
        self.pw.changes.clear()
        result = self.ask("input", "80", second["key"])
        self.assertEqual((result["ok"], result["problem"]), (False, "gone"))
        self.assertEqual(self.pw.changes, [])

    def test_a_microphone_that_does_not_switch_is_reported(self):
        first = next(m for m in self.ask("microphones") if m["name"].endswith("Input 1"))
        self.pw.obeys = False
        result = self.ask("input", str(first["id"]), first["key"])
        self.assertEqual((result["ok"], result["problem"]), (False, "unchanged"))
        self.assertEqual(result["sound"]["microphone"]["name"], "Built-in Microphone")

    def test_mute_is_verified_on_the_microphone_shown_even_renumbered(self):
        shown = self.ask("sound")["microphone"]
        self.pw.renumber(sources={63: self.pw.sources[57], 74: self.pw.sources[74], 76: self.pw.sources[76]})
        result = self.ask("mic-mute", str(shown["id"]), "on", shown["key"])
        self.assertTrue(result["ok"])
        self.assertTrue(result["sound"]["microphone"]["muted"])
        self.assertEqual(self.pw.changes, [("wpctl", "set-mute", "63", "1")])
        # Not muted after all: not said to be.
        self.pw.obeys = False
        self.pw.changes.clear()
        result = self.ask("mic-mute", "63", "off", shown["key"])
        self.assertEqual((result["ok"], result["problem"]), (False, "unchanged"))
        self.assertTrue(result["sound"]["microphone"]["muted"])
        # Another microphone in use since it was shown: it's not muted in its place.
        self.pw.source = self.pw.sources[74]
        self.pw.changes.clear()
        result = self.ask("mic-mute", "63", "on", shown["key"])
        self.assertEqual((result["ok"], result["problem"]), (False, "gone"))
        self.assertEqual(self.pw.changes, [])

    def test_the_older_commands_still_choose_by_number(self):
        self.assertTrue(self.ask("output", "73")["ok"])
        self.assertEqual(self.pw.sink, self.pw.sinks[73])
        self.assertTrue(self.ask("input", "76")["ok"])
        self.assertEqual(self.pw.source, self.pw.sources[76])
        self.assertTrue(self.ask("mic-mute", "76", "on")["ok"])
        self.assertIn(self.pw.sources[76], self.pw.muted)
        self.assertEqual(self.pw.changes, [("wpctl", "set-default", "73"), ("wpctl", "set-default", "76"),
                                           ("wpctl", "set-mute", "76", "1")])

    def test_a_key_must_be_hex_from_the_list(self):
        for words in (("output", "73", "zz"), ("output", "73", "ABCD"), ("output", "73", "abc"),
                      ("output", "73", key("x"), "more"), ("mic-mute", "57", "on", "0g")):
            with self.subTest(words=words), patch("sys.stderr"):
                self.assertEqual(self.ask(*words), 1)
        # Any other words after "input" only read the mouse and keyboard page, as before.
        with patch.object(self.q, "input_devices", return_value={}):
            self.assertNotIn("ok", self.ask("input", "57", "; reboot"))
        self.assertEqual(self.pw.changes, [])


class SoundChoicesInThePanels(unittest.TestCase):
    """Quick Settings, Sound and Settings send the device's name along, wait for the helper's
    word, show a failure with Try again, and never send a second change over the first."""
    QUICK = PLASMOIDS / "org.monet.quick/contents/ui/main.qml"
    SOUND = PLASMOIDS / "org.monet.sound/contents/ui/main.qml"
    SETTINGS = ROOT / "linux/share/monet/settings-app/MonetSettings.qml"

    def test_only_hex_keys_go_on_a_command_line(self):
        for path in (self.QUICK, self.SOUND, self.SETTINGS):
            qml = qml_source(path)
            with self.subTest(path.parent.name):
                self.assertIn('return /^(?:[0-9a-f]{2})+$/.test(device.key || "") ? " " + device.key : ""', qml)
                self.assertIn("return !!a && !!b && (a.key && b.key ? a.key === b.key : a.id === b.id)", qml)
                self.assertIn('"%1 isn\'t connected now. Connect it and try again."', qml)

    def test_quick_settings_waits_for_the_switch_and_offers_try_again(self):
        qml = self.QUICK.read_text(encoding="utf-8")
        for line in ('if (!output || !Number.isInteger(output.id) || outputRequest) {',
                     'outputRequest = requestSource("output " + output.id + deviceKey(output))',
                     'if (source !== root.outputRequest) return',
                     'root.outputError = result.ok === true && data["exit code"] === 0 ? "" : root.outputFailure(result.problem)',
                     'if (!outputsBusy && !outputRequest) {',
                     'readonly property bool moving: root.outputRequest !== "" && root.sameOutput(modelData, root.outputWanted)',
                     'onClicked: root.playThrough(root.outputWanted)'):
            self.assertIn(line, qml)
        # No longer drawn as switched before it has.
        self.assertNotIn("default: o.id === output.id", qml)

    def test_sound_waits_for_each_change_and_offers_try_again(self):
        qml = self.SOUND.read_text(encoding="utf-8")
        for line in ('readonly property bool outputBusy: outputRequest !== ""',
                     'readonly property bool microphoneBusy: microphoneRequest !== ""',
                     'outputRequest = requestSource("output " + output.id + deviceKey(output))',
                     'microphoneRequest = requestSource((asked.mute ? "mic-mute " + device.id + " " + asked.mute : "input " + device.id)',
                     'if (source !== root.outputRequest) return', 'if (source !== root.microphoneRequest) return',
                     'if (!device || !Number.isInteger(device.id) || microphoneBusy || outputBusy) return',
                     'if (root.outputBusy || root.microphoneBusy) return',
                     'onClicked: root.playThrough(root.outputWanted)', 'onClicked: root.askMicrophone(root.microphoneAsked)'):
            self.assertIn(line, qml)

    def test_settings_waits_for_each_change_and_offers_try_again(self):
        qml = settings_source()
        for line in ('ask("output " + output.id + deviceKey(output), (out, code) => {',
                     'ask("input " + input.id + deviceKey(input), (out, code) => {',
                     'onClicked: sheet.pickOutput(sheet.outputWanted)', 'onClicked: sheet.pickMicrophone(sheet.microphoneWanted)',
                     'objectName: "outputProblem"', 'objectName: "microphoneProblem"'):
            self.assertIn(line, qml)


if __name__ == "__main__":
    unittest.main()
