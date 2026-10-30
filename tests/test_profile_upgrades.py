"""Real KConfig migration policy in isolated homes, including failure and undo."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "linux/libexec/monet-profile"
LINUX = os.name != "nt" and shutil.which("kreadconfig6") and shutil.which("kwriteconfig6")


@unittest.skipUnless(LINUX, "Linux KConfig tools")
class ProfileUpgrades(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "config"; self.data = self.root / "data"; self.state = self.root / "state"
        for p in (self.config, self.data, self.state): p.mkdir()
        self.env = dict(os.environ, XDG_CONFIG_HOME=str(self.config), XDG_DATA_HOME=str(self.data), XDG_STATE_HOME=str(self.state))
        self.env.pop("MONET_PROFILE_RUN", None); self.env.pop("MONET_PROFILE_FORCE", None)
        self.helper = self.root / "monet-profile"; shutil.copyfile(HELPER, self.helper); self.helper.chmod(0o755)
        (self.root / "monet-light").write_text("#!/bin/sh\nexit 0\n"); (self.root / "monet-light").chmod(0o755)

    def call(self, *args, ok=True, env=None):
        result = subprocess.run([str(self.helper), *args], env=env or self.env, text=True, capture_output=True, timeout=60)
        if ok: self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def spec(self, key="upgradeFont"):
        return ["--file", "kdeglobals", "--group", "General", "--key", key]

    def read(self, key="upgradeFont"):
        return subprocess.check_output(["kreadconfig6", "--file", str(self.config / "kdeglobals"), "--group", "General", "--key", key, "--default", "MISSING"], env=self.env, text=True).removesuffix("\n")

    def user(self, value, key="upgradeFont"):
        subprocess.run(["kwriteconfig6", *self.spec(key), value], env=self.env, check=True)

    def record(self): return json.loads((self.state / "monet/profile/state.json").read_text())

    def script(self, contents):
        path = self.root / "upgrade"
        path.write_text('#!/bin/sh\nset -e\n' + contents)
        path.chmod(0o755); return path

    def test_unrecorded_existing_empty_false_and_zero_preferences_are_preserved(self):
        for value in ("My font", "", "false", "0"):
            self.user(value)
            self.call("put", *self.spec(), "Monet")
            self.assertEqual(self.read(), value)

    def test_owned_values_evolve_but_modified_and_removed_values_do_not(self):
        self.call("put", *self.spec(), "Monet1")
        self.call("put", *self.spec(), "Monet2")
        self.assertEqual(self.read(), "Monet2")
        self.user("")
        self.call("put", *self.spec(), "Monet3")
        self.assertEqual(self.read(), "")
        subprocess.run(["kwriteconfig6", *self.spec(), "--delete"], env=self.env, check=True)
        self.call("put", *self.spec(), "Monet4")
        self.assertEqual(self.read(), "MISSING")

    def test_legacy_ledger_import_requires_matching_current_value(self):
        (self.config / "monet").mkdir()
        (self.config / "monet/look-written").write_text(" ".join(self.spec()) + "\tOld Monet\n")
        self.user("Old Monet"); self.call("put", *self.spec(), "New Monet")
        self.assertEqual(self.read(), "New Monet")
        self.user("Mine"); self.call("put", *self.spec(), "Next Monet")
        self.assertEqual(self.read(), "Mine")

    def test_explicit_reset_replaces_choice_but_defaults_only_do_not(self):
        self.user("Mine")
        self.call("put", "--default-only", *self.spec(), "Monet")
        self.assertEqual(self.read(), "Mine")
        self.call("put", *self.spec(), "Monet", env=dict(self.env, MONET_PROFILE_FORCE="1"))
        self.assertEqual(self.read(), "Monet")

    def test_changed_migration_runs_once_failed_runs_retry_and_old_revision_does_not_replay(self):
        first = f'"{self.helper}" put --file kdeglobals --group General --key upgradeFont First\n'
        path = self.script(first)
        self.call("run", str(path)); self.call("run", str(path))
        self.assertEqual(len(self.record()["runs"]), 1)
        self.script(first.replace("First", "Second") + "exit 1\n")
        self.call("run", str(path), ok=False)
        self.assertEqual(len(self.record()["applied"]), 1)
        self.script(first.replace("First", "Second")); self.call("run", str(path))
        self.assertEqual(self.read(), "Second")
        self.script(first); self.call("run", str(path))
        self.assertEqual(self.read(), "Second")

    def test_rollback_restores_owned_changes_and_refuses_later_user_edits(self):
        path = self.script(f'"{self.helper}" put --file kdeglobals --group General --key upgradeFont Monet\n'
                           f'"{self.helper}" put --file kdeglobals --group General --key accent Green\n')
        self.call("run", str(path)); token = next(iter(self.record()["runs"]))
        self.user("My font")
        result = self.call("rollback", token, ok=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.read(), "My font"); self.assertEqual(self.read("accent"), "MISSING")
        self.call("run", str(path)); self.assertEqual(self.read("accent"), "MISSING")

    def test_write_failure_does_not_record_success(self):
        tools = self.root / "bin"; tools.mkdir()
        fail = tools / "kwriteconfig6"; fail.write_text("#!/bin/sh\nexit 1\n"); fail.chmod(0o755)
        path = self.script(f'"{self.helper}" put --file kdeglobals --group General --key upgradeFont Monet\n')
        result = self.call("run", str(path), ok=False, env=dict(self.env, PATH=str(tools) + os.pathsep + os.environ["PATH"]))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.record()["applied"], [])
        self.assertEqual(self.read(), "MISSING")
        self.call("run", str(path)); self.assertEqual(self.read(), "Monet")

    def test_matching_locked_system_default_needs_no_user_write(self):
        system = self.root / "system"; system.mkdir()
        (system / "kdeglobals").write_text("[KDE Control Module Restrictions][$i]\nmonet_fixture[$i]=false\n")
        env = dict(self.env, XDG_CONFIG_DIRS=str(system))
        args = ['--file', 'kdeglobals', '--group', 'KDE Control Module Restrictions', '--key', 'monet_fixture']
        command = f'"{self.helper}" put --file kdeglobals --group "KDE Control Module Restrictions" --key monet_fixture '
        path = self.script(command + 'false\n')
        self.call("run", str(path), env=env)
        record = self.record()
        self.assertEqual(len(record["applied"]), 1)
        self.assertEqual(record["owned"], {})
        self.assertEqual(next(iter(record["runs"].values()))["changes"], {})
        self.assertFalse((self.config / 'kdeglobals').exists())
        self.script(command + 'true\n')
        self.assertNotEqual(self.call("run", str(path), env=env, ok=False).returncode, 0)
        self.assertEqual(len(self.record()["applied"]), 1)
        self.assertEqual(subprocess.check_output(['kreadconfig6', *args], env=env, text=True).strip(), 'false')

    def test_launcher_three_way_merge_preserves_custom_fields_and_removed_shortcuts(self):
        target = self.data / "applications/org.example.App.desktop"
        source = self.root / "app.desktop"
        source.write_text("[Desktop Entry]\nType=Application\nX-Monet=true\nName=App\nIcon=old\nExec=app-v1\nX-KDE-Shortcuts=Meta+J\n")
        self.call("file", str(target), str(source))
        target.write_text(target.read_text().replace("Name=App", "Name=My App").replace("Icon=old", "Icon=my-icon").replace("X-KDE-Shortcuts=Meta+J\n", ""))
        source.write_text(source.read_text().replace("Exec=app-v1", "Exec=app-v2").replace("Icon=old", "Icon=new"))
        self.call("file", str(target), str(source))
        result = target.read_text()
        for line in ("Name=My App", "Icon=my-icon", "Exec=app-v2"): self.assertIn(line, result)
        self.assertNotIn("X-KDE-Shortcuts", result)
        before = target.stat().st_mtime_ns
        self.call("file", str(target), str(source)); self.assertEqual(target.stat().st_mtime_ns, before)
        target.unlink()
        self.call("file", str(target), str(source)); self.assertFalse(target.exists())

    def test_user_launchers_and_symlinks_are_not_replaced(self):
        target = self.data / "custom.desktop"; target.write_text("[Desktop Entry]\nExec=my-tool\nName=Mine\n")
        source = self.root / "app.desktop"; source.write_text("[Desktop Entry]\nX-Monet=true\nExec=app\n")
        self.call("file", str(target), str(source)); self.assertIn("Exec=my-tool", target.read_text())
        linked = self.data / "linked.desktop"; linked.symlink_to(target)
        self.call("file", str(linked), str(source)); self.assertTrue(linked.is_symlink())

    def test_corrupt_record_is_not_overwritten(self):
        folder = self.state / "monet/profile"; folder.mkdir(parents=True)
        (folder / "state.json").write_text("broken")
        self.assertNotEqual(self.call("put", *self.spec(), "Monet", ok=False).returncode, 0)
        self.assertEqual((folder / "state.json").read_text(), "broken")
        self.assertEqual(self.read(), "MISSING")

    def test_private_journal_and_launcher_rollback(self):
        source = self.root / "app.desktop"; source.write_text("[Desktop Entry]\nX-Monet=true\nExec=app\n")
        target = self.data / "applications/test.desktop"
        path = self.script(f'"{self.helper}" file "{target}" "{source}"\n')
        self.call("run", str(path)); token = next(iter(self.record()["runs"]))
        self.assertEqual((self.state / "monet/profile/state.json").stat().st_mode & 0o777, 0o600)
        self.call("rollback", token); self.assertFalse(target.exists())
        self.call("run", str(path)); self.assertFalse(target.exists())

    def test_arguments_get_separate_receipts(self):
        path = self.script(f'"{self.helper}" put --file kdeglobals --group General --key upgradeFont "$1"\n')
        self.call("run", str(path), "First"); self.call("run", str(path), "Second")
        self.assertEqual(self.read(), "Second")
        self.assertEqual(len(self.record()["applied"]), 2)

    def test_interrupted_write_is_journaled_before_it_happens(self):
        # Kill the helper after KConfig has changed the file, before finish() can
        # acknowledge it. The pending record must still be usable for recovery.
        tools = self.root / "bin"; tools.mkdir()
        writer = tools / "kwriteconfig6"
        writer.write_text('#!/bin/sh\n"' + shutil.which("kwriteconfig6") + '" "$@"\nkill -KILL "$PPID"\n')
        writer.chmod(0o755)
        path = self.script(f'"{self.helper}" put --file kdeglobals --group General --key upgradeFont After\n')
        self.call("run", str(path), ok=False, env=dict(self.env, PATH=str(tools) + os.pathsep + self.env["PATH"]))
        token, record = next(iter(self.record()["runs"].items()))
        self.assertEqual(self.read(), "After"); self.assertEqual(record["status"], "failed")
        self.assertTrue(next(iter(record["changes"].values()))["pending"])
        self.call("rollback", token); self.assertEqual(self.read(), "MISSING")

    def test_rollback_leaves_a_replaced_symlink_and_restores_other_changes(self):
        source = self.root / "app.desktop"; source.write_text("[Desktop Entry]\nX-Monet=true\nExec=app\n")
        target = self.data / "applications/test.desktop"
        path = self.script(f'"{self.helper}" put --file kdeglobals --group General --key upgradeFont Monet\n'
                           f'"{self.helper}" file "{target}" "{source}"\n')
        self.call("run", str(path)); token = next(iter(self.record()["runs"]))
        target.unlink(); target.symlink_to(source)
        result = self.call("rollback", token, ok=False)
        self.assertEqual(result.returncode, 1); self.assertTrue(target.is_symlink())
        self.assertEqual(self.read(), "MISSING")

    def test_full_upgrade_keeps_custom_theme_shortcuts_and_monet_preferences(self):
        tools = self.root / "bin"; tools.mkdir()
        for name, body in {
            "busctl": 'exit 0', "systemctl": 'exit 0', "flatpak": 'exit 0',
            "hostnamectl": 'echo laptop', "kbuildsycoca6": 'exit 0', "pkill": 'exit 0',
            "fc-list": "printf '%s\\n' Inter 'Fraunces 72pt SuperSoft'",
            "plasma-apply-lookandfeel": f'echo RESET >> "{self.root}/theme-reset"',
        }.items():
            file = tools / name; file.write_text("#!/bin/sh\n" + body + "\n"); file.chmod(0o755)
        self.env["PATH"] = str(tools) + os.pathsep + self.env["PATH"]
        share = self.root / "share"; (share / "applications").mkdir(parents=True)
        (share / "monet").mkdir()
        (share / "monet/files-free-space-v1").touch()
        (share / "applications/monet-store.desktop").write_text("[Desktop Entry]\nName=Store\nType=Application\nExec=monet-store %u\n")
        system = self.root / "system-apps"; system.mkdir()
        (system / "org.kde.dolphin.desktop").write_text("[Desktop Entry]\nType=Application\nName=Dolphin\nExec=dolphin %u\n")
        local = self.data / "applications"; local.mkdir()
        (local / "org.kde.dolphin.desktop").write_text("[Desktop Entry]\nName=My Files\nExec=dolphin --new-window %u\nIcon=my-folder\nX-KDE-Shortcuts=Ctrl+Alt+F\n")
        config = {
            "kdeglobals": "[General]\nfont=My Font,13\nColorScheme=MyColors\nAccentColor=1,2,3\n[KDE]\nLookAndFeelPackage=org.example.desktop\nwidgetStyle=Fusion\nAnimationDurationFactor=0\n[Icons]\nTheme=MyIcons\n",
            "kcminputrc": "[Mouse]\ncursorTheme=MyCursor\n[Libinput][123][456][My Touchpad]\nNaturalScroll=false\n",
            "dolphinrc": "[General]\nAlwaysShowTabBar=false\nShowFullPath=false\nShowStatusBar=Disabled\n",
            "systemmonitorrc": "[General]\npageOrder=processes.page,custom.page,overview.page\nstartPage=custom.page\nhiddenPages=history.page\n",
            "kwinrc": "[org.kde.kdecoration2]\nlibrary=org.example.decoration\ntheme=MyFrame\nButtonsOnLeft=\nButtonsOnRight=AX\n",
            "kglobalshortcutsrc": "[kwin]\nOverview=Ctrl+Alt+O,Meta+W,Toggle Overview\nGrid View=none,Meta+G,Toggle Grid View\n",
        }
        for name, text in config.items(): (self.config / name).write_text(text)
        (self.config / "monet").mkdir()
        prefs = self.config / "monet/prefs.json"; prefs.write_text('{"glass":"matte","dodge":false,"snap":false}')
        light = self.config / "monet/light"; light.write_text("smoke\n")
        look = self.root / "monet-look"
        look.write_text((ROOT / "linux/libexec/monet-look").read_text().replace("@LIBEXECDIR@", str(self.root)).replace("@DATADIR@", str(share)).replace("/usr/share/applications", str(system)))
        look.chmod(0o755)
        launcher = (local / "org.kde.dolphin.desktop").read_bytes()
        self.call("run", str(look), "--keep")
        self.call("run", str(look), "--keep")
        self.assertFalse((self.root / "theme-reset").exists())
        self.assertEqual((local / "org.kde.dolphin.desktop").read_bytes(), launcher)
        for name, text in config.items():
            # New Monet keys may be added, but every explicit user value is unchanged.
            for line in text.splitlines():
                if "=" in line: self.assertIn(line + "\n", (self.config / name).read_text(), (name, line))
        self.assertEqual(prefs.read_text(), '{"glass":"matte","dodge":false,"snap":false}')
        self.assertEqual(light.read_text(), "smoke\n")
        # New devices get the requested default without overwriting that touchpad.
        natural = subprocess.check_output(["kreadconfig6", "--file", str(self.config / "kcminputrc"),
                                            "--group", "Libinput", "--group", "Defaults", "--key", "NaturalScroll"],
                                           env=self.env, text=True).strip()
        self.assertEqual(natural, "true")
        # Shortcut migration service also leaves custom/disabled bindings intact.
        self.call("run", str(look), "--keys")
        self.assertIn("Overview=Ctrl+Alt+O,", (self.config / "kglobalshortcutsrc").read_text())

        # An earlier Monet-owned compact bar must evolve when the patched
        # Files bundle arrives. The explicitly Disabled bar above was kept.
        (self.config / "dolphinrc").write_text("[General]\n")
        self.call("put", "--file", "dolphinrc", "--group", "General", "--key", "ShowStatusBar", "Small")
        subprocess.run([str(look), "--keep"], env=self.env, check=True, capture_output=True, timeout=30)
        self.assertIn("ShowStatusBar=FullWidth", (self.config / "dolphinrc").read_text())

    def test_before_desktop_job_keeps_menu_and_tray_choices_without_old_stamps(self):
        rc = self.config / "plasma-org.kde.plasma.desktop-appletsrc"
        rc.write_text('[ActionPlugins][0]\nRightButton;NoModifier=\n'
                      '[ActionPlugins][0][RightButton;NoModifier]\nadd widgets=false\nconfigure=true\n'
                      '[Containments][4][Applets][6]\nplugin=org.kde.plasma.systemtray\n'
                      '[Containments][4][Applets][6][General]\nextraItems=org.kde.plasma.brightness,custom\nknownItems=custom\n')
        expected = rc.read_text()
        path = self.root / "monet-fresh"
        path.write_text((ROOT / "linux/libexec/monet-fresh").read_text().replace("@LIBEXECDIR@", str(self.root)))
        path.chmod(0o755)
        env = dict(self.env, XDG_CACHE_HOME=str(self.root / "cache"))
        for _ in range(2):
            subprocess.run([str(path)], env=env, check=True, capture_output=True, timeout=30)
        for line in expected.splitlines():
            if "=" in line: self.assertIn(line + "\n", rc.read_text())

    def test_desktop_menu_defaults_exist_before_first_login_and_account_choices_win(self):
        system = self.root / "system-defaults"
        system.mkdir()
        name = "plasma-org.kde.plasma.desktop-appletsrc"
        (system / name).write_text((ROOT / "linux/share/monet/desktop-menu.conf").read_text())
        env = dict(self.env, XDG_CONFIG_DIRS=str(system))
        args = ["kreadconfig6", "--file", name, "--group", "ActionPlugins", "--group", "0",
                "--group", "RightButton;NoModifier", "--key"]
        for key, expected in [("configure", "false"), ("_wallpaper", "true"), ("add widgets", "true")]:
            self.assertEqual(subprocess.check_output([*args, key], env=env, text=True).strip(), expected)
        (self.config / name).write_text("[ActionPlugins][0][RightButton;NoModifier]\nconfigure=true\n")
        self.assertEqual(subprocess.check_output([*args, "configure"], env=env, text=True).strip(), "true")
