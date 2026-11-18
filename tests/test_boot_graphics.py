"""Build-root graphics changes keep drivers available and preserve other boot prerequisites."""
import importlib.util
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'image/boot'
spec = importlib.util.spec_from_file_location('boot_graphics', FOLDER / 'prepare.py')
boot = importlib.util.module_from_spec(spec); spec.loader.exec_module(boot)


class GraphicsAutoload(unittest.TestCase):
    def values(self, config):
        # Evaluate the generated configuration in the shell dracut uses.
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config'; path.write_text(config)
            result = subprocess.run(['bash', '-eu', '-c', 'force_drivers="storage vfio_pci"; add_drivers="existing"; source "$1"; printf "%s\\n%s\\n" "$force_drivers" "$add_drivers"', 'fixture', str(path)],
                                    capture_output=True, text=True, timeout=5, check=True)
            force, included = result.stdout.splitlines()
            return force.split(), included.split()

    def test_portable_modules_stay_included_without_unconditional_loading(self):
        modules = 'i915 amdgpu nvidia nvidia_drm nvidia_modeset nvidia_uvm'
        force, included = self.values(boot.autoload_config('force_drivers+=" ' + modules + ' "\n'))
        self.assertEqual(force, ['storage', 'vfio_pci'])
        self.assertEqual(included, ['existing', *modules.split()])

    def test_other_forced_modules_and_assignment_semantics_are_kept(self):
        force, included = self.values(boot.autoload_config('force_drivers+=" amdgpu btrfs nvidia-drm " # vendor\n'))
        self.assertEqual(force, ['storage', 'vfio_pci', 'btrfs'])
        self.assertEqual(included, ['existing', 'amdgpu', 'nvidia-drm'])
        force, included = self.values(boot.autoload_config('force_drivers=" i915 "\n'))
        self.assertEqual(force, []); self.assertIn('i915', included)

    def test_reapplying_does_not_duplicate_drivers(self):
        first = boot.autoload_config('force_drivers+=" i915 amdgpu nvidia_drm "\n')
        self.assertEqual(boot.autoload_config(first), first)

    def test_unrelated_and_dynamic_configuration_is_left_alone(self):
        text = '# force_drivers+=" amdgpu "\nforce_drivers+=" cryptd "\nforce_drivers+=$local_drivers\n'
        self.assertEqual(boot.autoload_config(text), text)

    def test_prepares_only_the_supplied_image_root(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); config = root / 'usr/lib/dracut/dracut.conf.d/99-nvidia.conf'
            config.parent.mkdir(parents=True); config.write_text('force_drivers+=" i915 nvidia_drm "\n')
            boot.prepare(root)
            self.assertIn('add_drivers', config.read_text())
            module = root / 'usr/lib/dracut/modules.d/99monet-graphics'
            self.assertTrue((module / 'module-setup.sh').stat().st_mode & 0o111)
            self.assertEqual((module / '61-monet-nvidia-kms.rules').read_bytes(), (FOLDER / '99monet-graphics/61-monet-nvidia-kms.rules').read_bytes())
            before = config.read_text(); boot.prepare(root); self.assertEqual(config.read_text(), before)

    def test_non_nvidia_images_need_no_vendor_preload_file(self):
        with tempfile.TemporaryDirectory() as folder:
            boot.prepare(folder)
            self.assertTrue((Path(folder) / 'usr/lib/dracut/modules.d/99monet-graphics/module-setup.sh').exists())

    def test_symlinked_vendor_config_is_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); config = root / 'usr/lib/dracut/dracut.conf.d/99-nvidia.conf'
            config.parent.mkdir(parents=True); outside = root / 'original'; outside.write_text('untouched')
            config.symlink_to(outside)
            with self.assertRaises(ValueError): boot.prepare(root)
            self.assertEqual(outside.read_text(), 'untouched')

    def test_dracut_installs_the_matching_device_rule(self):
        module = FOLDER / '99monet-graphics'
        result = subprocess.run(['bash', '-eu', '-c', 'moddir="$1"; source "$moddir/module-setup.sh"; check; depends; inst_rules() { printf "%s\\n" "$1"; }; install', 'fixture', str(module)],
                                capture_output=True, text=True, timeout=5, check=True)
        self.assertEqual(result.stdout.splitlines(), ['kernel-modules udev-rules', str(module / '61-monet-nvidia-kms.rules')])

    @unittest.skipUnless(shutil.which('udevadm'), 'requires native udev rule validation')
    def test_native_udev_accepts_the_nvidia_kms_rule(self):
        result = subprocess.run(['udevadm', 'verify', str(FOLDER / '99monet-graphics/61-monet-nvidia-kms.rules')],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
