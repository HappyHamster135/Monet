"""Upgrade shortcuts and borderless snap geometry, without a running Plasma session."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LOOK = ROOT / "linux/libexec/monet-look"
SNAP = ROOT / "linux/share/kwin/scripts/monet-snap/contents/ui/main.qml"
OLD_STORES = ("io.github.kolunmi.Bazaar", "org.kde.discover")


@unittest.skipUnless(os.name != "nt" and shutil.which("bash"), "needs Linux bash")
class StoreUpgrade(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.share = self.root / "share"
        self.bin = self.root / "bin"
        for folder in (self.data / "applications", self.share / "applications", self.bin):
            folder.mkdir(parents=True)
        self.entry = self.share / "applications/monet-store.desktop"
        self.entry.write_text("[Desktop Entry]\nType=Application\nName=Store\n"
                              "Exec=/usr/libexec/monet-store %u\nMimeType=x-scheme-handler/appstream;\n")
        self.script = self.root / "monet-look"
        self.script.write_text(LOOK.read_text().replace("@DATADIR@", str(self.share)).replace("@LIBEXECDIR@", str(self.root)))
        helper = self.root / "monet-profile"
        shutil.copyfile(ROOT / "linux/libexec/monet-profile", helper); helper.chmod(0o755)
        for name, body in {
            "kbuildsycoca6": 'printf "%s\\n" "$*" >> "$MONET_QA/cache.log"',
            "busctl": 'printf "%s" "$8" > "$MONET_QA/dock.js"',
        }.items():
            stub = self.bin / name
            stub.write_text("#!/bin/sh\n" + body + "\n")
            stub.chmod(0o755)
        self.env = dict(os.environ, XDG_DATA_HOME=str(self.data),
                        XDG_CONFIG_HOME=str(self.root / "config"), XDG_STATE_HOME=str(self.root / "state"), MONET_QA=str(self.root),
                        PATH=str(self.bin) + os.pathsep + os.environ["PATH"])
        for ident in OLD_STORES:
            (self.data / f"applications/{ident}.desktop").write_text(
                "[Desktop Entry]\nName=Store\nExec=bazaar\nDBusActivatable=true\n"
                "[Desktop Action old]\nExec=bazaar --old\n")

    def repair(self):
        subprocess.run(["bash", str(self.script), "--store"], env=self.env, check=True, timeout=20)

    def test_upgrade_replaces_stale_activation_and_is_idempotent(self):
        # This account already has every old migration stamp; Store repair still runs alone.
        stamps = self.root / "config/monet"
        stamps.mkdir(parents=True)
        for stamp in ("look-0.9.3", "names"):
            (stamps / stamp).touch()
        self.repair()
        for ident in OLD_STORES:
            target = self.data / f"applications/{ident}.desktop"
            text = target.read_text()
            self.assertIn("Exec=/usr/libexec/monet-store %u\n", text)
            self.assertIn("NoDisplay=true\n", text)
            self.assertNotIn("DBusActivatable", text)
            self.assertNotIn("Desktop Action", text)
            self.assertNotIn("MimeType", text)
            # A second sign-in must not rewrite a watched file or rebuild the cache again.
            os.utime(target, (1000000000, 1000000000))
        self.repair()
        self.assertEqual((self.root / "cache.log").read_text(), "--noincremental\n")
        for ident in OLD_STORES:
            self.assertEqual((self.data / f"applications/{ident}.desktop").stat().st_mtime, 1000000000)
        self.assertFalse(list((self.data / "applications").glob("*.monet.*")))
        self.assertEqual((stamps / "look-0.9.3").read_text(), "")

    def test_without_monets_store_existing_shortcuts_stay_usable(self):
        self.entry.unlink()
        before = {p.name: p.read_bytes() for p in (self.data / "applications").iterdir()}
        self.repair()
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.data / "applications").iterdir()})
        self.assertFalse((self.root / "cache.log").exists())
        self.assertFalse((self.root / "dock.js").exists())

    def test_sign_in_repairs_shortcuts_even_after_a_recorded_upgrade(self):
        session = (ROOT / "linux/libexec/monet-session").read_text()
        self.assertIn('if "$LIBEXECDIR/monet-profile" run "$LIBEXECDIR/monet-look" --keep; then', session)
        self.assertIn('fi\n# Always repair old entry points, even when the content receipt already exists.\n"$LIBEXECDIR/monet-look" --store', session)

    def test_customized_store_command_and_dock_target_survive(self):
        target = self.data / f"applications/{OLD_STORES[0]}.desktop"
        custom = "[Desktop Entry]\nX-Monet=true\nName=My Store\nExec=bazaar --custom-option\nIcon=my-store\n"
        target.write_text(custom)
        self.repair()
        self.assertEqual(target.read_text(), custom)
        script = (self.root / "dock.js").read_text()
        self.assertNotIn(OLD_STORES[0] + ".desktop", script)
        self.assertIn(OLD_STORES[1] + ".desktop", script)

    def test_store_repair_keeps_custom_actions_and_menu_visibility(self):
        target = self.data / f"applications/{OLD_STORES[0]}.desktop"
        target.write_text("[Desktop Entry]\nName=My Store\nIcon=my-store\nNoDisplay=false\n"
                          "Exec=bazaar\nActions=old;mine;\nX-KDE-Shortcuts=Meta+B\n"
                          "[Desktop Action old]\nExec=bazaar --old\n"
                          "[Desktop Action mine]\nName=My action\nExec=my-command\n")
        self.repair()
        text = target.read_text()
        for line in ("Name=My Store", "Icon=my-store", "NoDisplay=false", "X-KDE-Shortcuts=Meta+B",
                     "Actions=mine;", "Exec=my-command", "Exec=/usr/libexec/monet-store %u"):
            self.assertIn(line + "\n", text)
        self.assertNotIn("[Desktop Action old]", text)
        self.assertNotIn(OLD_STORES[0] + ".desktop", (self.root / "dock.js").read_text())


@unittest.skipUnless(shutil.which("node"), "needs a JavaScript runtime")
class WindowGeometry(unittest.TestCase):
    def run_js(self, code):
        done = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=15)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_old_dock_ids_and_paths_migrate_without_moving_other_apps(self):
        script = re.search(r"dock_shortcuts\(\).*?<<'JS'.*?\n(.*?)\nJS", LOOK.read_text(), re.S).group(1)
        script = script.replace("STORE", "monet-store.desktop").replace("ALIASES", "org.kde.discover.desktop|io.github.kolunmi.Bazaar.desktop|monet-store.desktop").replace("SETTINGS_ALIAS", "systemsettings.desktop")
        before = ["applications:org.kde.dolphin.desktop", "applications:io.github.kolunmi.Bazaar.desktop",
                  "file:///usr/share/applications/org.kde.discover.desktop", "applications:systemsettings.desktop",
                  "file:///home/j/custom/org.kde.discover.desktop"]
        code = ("let launchers = " + json.dumps(",".join(before)) + "; let writes = 0;"
                "const tasks = { readConfig: () => launchers, writeConfig: (_, list) => {"
                " launchers = list.join(','); writes++; }};"
                "const panels = () => [{ widgets: () => [tasks] }];")
        result = self.run_js(code + script + script + "console.log(JSON.stringify({launchers, writes}));")
        self.assertEqual(result["launchers"].split(","), [before[0], "applications:monet-store.desktop",
                                                        "applications:monet-store.desktop", "applications:monet-settings.desktop", before[4]])
        self.assertEqual(result["writes"], 1)

    def test_snapping_and_shared_edges_have_no_inset(self):
        main = SNAP.read_text()
        functions = "\n".join(re.search(r"\n    (function " + name + r"\(.*?\n    })\n", main, re.S).group(1)
                              for name in ("place", "reshaped"))
        code = """
