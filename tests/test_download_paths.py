"""Native XDG and Browser agree on defaults and literal custom destinations."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from tests.test_look import quick_helper


@unittest.skipUnless(shutil.which('xdg-user-dirs-update'), 'XDG user directories')
class DownloadPaths(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.config = self.home / '.config'; self.config.mkdir()
        self.quick = quick_helper()
        self.quick.HOME, self.quick.CONFIG = self.home, self.config
        self.data = self.home / '.local/share'; self.data.mkdir(parents=True)
        system = self.home / 'system-config'; system.mkdir()
        (system / 'user-dirs.defaults').write_text('DESKTOP=Desktop\nDOWNLOAD=Downloads\n')
        self.env = patch.dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.config),
                              XDG_DATA_HOME=str(self.data), XDG_CONFIG_DIRS=str(system),
                              XDG_DATA_DIRS=str(self.home / 'system-data'))
        self.env.start(); self.addCleanup(self.env.stop)
        self.root = self.home / '.zen'; self.root.mkdir()
        self.profile = self.root / 'default'; self.profile.mkdir()
        (self.root / 'profiles.ini').write_text('[Profile0]\nIsRelative=1\nPath=default\n')
        self.quick.zen_root = lambda: self.root

    def test_first_login_defaults_to_localized_desktop_once_and_retains_old_downloads(self):
        desktop = self.home / 'Skrivbord'; desktop.mkdir()
        downloads = self.home / 'Downloads'; downloads.mkdir()
        (downloads / 'keep.txt').write_text('keep')
        (self.config / 'user-dirs.dirs').write_text('XDG_DESKTOP_DIR="$HOME/Skrivbord"\nXDG_DOWNLOAD_DIR="$HOME/Downloads"\n')
        # MIME policy is separate from native directory integration in this check.
        with patch.object(self.quick, 'ARCHIVE_MIMES', ()):
            self.quick.files_defaults()
            self.assertEqual(self.quick.downloads_dir(), desktop)
            self.assertEqual(subprocess.check_output(['xdg-user-dir', 'DOWNLOAD'], text=True).strip(), str(desktop))
            self.assertEqual((downloads / 'keep.txt').read_text(), 'keep')
            custom = self.home / 'Keep downloads here'; custom.mkdir()
            self.quick.set_download_path(custom)
            self.quick.files_defaults()
            self.assertEqual(self.quick.downloads_dir(), custom)

    def test_custom_paths_are_literal_in_xdg_and_browser_and_other_prefs_stay(self):
        target = self.home / 'Work "quoted" $HOME $(touch NO) `echo x` \\ å'; target.mkdir()
        prefs = self.profile / 'user.js'
        prefs.write_text('user_pref("my.preference", true);\nuser_pref("browser.download.dir", "/old");\n')
        self.quick.set_download_path(target)
        self.assertEqual(self.quick.downloads_dir(), target)
        self.assertEqual(subprocess.check_output(['xdg-user-dir', 'DOWNLOAD'], text=True).strip(), str(target))
        self.assertIn('user_pref("my.preference", true);', prefs.read_text())
        line, = [line for line in prefs.read_text().splitlines() if '"browser.download.dir"' in line]
        self.assertEqual(json.loads(line.split(', ', 1)[1].removesuffix(');')), str(target))
        self.assertFalse((self.home / 'NO').exists())

    def test_existing_custom_destination_is_preserved_and_bad_selection_keeps_preferences(self):
        custom = self.home / 'Projects'; custom.mkdir()
        self.quick.set_download_path(custom)
        with patch.object(self.quick, 'ARCHIVE_MIMES', ()):
            self.quick.files_defaults()
        self.assertEqual(self.quick.downloads_dir(), custom)
        before = (self.config / 'user-dirs.dirs').read_bytes()
        for invalid in (self.home / 'missing', self.profile / 'user.js', self.home):
            with self.assertRaises((ValueError, OSError)):
                self.quick.set_download_path(invalid)
        self.assertEqual((self.config / 'user-dirs.dirs').read_bytes(), before)

    @unittest.skipUnless(shutil.which('xdg-mime'), 'native MIME defaults')
    def test_archives_use_monet_handler_and_keep_an_explicit_alternative(self):
        apps = self.data / 'applications'; apps.mkdir()
        for name in ('monet-archive.desktop', 'org.kde.ark.desktop', 'personal-archive.desktop'):
            (apps / name).write_text('[Desktop Entry]\nType=Application\nName=Archive\nExec=/usr/bin/true %f\n'
                                     'MimeType=application/zip;application/x-tar;application/x-rpm;\n')
        (self.config / 'mimeapps.list').write_text('[Default Applications]\n'
            'application/zip=org.kde.ark.desktop;\napplication/x-tar=personal-archive.desktop;\napplication/x-rpm=org.kde.ark.desktop;\n')
        self.quick.files_defaults()
        self.assertEqual(subprocess.check_output(['xdg-mime', 'query', 'default', 'application/zip'], text=True).strip(),
                         'monet-archive.desktop')
        self.assertEqual(subprocess.check_output(['xdg-mime', 'query', 'default', 'application/x-tar'], text=True).strip(),
                         'personal-archive.desktop')
        self.assertEqual(subprocess.check_output(['xdg-mime', 'query', 'default', 'application/x-rpm'], text=True).strip(),
                         'monet-archive.desktop')
