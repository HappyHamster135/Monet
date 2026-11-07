"""Extraction failures on a dedicated, deliberately full temporary filesystem."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

from tests.test_files_qol import jobs_module
from tests.native_archive_session import desktop, key, run_job, text


@unittest.skipUnless(all(shutil.which(tool) for tool in ('ark', '7z', 'Xvfb', 'xdotool')),
                     'native encrypted archive dialog runtime')
class NativePasswords(unittest.TestCase):
    password = 'Monet-test-password'

    def exercise(self, suffix, response):
        with desktop(), tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            source = folder / 'readme.txt'; source.write_text('native encrypted extraction')
            archive = folder / ('private.' + suffix)
            command = ['7z', 'a', '-p' + self.password]
            if suffix == '7z': command.append('-mhe=on')
            subprocess.run([*command, str(archive), str(source)], check=True, stdout=subprocess.DEVNULL)
            queue = jobs_module().Queue(folder / 'transfers')
            job = queue.submit(archive, folder / 'extracted')
            titles = run_job(queue, job['token'], response, repeat=True)
            self.assertTrue(any('password' in title.lower() for title in titles), titles)
            result = queue.read(job['token'])
            if result['state'] == 'done':
                self.assertEqual((folder / 'extracted/readme.txt').read_text(), source.read_text())
            return result

    def test_real_zip_and_header_encrypted_seven_zip_use_native_password_dialogs(self):
        def answer(window, title):
            if 'password' in title.lower():
                key(window, 'ctrl+a'); text(self.password); key(window, 'Return')
            else: key(window, 'Escape')
        for suffix in ('zip', '7z'):
            with self.subTest(suffix=suffix):
                self.assertEqual(self.exercise(suffix, answer)['state'], 'done')

    def test_cancelling_native_password_dialog_is_never_completion(self):
        self.assertEqual(self.exercise('7z', lambda window, title: key(window, 'Escape'))['state'], 'cancelled')

    def test_wrong_password_cannot_be_reported_as_success(self):
        answered = []
        def answer(window, title):
            if 'password' in title.lower() and not answered:
                answered.append(True)
                text('incorrect-test-password'); key(window, 'Return')
            else: key(window, 'Escape')
        self.assertIn(self.exercise('zip', answer)['state'], ('failed', 'cancelled'))


@unittest.skipUnless(os.environ.get('MONET_TEST_ARCHIVE_TMPFS') and all(shutil.which(tool) for tool in ('ark', 'Xvfb', 'xdotool')),
                     'opt-in dedicated small tmpfs and native Ark')
class NativeFullDisk(unittest.TestCase):
    def test_enospc_preserves_partial_output_and_retry_uses_a_new_folder(self):
        # The caller supplies an otherwise unused, private tmpfs (for example a
        # disposable Podman /dev/shm). Never fill an arbitrary host filesystem.
        root = Path(os.environ['MONET_TEST_ARCHIVE_TMPFS']).resolve(strict=True)
        self.assertEqual(os.stat(root).st_dev, os.stat('/dev/shm').st_dev)
        self.assertNotEqual(os.stat(root).st_dev, os.stat('/tmp').st_dev)
        fs = os.statvfs(root)
        capacity = fs.f_blocks * fs.f_frsize
        self.assertLessEqual(capacity, 128 * 1024 * 1024)
        self.assertGreaterEqual(capacity, 1024 * 1024)
        with desktop(), tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory(dir=root) as output:
            folder = Path(temp); target = Path(output)
            source = folder / 'photos.zip'
            content = os.urandom(512 * 1024)
            with zipfile.ZipFile(source, 'w') as archive:
                archive.writestr('photo.bin', content)
            filler = target / 'space-used-by-another-file'
            available = os.statvfs(target).f_bavail * fs.f_frsize
            with filler.open('wb') as stream:
                stream.write(b'x' * (available - 128 * 1024))
            queue = jobs_module().Queue(folder / 'transfers')
            job = queue.submit(source, target / 'extracted')
            dialogs = run_job(queue, job['token'], lambda window, title: key(window, 'Return'))
            self.assertTrue(dialogs, 'Ark should explain the real disk-full failure')
            self.assertEqual(queue.read(job['token'])['state'], 'failed')
            self.assertTrue((target / 'extracted').is_dir())
            # Reclaim space, then retry through the same production queue.
            # No original/partial directory may be reused or overwritten.
            partial = {p.name: p.read_bytes() for p in (target / 'extracted').iterdir() if p.is_file()}
            filler.unlink()
            # Keep this synchronous so the isolated test owns and reaps Ark.
            from unittest.mock import patch
            with patch.object(queue, 'launch'):
                retry = queue.control(job['token'], 'retry')
            self.assertNotEqual(retry['destination'], job['destination'])
            run_job(queue, retry['token'])
            self.assertEqual(queue.read(retry['token'])['state'], 'done')
            self.assertEqual((Path(retry['destination']) / 'photo.bin').read_bytes(), content)
            self.assertEqual({p.name: p.read_bytes() for p in (target / 'extracted').iterdir() if p.is_file()}, partial)


if __name__ == '__main__':
    unittest.main()
