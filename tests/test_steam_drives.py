"""Steam's libraries on the PC's other drives, found again when a drive is mounted somewhere new
(monet-quick steam-drives), and what runs it: sign-in and Steam's own autostart.

    python3 tools/test.py tests.test_steam_drives
"""

import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
# No __pycache__ beside the helpers we load: the Linux package copies libexec/.
sys.dont_write_bytecode = True


def quick_helper():
    """linux/libexec/monet-quick as a module (it has no .py ending)."""
    loader = importlib.machinery.SourceFileLoader("monet_quick", str(ROOT / "linux/libexec/monet-quick"))
    spec = importlib.util.spec_from_loader("monet_quick", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def entry(path, contentid=None, apps=None):
    """One library as Steam lists it in libraryfolders.vdf."""
    lines = f'\t\t"path"\t\t"{path}"\n\t\t"label"\t\t""\n'
    if contentid is not None:
        lines += f'\t\t"contentid"\t\t"{contentid}"\n'
    lines += '\t\t"totalsize"\t\t"0"\n\t\t"apps"\n\t\t{\n'
    for appid in apps or ():
        lines += f'\t\t\t"{appid}"\t\t"1000"\n'
    return lines + "\t\t}\n"


def steam_list(entries):
    return '"libraryfolders"\n{\n' + "".join(f'\t"{k}"\n\t{{\n{v}\t}}\n' for k, v in entries.items()) + "}\n"


class SteamDrives(unittest.TestCase):
    def setUp(self):
        self.q = quick_helper()
        self.tmp = Path(tempfile.mkdtemp(prefix="monet-steam-drives-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.steam = self.tmp / "home/.local/share/Steam"
        (self.steam / "steamapps").mkdir(parents=True)
        (self.steam / "config").mkdir()
        # Steam closed, and Windows' Games folder not here this time.
        self.shared = self.tmp / "run/media/Windows games"
        for name, value in (("steam_running", lambda: False), ("SHARED", self.shared)):
            patcher = mock.patch.object(self.q, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def library(self, folder, contentid=None, apps=()):
        (folder / "steamapps").mkdir(parents=True)
        if contentid is not None:
            (folder / "libraryfolder.vdf").write_text(f'"libraryfolder"\n{{\n\t"contentid"\t\t"{contentid}"\n\t"label"\t\t""\n}}\n')
        for appid in apps:
            (folder / f"steamapps/appmanifest_{appid}.acf").write_text('"AppState" { }')
        return folder

    def lists(self, text, config=None):
        paths = self.steam / "steamapps/libraryfolders.vdf", self.steam / "config/libraryfolders.vdf"
        paths[0].write_text(text)
        paths[1].write_text(text if config is None else config)
        return paths

    def test_drives_are_read_from_the_mount_table(self):
        mountinfo, by_uuid = self.tmp / "mountinfo", self.tmp / "by-uuid"
        by_uuid.mkdir()
        (by_uuid / "1111-AAAA").symlink_to("/dev/monet-test-nvme1n1p1")
        (by_uuid / "2222-BBBB").symlink_to("/dev/monet-test-sda2")
        mountinfo.write_text("\n".join([
            "22 1 0:21 / / ro,relatime shared:1 - overlay composefs ro",
            "30 22 0:34 /root/ostree/deploy/default/var /var rw,relatime shared:5 - btrfs /dev/monet-test-nvme0n1p3 rw",
            "40 22 0:50 / /run/media rw,nosuid shared:9 - tmpfs tmpfs rw",
            "60 40 0:61 / /run/media/system/970 rw,noatime shared:40 - ext4 /dev/monet-test-nvme1n1p1 rw",
            "61 40 8:1 / /run/media/system/HDD rw,noatime shared:41 - ext4 /dev/monet-test-sda1 rw",
            r"62 40 8:17 / /run/media/ann/Ta\040Bort rw,nosuid shared:42 - ntfs3 /dev/monet-test-sdb1 rw",
            # Monet's own binds of Windows' folders are no drives of their own.
            r"63 40 259:4 /Games /run/media/Windows\040games rw shared:43 - ntfs3 /dev/monet-test-nvme0n1p4 rw",
            r"64 40 259:4 /Shared /run/media/Shared\040with\040Windows rw shared:44 - ntfs3 /dev/monet-test-nvme0n1p4 rw",
            "65 22 8:33 / /mnt/games rw shared:45 - xfs /dev/monet-test-sdc1 rw",
            "66 22 0:70 / /mnt/share rw shared:46 - nfs4 server:/export rw",
            # Mounted again over the same place: the later one is what's there.
            "67 40 8:2 / /run/media/system/HDD rw,noatime shared:47 - ext4 /dev/monet-test-sda2 rw",
        ]) + "\n")
        with mock.patch.object(self.q, "SHARED", Path("/run/media/Windows games")):
            found = self.q.drive_mounts(mountinfo, by_uuid)
        self.assertEqual(found, [(Path("/run/media/system/970"), "1111-AAAA"), (Path("/run/media/ann/Ta Bort"), ""),
                                 (Path("/mnt/games"), ""), (Path("/run/media/system/HDD"), "2222-BBBB")])
        self.assertEqual(self.q.drive_mounts(self.tmp / "none", by_uuid), [])
        self.assertEqual(self.q.drive_mounts(mountinfo, self.tmp / "none")[0], (Path("/run/media/system/970"), ""))

    def test_a_moved_library_is_found_again_by_its_own_contentid(self):
        q, now = self.q, self.tmp / "now/run/media/system"
        self.library(now / "970/SteamLibrary", "111", ["730"])
        kept = self.library(now / "HDD/Games", "222")
        self.library(now / "970/Copy of Windows games", "333")
        self.library(now / "970/Twin", "555")
        self.library(now / "HDD/Twin", "555")
        mounts = [(now / "970", "1111-AAAA"), (now / "HDD", "")]
        old = self.tmp / "old/run/media/media-automount/970/SteamLibrary"
        text = steam_list({
            "0": entry(self.steam, "1", ["228980"]),
            "1": entry(old, "111", ["730"]),
            "2": entry(kept, "222"),                                  # still there: never touched
            "3": entry(self.shared, "333"),                           # Windows' Games folder: comes and goes
            "4": entry(self.tmp / "old/gone/SteamLibrary", "444"),    # nowhere now: left as it is
            "5": entry(self.tmp / "old/run/media/ann/HDD/Twin", "555"),  # two places say 555: unsure, left
            "6": entry("relative/SteamLibrary", "111"),
        })
        config = steam_list({"0": entry(self.steam, "1"), "1": entry(old, "111")})
        lists = self.lists(text, config)
        self.assertEqual(q.steam_drives(self.steam, mounts), "moved")
        moved = str(now / "970/SteamLibrary")
        self.assertEqual(lists[0].read_text(), text.replace(f'"{old}"', f'"{moved}"'))
        self.assertEqual(lists[1].read_text(), config.replace(f'"{old}"', f'"{moved}"'))
        listed = q.vdf(lists[0].read_text())["libraryfolders"]
        self.assertEqual((listed["1"]["path"], listed["1"]["apps"]), (moved, {"730": "1000"}))
        # Both lists as they were before, kept beside them.
        self.assertEqual(lists[0].with_name("libraryfolders.vdf.before-drives").read_text(), text)
        self.assertEqual(lists[1].with_name("libraryfolders.vdf.before-drives").read_text(), config)
        # Again: nothing more to do.
        self.assertEqual(q.steam_drives(self.steam, mounts), "ok")
        self.assertEqual(lists[0].read_text(), text.replace(f'"{old}"', f'"{moved}"'))

    def test_a_drive_mounted_twice_gives_the_place_it_was_mounted_first(self):
        q, drive = self.q, self.tmp / "now/run/media/system/970"
        self.library(drive / "SteamLibrary", "111")
        second = self.tmp / "now/run/media/ann/970"
        second.parent.mkdir(parents=True)
        second.symlink_to(drive)  # the same folders, as a second mount shows them
        old = self.tmp / "old/run/media/media-automount/970/SteamLibrary"
        lists = self.lists(steam_list({"0": entry(self.steam), "1": entry(old, "111")}))
        self.assertEqual(q.steam_drives(self.steam, [(drive, ""), (second, "")]), "moved")
        self.assertEqual(q.vdf(lists[0].read_text())["libraryfolders"]["1"]["path"], str(drive / "SteamLibrary"))

    def test_without_a_contentid_the_drives_label_or_uuid_and_the_same_folder(self):
        q, now = self.q, self.tmp / "now"
        olds = [Path("/run/media/ann/HDD/Games"), Path("/run/media/media-automount/2222-BBBB/SteamLibrary"),
                Path("/run/media/ann/Stuff/Games"), Path("/run/media/ann/Data/Nowhere")]
        if any(p.exists() for p in olds):
            self.skipTest("this PC has these drives")
        self.library(now / "run/media/system/HDD/Games")
        self.library(now / "run/media/system/Data/SteamLibrary")
        self.library(now / "mnt/Games")  # named like a folder, not the drive Stuff
        mounts = [(now / "run/media/system/HDD", ""), (now / "run/media/system/Data", "2222-BBBB"), (now / "mnt/Games", "")]
        lists = self.lists(steam_list({"0": entry(self.steam), "1": entry(olds[0]), "2": entry(olds[1], "0"),
                                       "3": entry(olds[2]), "4": entry(olds[3])}))
        self.assertEqual(q.steam_drives(self.steam, mounts), "moved")
        listed = q.vdf(lists[0].read_text())["libraryfolders"]
        self.assertEqual([listed[k]["path"] for k in "1234"],
                         [str(now / "run/media/system/HDD/Games"), str(now / "run/media/system/Data/SteamLibrary"),
                          str(olds[2]), str(olds[3])])

    def test_a_library_added_again_by_hand_is_left_as_it_is(self):
        q, drive = self.q, self.tmp / "now/run/media/system/970"
        self.library(drive / "SteamLibrary", "111")
        old = self.tmp / "old/run/media/ann/970/SteamLibrary"
        text = steam_list({"0": entry(self.steam), "1": entry(old, "111"), "2": entry(drive / "SteamLibrary", "111")})
        lists = self.lists(text)
        self.assertEqual(q.steam_drives(self.steam, [(drive, "")]), "ok")
        self.assertEqual(lists[0].read_text(), text)
        self.assertFalse(lists[0].with_name("libraryfolders.vdf.before-drives").exists())

    def test_nothing_changes_while_steam_runs(self):
        q, drive = self.q, self.tmp / "now/run/media/system/970"
        self.library(drive / "SteamLibrary", "111")
        text = steam_list({"0": entry(self.steam), "1": entry(self.tmp / "old/970/SteamLibrary", "111")})
        lists = self.lists(text)
        with mock.patch.object(q, "steam_running", lambda: True):
            self.assertEqual(q.steam_drives(self.steam, [(drive, "")]), "steam-running")
        self.assertEqual((lists[0].read_text(), lists[1].read_text()), (text, text))
        self.assertEqual(sorted(p.name for p in lists[0].parent.iterdir()), ["libraryfolders.vdf"])

    def test_broken_or_missing_lists_are_left_alone(self):
        q, drive = self.q, self.tmp / "now/run/media/system/970"
        self.library(drive / "SteamLibrary", "111")
        mounts = [(drive, "")]
        self.assertEqual(q.steam_drives(self.tmp / "no-steam", mounts), "no-steam")
        old = self.tmp / "old/970/SteamLibrary"
        for text in ('"libraryfolders"\n{\n\t"1"\n\t{\n\t\t"path"\t\t"%s"\n\t\t"contentid"\t\t"111"\n\t}\n' % old,  # no end
                     '"libraryfolders"\t"%s"\n' % old,
                     '"LibraryFolders"\n{\n\t"TimeNextStatsReport"\t\t"1"\n\t"1"\t\t"%s"\n}\n' % old,  # Steam's old way
                     "\x00\xff{{ not keyvalues }}\"", ""):
            lists = self.lists(text)
            self.assertEqual(q.steam_drives(self.steam, mounts), "ok", text)
            self.assertEqual(lists[0].read_text(encoding="utf-8", errors="replace"), text)
        # A library folder whose own mark is broken isn't the one.
        (drive / "SteamLibrary/libraryfolder.vdf").write_text('"libraryfolder" "111"')
        lists = self.lists(steam_list({"0": entry(self.steam), "1": entry(old, "111")}))
        self.assertEqual(q.steam_drives(self.steam, mounts), "ok")
        # Without config/libraryfolders.vdf, the one in steamapps still gets it.
        (drive / "SteamLibrary/libraryfolder.vdf").write_text('"libraryfolder"\n{\n\t"contentid"\t\t"111"\n}\n')
        lists[1].unlink()
        self.assertEqual(q.steam_drives(self.steam, mounts), "moved")
        self.assertFalse(lists[1].exists())

    def test_windows_games_stays_in_steam(self):
        q, drive = self.q, self.tmp / "now/run/media/system/970"
        self.library(drive / "SteamLibrary", "111")
        lists = self.lists(steam_list({"0": entry(self.steam), "1": entry(self.shared, "77"),
                                       "2": entry(self.tmp / "old/970/SteamLibrary", "111")}))
        self.assertEqual(q.steam_drives(self.steam, [(drive, "")]), "moved")
        listed = q.vdf(lists[0].read_text())["libraryfolders"]
        self.assertEqual(listed["1"]["path"], str(self.shared))
        # Windows' drive shared again: steam-share finds its entry where it was, and adds no other.
        self.library(self.shared, "77")
        self.assertEqual(q.share_with_steam(self.steam, self.shared), "ok")
        paths = [e["path"] for e in q.vdf(lists[0].read_text())["libraryfolders"].values()]
        self.assertEqual(paths.count(str(self.shared)), 1)

    def test_a_value_is_set_in_its_own_block_only(self):
        q = self.q
        text = '"a"\n{\n\t"1"\n\t{\n\t\t"Path"\t\t"x"\n\t\t"apps"\n\t\t{\n\t\t\t"path"\t\t"y"\n\t\t}\n\t}\n}\n'
        self.assertEqual(q.vdf_set(text, ["A", "1"], "path", 'z "q"'), text.replace('"x"', '"z \\"q\\""'))
        self.assertEqual(q.vdf_set(text, ["a", "1", "apps"], "path", "w"), text.replace('"y"', '"w"'))
        self.assertIsNone(q.vdf_set(text, ["a", "1"], "label", "w"))
        self.assertIsNone(q.vdf_set(text, ["a", "2"], "path", "w"))

    def test_steam_waits_while_the_pc_mounts_its_drives(self):
        q = self.q
        jobs = ("  412 ublue-os-media-automount.service start waiting\n",
                "  431 systemd-fsck@dev-disk-by\\x2duuid-1111.service start running\n",
                "  433 run-media-system-Ta\\x2dBort.mount start waiting\n")
        for line in jobs:
            self.assertTrue(q.drives_settling(line), line)
        self.assertFalse(q.drives_settling("  500 plasma-kwin_wayland.service start running\n  501 tmp.mount stop waiting\n"))
        self.assertFalse(q.drives_settling(""))
        now, slept = [0.0], []

        def sleep(seconds):
            slept.append(seconds)
            now[0] += seconds

        answers = [True, True, False]
        self.assertTrue(q.wait_for_drives(30, lambda: answers.pop(0), sleep, lambda: now[0]))
        self.assertEqual(slept, [0.5, 0.5])
        slept.clear()
        self.assertFalse(q.wait_for_drives(2, lambda: True, sleep, lambda: now[0]))
        self.assertEqual(len(slept), 4)  # gives up after the time it's given
        # However slow the question is, the wait ends on time.
        slow = lambda: now.__setitem__(0, now[0] + 10) or True
        self.assertFalse(q.wait_for_drives(30, slow, sleep, lambda: now[0]))
        self.assertLessEqual(len(slept), 4 + 3)


class WhatRunsIt(unittest.TestCase):
    def test_before_steam_starts_and_at_sign_in(self):
        dropin = (ROOT / "linux/systemd/user/app-steam@autostart.service.d/monet-steam-share.conf").read_text()
        drives = "ExecStartPre=-@LIBEXECDIR@/monet-quick steam-drives wait\n"
        self.assertIn(drives, dropin)
        self.assertLess(dropin.index(drives), dropin.index("ExecStartPre=-@LIBEXECDIR@/monet-quick steam-share\n"))
        session = (ROOT / "linux/libexec/monet-session").read_text()
        # In the background: the desktop doesn't wait for the drives.
        self.assertIn('\n"$LIBEXECDIR/monet-quick" steam-drives wait >/dev/null 2>&1 &\n', session)
        quick = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        self.assertRegex(quick_helper().__doc__, r"monet-quick steam-drives \[wait\]\s")
        command = quick[quick.index('elif cmd == "steam-drives":'):]
        command = command[:command.index("elif cmd ==", 10)]
        # Once at a time: sign-in and Steam's autostart run it together.
        self.assertIn('fcntl.flock(lock, fcntl.LOCK_EX)', command)
        self.assertLess(command.index("wait_for_drives()"), command.index("steam_drives()"))

    def test_a_steam_library_in_var_tmp_is_not_cleared_away(self):
        rule = (ROOT / "linux/tmpfiles/monet-steam.conf").read_text()
        self.assertIn("\nx /var/tmp/SteamLibrary\n", rule)
        lines = [line for line in rule.splitlines() if line and not line.startswith("#")]
        self.assertEqual(lines, ["x /var/tmp/SteamLibrary"])  # nothing else in /var/tmp touched
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('put 644 "$SRC/tmpfiles/monet-steam.conf" "$TMPFILESDIR/monet-steam.conf"', install)
        self.assertIn("/etc/tmpfiles.d/monet-steam.conf", (ROOT / "linux/uninstall.sh").read_text())

    def test_bazzites_own_mounts_are_left_as_they_are(self):
        # Monet changes where Steam looks, never where Bazzite mounts the drives: nothing of
        # ublue-os-media-automount (its service, its rules or its /run/media link) is overridden.
        for folder in ("linux/tmpfiles", "linux/udev", "linux/systemd"):
            for path in (ROOT / folder).rglob("*"):
                if path.is_file():
                    self.assertNotIn("media-automount", path.read_text(encoding="utf-8", errors="replace"), path)
        self.assertNotIn("media-automount", (ROOT / "image/Containerfile").read_text())
        self.assertNotIn("media-automount", (ROOT / "image/finish-image.sh").read_text())


if __name__ == "__main__":
    unittest.main()
