"""Homebrew identity, detection and native package operation regressions."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.test import private_session
sys.path.insert(0, str(ROOT / "linux/share/monet/utilities"))
from brew_packages import locate, package_info, search_results


class Packages(unittest.TestCase):
    def test_installed_records_distinguish_kind_pins_and_dependencies(self):
        formula = {"name": "sample", "versions": {"stable": "2"}, "revision": 2, "outdated": True,
                   "installed": [{"version": "1", "installed_on_request": False},
                                 {"version": "1.1", "installed_on_request": False}], "dependencies": ["dep"]}
        cask = {"token": "sample", "version": "1.5", "installed": "1", "outdated": True, "pinned": True}
        data = package_info(json.dumps({"formulae": [formula], "casks": [cask]}))
        f = data["formula", "sample"]
        self.assertEqual((f.installed, f.available, f.dependencies), ("1, 1.1", "2_2", ("dep",)))
        self.assertTrue(f.dependency and f.upgradable)
        self.assertFalse(data["cask", "sample"].upgradable)
        hits = search_results(b"sample\nsome/tap/brew@3\n--install\n> header two\ninvalid/two\n", "cask", data)
        self.assertEqual(list(hits), [("cask", "sample"), ("cask", "some/tap/brew@3")])
        self.assertIs(hits["cask", "sample"], data["cask", "sample"])
        with self.assertRaises(ValueError):
            package_info('{"formulae": {}}')

    def test_incomplete_installation_and_custom_executable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            brew = root / "Homebrew/bin/brew"
            brew.parent.mkdir(parents=True)
            brew.write_text("#!/bin/sh\nexit 0\n")
            brew.chmod(0o755)
            link = root / "brew"
            link.symlink_to(brew)
            self.assertEqual(locate(str(link)), ("", "incomplete"))
            main = root / "Homebrew/Library/Homebrew/brew.sh"
            main.parent.mkdir(parents=True)
            main.touch()
            self.assertEqual(locate(str(link)), (str(link), ""))
        for invalid in (["invalid"], "relative/path"):
            self.assertEqual(locate(invalid), ("", "missing"))

    @unittest.skipUnless(importlib.util.find_spec("PySide6"), "requires Qt")
    def test_cancel_failure_close_and_reopen(self):
        with private_session() as env:
            result = subprocess.run([sys.executable, "-B", __file__, "--fixture"], env=env, cwd=ROOT,
                                    text=True, capture_output=True, timeout=28)
        self.assertEqual(result.returncode, 0, result.stderr)


def fixture():
    from PySide6.QtCore import QSettings
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    import time
    from window import Window

    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    root = Path(os.environ["HOME"])
    cli = root / "brew"
    cli.write_text("""#!/usr/bin/python3
import os, sys, time
from pathlib import Path
root = Path(os.environ["HOME"])
if sys.argv[1] == "info":
    print('{"formulae":[],"casks":[]}')
elif sys.argv[1] == "search":
    print("example")
elif (root / "fail").exists():
    print("failure diagnostic",file=sys.stderr)
    sys.exit(1)
else:
    (root / "started").touch()
    try:
        for _ in range(500):
            if (root / "release").exists():break
            time.sleep(0.02)
    except KeyboardInterrupt:
        (root / "cancelled").touch()
        sys.exit(130)
""")
    cli.chmod(0o700)
    settings = QSettings("Monet", "Utilities")
    settings.setValue("brewExecutable", str(cli))
    settings.sync()
    window = Window("/usr/libexec")
    window.Open(["homebrew"])
    page = window.pages["homebrew"]

    def wait(predicate):
        until = time.monotonic() + 5
        while not predicate() and time.monotonic() < until:
            QTest.qWait(25)
        assert predicate(), page.status.text()

    wait(lambda: page.loaded)
    page.view.setCurrentIndex(1)
    page.text.setText("example")
    page.search()
    wait(lambda: page.job is None)
    assert page.selected().name == "example"
    page.install.click()
    wait(lambda: (root / "started").exists())
    page.stop.click()
    wait(lambda: page.job is None)
    assert (root / "cancelled").exists() and "cancelled" in page.status.text().lower()
    (root / "fail").touch()
    page.install.click()
    wait(lambda: page.job is None)
    assert page.show_log.isChecked() and "failure diagnostic" in page.log.toPlainText()
    (root / "fail").unlink()
    page.install.click()
    window.close()
    assert not window.isVisible() and page.applying_action
    window.Open(["homebrew"])
    (root / "release").touch()
    wait(lambda: page.job is None)
    assert window.isVisible() and page.loaded
    page.configure(str(root / "unknown-brew"))
    assert not page.last_command and not page.model.rows and page.setup.isVisible()
    window.close()


if __name__ == "__main__" and sys.argv[1:] == ["--fixture"]:
    fixture()
