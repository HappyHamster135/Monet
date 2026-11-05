"""Release packaging must carry the reviewed connector and its matching source."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    spec = importlib.util.spec_from_file_location('connector_packaging_fixture', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConnectorPackage(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = load(ROOT / 'browser/monet-passwords/package.py')
        for relative, names in {
            'browser/monet-passwords': (*self.package.INPUTS, 'release.json', 'package.py'),
            'linux/share/monet/passwords': ('connector.py', 'connector.xpi'),
            'tools': ('package.sh',),
        }.items():
            folder = self.root / relative; folder.mkdir(parents=True)
            for name in names: shutil.copyfile(ROOT / relative / name, folder / name)

    def test_shipped_artifact_and_recipe_are_bound_together(self):
        data = self.package.verify(self.root)
        self.assertEqual(data, (ROOT / 'linux/share/monet/passwords/connector.xpi').read_bytes())
        source = self.root / 'browser/monet-passwords/automatic-submit.js'
        source.write_text(source.read_text() + '\n// changed after signing\n')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            self.package.verify(self.root)

    def test_missing_or_corrupt_bundle_fails_before_replacing_package_output(self):
        output = self.root / 'output'; output.mkdir()
        marker = output / 'personal-file'; marker.write_text('keep')
        archive = self.root / 'linux/share/monet/passwords/connector.xpi'
        for content in (b'corrupt archive', None):
            if content is None: archive.unlink()
            else: archive.write_bytes(content)
            result = subprocess.run(['bash', str(self.root / 'tools/package.sh'), 'linux',
                                     str(self.root / 'binary'), str(output)],
                                    capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(marker.read_text(), 'keep')

    def test_different_rebuilt_payload_is_rejected(self):
        import zipfile
        rebuilt = self.root / 'candidate.xpi'
        with zipfile.ZipFile(ROOT / 'linux/share/monet/passwords/connector.xpi') as source:
            with zipfile.ZipFile(rebuilt, 'w') as target:
                for name in source.namelist():
                    if not name.startswith('META-INF/'):
                        target.writestr(name, source.read(name))
        self.package.verify(self.root, rebuilt)
        with zipfile.ZipFile(rebuilt, 'a') as target:
            target.writestr('unexpected.js', 'alert("changed");')
        with self.assertRaisesRegex(ValueError, 'rebuilt source'):
            self.package.verify(self.root, rebuilt)

    def test_preview_plan_contains_verified_archive_without_installing(self):
        preview = load(ROOT / 'tools/install-desktop-preview.py')
        for name in ('DATA', 'CONFIG', 'STATE', 'HELPERS', 'PRIVATE'):
            setattr(preview, name, self.root / name.lower())
        with patch.object(preview, 'cli_prefix', return_value=None):
            plan = preview.plan()
        archive = preview.PRIVATE / 'monet/passwords/connector.xpi'
        self.assertEqual(plan[archive], (self.package.verify(), 0o644))
        self.assertFalse(archive.exists())

    def test_installer_rejects_corrupt_archive_before_any_system_operation(self):
        shutil.copyfile(ROOT / 'linux/install.sh', self.root / 'linux/install.sh')
        (self.root / 'linux/share/monet/passwords/connector.xpi').write_bytes(b'corrupt')
        # No installation, privilege or service commands are reachable even if
        # a regression accidentally moves the verification past its preflight.
        commands = self.root / 'commands'; commands.mkdir()
        for command in ('python3', 'dirname'):
            (commands / command).symlink_to(shutil.which(command))
        result = subprocess.run(['bash', str(self.root / 'linux/install.sh'), '--image'],
                                env=dict(os.environ, PATH=str(commands)),
                                executable=shutil.which('bash'), capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('not installed completely', result.stderr)


if __name__ == '__main__':
    unittest.main()