const Qt = { rect: (x, y, width, height) => ({x, y, width, height}) };
const sizes = {}, together = {}, pendingGeometry = {}, key = w => w.id;
let placing = false, sharing = false, snapping = true;
const Workspace = {stackingOrder: []}, screen = {};
const win = id => ({id, output: screen, minSize: {width: 160, height: 120},
    frameGeometry: Qt.rect(0, 0, 300, 200)});
""" + functions + """
const a = win('a'), b = win('b'), c = win('c');
place(a, Qt.rect(100, 40, 960, 1040), a.frameGeometry);
place(b, Qt.rect(1060, 40, 960, 1040), b.frameGeometry);
const placed = [a.frameGeometry, b.frameGeometry];
Workspace.stackingOrder = [a, b];
const old = a.frameGeometry;
a.frameGeometry = Qt.rect(100, 40, 1100, 1040);
reshaped(a, old);
const horizontal = b.frameGeometry;
const rightBefore = b.frameGeometry;
// The next change is a user dragging the neighbouring window, not an acknowledgement.
b.resize = true;
b.frameGeometry = Qt.rect(1060, 40, 960, 1040);
reshaped(b, rightBefore);
const leftward = a.frameGeometry;
place(a, Qt.rect(100, 40, 1920, 520), a.frameGeometry);
place(c, Qt.rect(100, 560, 1920, 520), c.frameGeometry);
Workspace.stackingOrder = [a, c];
const above = a.frameGeometry;
a.frameGeometry = Qt.rect(100, 40, 1920, 600);
reshaped(a, above);
const vertical = c.frameGeometry, below = c.frameGeometry;
c.resize = true;
c.frameGeometry = Qt.rect(100, 560, 1920, 520);
reshaped(c, below);
console.log(JSON.stringify({placed, horizontal, leftward, vertical, upward: a.frameGeometry, saved: sizes.a}));
"""
        result = self.run_js(code)
        self.assertEqual(result["placed"], [dict(x=100, y=40, width=960, height=1040),
                                           dict(x=1060, y=40, width=960, height=1040)])
        self.assertEqual(result["horizontal"], dict(x=1200, y=40, width=820, height=1040))
        self.assertEqual(result["leftward"], dict(x=100, y=40, width=960, height=1040))
        self.assertEqual(result["vertical"], dict(x=100, y=640, width=1920, height=440))
        self.assertEqual(result["upward"], dict(x=100, y=40, width=1920, height=520))
        self.assertEqual(result["saved"], dict(width=300, height=200))

    def test_shared_edges_follow_delayed_wayland_resizes(self):
        function = re.search(r"\n    (function reshaped\(.*?\n    })\n", SNAP.read_text(), re.S).group(1)
        result = self.run_js("""
