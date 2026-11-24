"""Browser-default preparation preserves personal preferences and reports failed writes."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.test_look import SHARE, quick_helper
from tests.test_browser_session import b

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'linux', 'Linux installation revisions')
class BuildRevision(unittest.TestCase):
    @unittest.skipUnless(shutil.which('systemd-tmpfiles'), 'requires systemd-tmpfiles')
    def test_flatpak_default_is_scoped_to_zen_and_keeps_local_overrides(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rules = root/'usr/lib/tmpfiles.d'
            rules.mkdir(parents=True)
            source = ROOT/'linux/tmpfiles/monet-zen.conf'
            (rules/source.name).write_text(source.read_text().replace('@DATADIR@', '/usr/share'))
            factory = Path('/usr/share/monet/zen/flatpak-defaults')
            installed = root/factory.relative_to('/')
            installed.parent.mkdir(parents=True)
            shutil.copy(ROOT/'linux/share/monet/zen/flatpak-defaults', installed)
            cmd = ['systemd-tmpfiles', '--root', str(root), '--create', source.name]
            subprocess.run(cmd, check=True, timeout=5)
            overrides = root/'var/lib/flatpak/overrides'
            override, = overrides.iterdir()
            self.assertEqual(override.name, 'app.zen_browser.zen')
            self.assertEqual(override.readlink(), factory)
            self.assertEqual(installed.read_text().splitlines(), [
                '[Environment]', 'MOZ_DEFAULT_PREFS=pref("zen.glance.open-essential-external-links", false);'])
            override.unlink()
            override.write_text('[Environment]\nLOCAL_DEFAULT=1\n')
            subprocess.run(cmd, check=True, timeout=5)
            self.assertEqual(override.read_text(), '[Environment]\nLOCAL_DEFAULT=1\n')

    def test_same_version_helper_or_browser_asset_changes_refresh_session_without_clearing_qml(self):
        source = (ROOT / 'linux/install.sh').read_text()
        revisions = source[source.index('# QML files in OS images'):]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            share = root / 'share/monet'; (share / 'zen').mkdir(parents=True)
            helpers = root / 'libexec'; helpers.mkdir()
            quick = helpers / 'monet-quick'; quick.write_text('original browser defaults\n')
            css = share / 'zen/zen.css'; css.write_text('original browser appearance\n')
            (share / 'fixture.qml').write_text('unchanged desktop\n')
            (root / 'VERSION').write_text('0.9.8-8\n')
            env = dict(os.environ, SRC=str(root), DATADIR=str(root / 'share'))
            def revision():
                result = subprocess.run(['bash','-euo','pipefail','-c',revisions],env=env,
                                        capture_output=True,text=True,timeout=5)
                self.assertEqual(result.returncode,0,result.stderr)
                return tuple((share / f'{name}-revision').read_text() for name in ('desktop','session'))
            first = revision()
            os.utime(quick, (1,1)); os.utime(css, (2,2))
            self.assertEqual(revision(),first)
            for file in [quick,css]:
                file.write_text(file.read_text()+'updated\n')
                following = revision()
                self.assertEqual(following[0],first[0])
                self.assertNotEqual(following[1],first[1])
                first = following
            self.assertEqual((root / 'VERSION').read_text(),'0.9.8-8\n')


class ZenDefaults(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.apps = self.root / 'apps'; self.apps.mkdir()
        (self.apps / 'app.zen_browser.zen.desktop').touch()
        self.q = quick_helper(); self.q.app_dirs = lambda: [self.apps]
        self.q.zen_root = lambda: self.root / '.zen'; self.q.DATADIR = str(SHARE)
        self.q.older_here = lambda: False

    def test_session_preparation_keeps_restore_privacy_and_personal_browser_choices(self):
        profile = self.q.zen(strict=True)[0]
        prefs = profile / 'prefs.js'
        personal = 'user_pref("browser.privatebrowsing.autostart", true);\n'
        prefs.write_text(personal)
        user = profile / 'user.js'
        user.write_text('user_pref("browser.startup.page", 0);\n// Personal browser choices\n' + user.read_text())
        self.assertEqual(self.q.zen(strict=True), [profile])
        self.assertEqual(prefs.read_text(), personal)
        self.assertIn('// Personal browser choices\n', user.read_text())
        self.assertFalse(b.native_enabled(profile))
        self.assertTrue(b.private_profile(profile))
        self.assertNotIn('dom.disable_beforeunload', user.read_text())

    def test_failed_preparation_remains_retryable_and_does_not_claim_success(self):
        profile = self.q.zen()[0]
        user = profile / 'user.js'; user.unlink(); user.mkdir()
        with self.assertRaises(OSError): self.q.zen(strict=True)
        self.assertEqual(self.q.zen(), [])
        self.assertTrue(user.is_dir())
        user.rmdir()
        self.assertEqual(self.q.zen(strict=True), [profile])
        self.assertTrue(user.is_file())
