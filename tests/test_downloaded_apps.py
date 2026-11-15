"""A fresh download is found without index entries, executable bits or first launch."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tests.test_look import quick_helper


class DownloadedApps(unittest.TestCase):
    def setUp(self):
        self.q = quick_helper()
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.roots = [self.root / 'Desktop', self.root / 'My downloads']
        for folder in self.roots: folder.mkdir()
        mock = patch.object(self.q, 'downloaded_app_roots', return_value=self.roots)
        mock.start(); self.addCleanup(mock.stop)
        locations = patch.object(self.q, 'downloaded_app_locations', return_value=self.roots)
        locations.start(); self.addCleanup(locations.stop)

    def file(self, name, folder=1):
        path = self.roots[folder] / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'MZfixture'); path.chmod(0o600)
        return path

    def test_unopened_exe_msi_and_appimage_are_found_and_never_executed(self):
        exe = self.file('ChatGPT Setup.EXE')
        self.file('nested/App.MSI'); self.file('stack/Applications/Portable.AppImage', 0)
        with patch.object(self.q.subprocess, 'Popen') as launch:
            rows = self.q.downloaded_apps('chatgpt')
            self.assertEqual(rows[0]['name'], exe.name)
            self.assertIn('Windows installer', rows[0]['detail'])
            self.assertIn('My downloads', rows[0]['detail'])
            self.assertEqual(bytes.fromhex(rows[0]['id'][9:]).decode(), str(exe))
            self.assertTrue(self.q.downloaded_apps('app msi'))
            self.assertTrue(self.q.downloaded_apps('portable'))
            launch.assert_not_called()

    def test_hidden_partial_links_and_folders_are_not_apps(self):
        self.file('ChatGPT.exe.part'); self.file('.ChatGPT.exe')
        self.file('.hidden/ChatGPT.exe')
        outside = self.root / 'ChatGPT.exe'; outside.write_bytes(b'MZfixture')
        (self.roots[0] / 'ChatGPT.exe').symlink_to(outside)
        (self.roots[0] / 'ChatGPT-copy.exe').mkdir()
        self.assertEqual(self.q.downloaded_apps('chatgpt'), [])

    def test_case_accents_duplicate_roots_and_exact_name_first(self):
        old = self.file('Éditor.exe', 0); new = self.file('Editor setup.exe')
        os.utime(old, (1, 1)); os.utime(new, (2, 2))
        rows = self.q.downloaded_apps('EDITOR', roots=[*self.roots, self.roots[0]])
        self.assertEqual([row['name'] for row in rows], [old.name, new.name])
        self.assertEqual(len(self.q.downloaded_apps('editor', limit=1)), 1)
        self.assertEqual(self.q.downloaded_apps('editor', budget=0), [])
        self.assertEqual(self.q.downloaded_apps('e'), [])

    def test_click_uses_existing_windows_prompt_with_literal_path(self):
        exe = self.file('ChatGPT $(touch BAD) `%U` å.exe')
        token = self.q.downloaded_apps('chatgpt')[0]['id'][9:]
        with patch.object(self.q, 'windows_program', return_value=True) as open_app:
            self.assertTrue(self.q.open_downloaded_app(token))
            open_app.assert_called_once_with(str(exe))
        self.assertFalse((self.root / 'BAD').exists())

    def test_stale_and_replaced_results_fail_without_launching(self):
        exe = self.file('ChatGPT.exe'); token = str(exe).encode().hex()
        exe.unlink()
        outside = self.root / 'outside.exe'; outside.write_bytes(b'MZfixture')
        with patch.object(self.q, 'windows_program') as open_app:
            self.assertFalse(self.q.open_downloaded_app(token))
            exe.symlink_to(outside)
            self.assertFalse(self.q.open_downloaded_app(token))
            self.assertFalse(self.q.open_downloaded_app(str(outside).encode().hex()))
            for token in ('ff', '00', '../escape', 'ab' * 10000):
                self.assertFalse(self.q.open_downloaded_app(token))
            open_app.assert_not_called()

    def test_downloaded_rpm_offers_extraction_without_running_the_package(self):
        package = self.file("ChatGPT.x86_64.rpm")
        exe = self.file("ChatGPT Setup.exe")
        rows = self.q.downloaded_apps("chatgpt")
        self.assertEqual([row["name"] for row in rows], [exe.name, package.name])
        self.assertIn("Linux package", rows[1]["detail"])
        with patch.object(self.q.subprocess, "Popen") as launch:
            self.assertTrue(self.q.open_downloaded_app(rows[1]["id"][9:]))
            launch.assert_called_once_with([f"{self.q.LIBEXECDIR}/monet-files-tools", "unpack", str(package)],
                                           start_new_session=True)

    def test_large_desktop_does_not_starve_downloads(self):
        for n in range(10): self.file(f'document-{n}.txt', 0)
        self.file('ChatGPT.exe')
        self.assertEqual(self.q.downloaded_apps('chatgpt', budget=2)[0]['name'], 'ChatGPT.exe')

    def test_deep_executables_are_found_beyond_the_old_budget(self):
        crowded = self.roots[0] / 'bundle'
        crowded.mkdir()
        for n in range(2005):
            (crowded / f'asset-{n}.txt').touch()
        exe = self.file('bundle/tools/windows/bin/Chat GPT Setup.exe', 0)
        opened = self.q.downloaded_apps('chatgpt')
        self.assertEqual(opened[0]['name'], exe.name)
        self.assertIn('bundle/tools/windows/bin', opened[0]['detail'])

    def test_bundle_name_finds_a_generic_executable_through_nested_folders(self):
        exe = self.file('Chat GPT - 2.0/win64/bin/Setup.exe')
        self.file('Chat GPT - 2.0/win64/bin/unins000.exe')
        self.file('Chat GPT - 2.0/assets/setup.exe.part')
        exact = self.file('ChatGPT.exe', 0)

        rows = self.q.downloaded_apps('chatgpt')
        self.assertEqual([row['name'] for row in rows], [exact.name, 'Chat GPT - 2.0 · Setup.exe'])
        self.assertIn('Chat GPT - 2.0/win64/bin', rows[1]['detail'])
        with patch.object(self.q, 'windows_program', return_value=True) as start:
            self.assertTrue(self.q.open_downloaded_app(rows[1]['id'][9:]))
            start.assert_called_once_with(str(exe))
        self.assertEqual(self.q.downloaded_apps('unins')[0]['name'], 'unins000.exe')

    def test_home_export_folders_still_require_matching_filenames(self):
        docs = self.root / 'Documents'
        (docs / 'ChatGPT').mkdir(parents=True)
        (docs / 'ChatGPT' / 'Setup.exe').write_bytes(b'MZfixture')
        other = docs / 'ChatGPT' / 'ChatGPT.exe'
        other.write_bytes(b'MZfixture')
        with patch.object(self.q, 'downloaded_app_locations', return_value=[self.root]), \
                patch.object(self.q, 'HOME', self.root):
            rows = self.q.downloaded_apps('chatgpt', roots=[docs, self.root])
        self.assertEqual([row['name'] for row in rows], [other.name])

    def test_unpacked_linux_app_is_found_without_registration(self):
        app = self.file('chatgpt.x86_64/usr/lib/chatgpt/ChatGPT', 0)
        app.write_bytes(b'\x7fELFfixture'); app.chmod(0o700)
        artwork = self.file('chatgpt.svg', 0)
        artwork.write_text('<svg/>'); artwork.chmod(0o700)
        rows = self.q.downloaded_apps('chat gpt')
        self.assertEqual([row['name'] for row in rows], ['ChatGPT'])
        token = rows[0]['id'][9:]
        with patch.object(self.q, 'ok', return_value=False), patch.object(self.q, 'native_run') as launch:
            self.assertTrue(self.q.open_downloaded_app(token))
            launch.assert_not_called()
        with patch.object(self.q, 'ok', return_value=True), patch.object(self.q, 'native_run', return_value=True) as launch:
            self.assertTrue(self.q.open_downloaded_app(token))
            launch.assert_called_once_with(token)