const Qt = {rect: (x,y,width,height) => ({x,y,width,height})};
const key = w => w.id, together = {a:true,b:true}, pendingGeometry = {};
let placing = false, sharing = false, snapping = true;
const a = {id:'a', output:1, resize:true, frameGeometry:Qt.rect(0,0,960,1080)};
let actual = Qt.rect(960,0,960,1080), requested = [];
const b = {id:'b', output:1, resize:false, minSize:{width:160,height:120},
 get frameGeometry() {return actual}, set frameGeometry(g) {requested.push(g)}};
const Workspace = {stackingOrder:[a,b]};
""" + function + """
let old = a.frameGeometry;
a.frameGeometry = Qt.rect(0,0,980,1080); reshaped(a, old);
old = a.frameGeometry;
a.frameGeometry = Qt.rect(0,0,1060,1080); reshaped(a, old);
// The neighbour acknowledges the first request after the second pointer step.
old = actual; actual = requested[0]; reshaped(b, old);
const stillWaiting = !!pendingGeometry.b, sourceAfterOldAck = a.frameGeometry;
old = actual; actual = requested[requested.length-1]; reshaped(b, old);
console.log(JSON.stringify({requested,stillWaiting,sourceAfterOldAck,pending:pendingGeometry}));
""")
        self.assertEqual(result["requested"], [dict(x=980, y=0, width=940, height=1080),
                                               dict(x=1060, y=0, width=860, height=1080)])
        self.assertTrue(result["stillWaiting"])
        self.assertEqual(result["sourceAfterOldAck"], dict(x=0, y=0, width=1060, height=1080))
        self.assertEqual(result["pending"], {})
