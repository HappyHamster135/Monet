"""First boot must respect an empty choice without requiring a network."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FirstBootApps(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / 'state'; self.state.mkdir()
        self.desktop = self.root / 'desktop'; self.desktop.mkdir()
        self.bin = self.root / 'bin'; self.bin.mkdir()
        self.calls = self.root / 'calls'
        source = (ROOT / 'linux/libexec/monet-apps').read_text()
        source = source.replace('STATE=/var/lib/monet', 'STATE=' + str(self.state))
        source = source.replace('/usr/share/applications/', str(self.desktop) + '/')
        self.script = self.root / 'run'; self.script.write_text(source)
        fake = self.bin / 'flatpak'
        fake.write_text('''#!/bin/bash
printf '%s\\n' "$*" >> "$FIXTURE_CALLS"
if [ "$1" = remote-add ]; then exit "${FIXTURE_REMOTE_RESULT:-0}"; fi
if [ "${@: -1}" = "${FIXTURE_FAIL_APP:-}" ]; then exit 1; fi
''')
        fake.chmod(0o755)

    def run_apps(self, **changes):
        env = dict(os.environ, PATH=str(self.bin) + ':' + os.environ['PATH'], FIXTURE_CALLS=str(self.calls), **changes)
        return subprocess.run(['bash', str(self.script)], env=env, capture_output=True, text=True, timeout=10)

    def test_empty_choice_finishes_offline_without_calling_flatpak(self):
        (self.state / 'apps').write_text('')
        self.assertEqual(self.run_apps(FIXTURE_REMOTE_RESULT='1').returncode, 0)
        self.assertTrue((self.state / 'apps-done').is_file())
        self.assertFalse((self.state / 'apps').exists())
        self.assertFalse(self.calls.exists())

    def test_only_builtin_apps_and_invalid_ids_need_no_remote(self):
        (self.state / 'apps').write_text('org.monet.Builtin\n--invalid\n../invalid\n')
        (self.desktop / 'org.monet.Builtin.desktop').touch()
        self.assertEqual(self.run_apps(FIXTURE_REMOTE_RESULT='1').returncode, 0)
        self.assertTrue((self.state / 'apps-done').exists())
        self.assertFalse(self.calls.exists())

    def test_remote_failure_preserves_the_choice_for_retry(self):
        selected = 'org.monet.Missing\n'
        (self.state / 'apps').write_text(selected)
        self.assertEqual(self.run_apps(FIXTURE_REMOTE_RESULT='1').returncode, 1)
        self.assertEqual((self.state / 'apps').read_text(), selected)
        self.assertFalse((self.state / 'apps-done').exists())
        self.assertEqual(len(self.calls.read_text().splitlines()), 1)

    def test_partial_failure_retries_only_missing_apps(self):
        (self.state / 'apps').write_text('org.monet.First\norg.monet.Second\norg.monet.Builtin\n')
        (self.desktop / 'org.monet.Builtin.desktop').touch()
        self.assertEqual(self.run_apps(FIXTURE_FAIL_APP='org.monet.First').returncode, 1)
        self.assertEqual((self.state / 'apps').read_text(), 'org.monet.First\n')
        self.assertNotIn('org.monet.Builtin', self.calls.read_text())
        self.calls.unlink()
        self.assertEqual(self.run_apps().returncode, 0)
        self.assertIn('org.monet.First', self.calls.read_text())
        self.assertNotIn('org.monet.Second', self.calls.read_text())
        self.assertTrue((self.state / 'apps-done').exists())


if __name__ == '__main__': unittest.main()
