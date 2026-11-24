"""Real greeter/boot frames and systemd phase accounting for boot benchmarks."""
import importlib.util
from pathlib import Path
import unittest

try:
    from PIL import Image
    HAVE_PIL=True
except ImportError:
    HAVE_PIL=False

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('boot_bench',ROOT/'tools/bench-boot.py')
bench=importlib.util.module_from_spec(spec);spec.loader.exec_module(bench)


class BootTiming(unittest.TestCase):
    def test_recorded_hardware_phases_do_not_double_count_the_bootloader(self):
        phases=bench.timing_phases(dict(FirmwareTimestampMonotonic='23454174',LoaderTimestampMonotonic='9073885',
            InitRDTimestampMonotonic='1836162',UserspaceTimestampMonotonic='6620013'))
        self.assertAlmostEqual(phases['firmware_ms'],14380.289)
        self.assertAlmostEqual(phases['loader_ms'],9073.885)
        self.assertAlmostEqual(phases['kernel_ms']+phases['initrd_ms'],6620.013)

    def test_a_boot_without_a_separate_initrd_keeps_the_kernel_time(self):
        phases=bench.timing_phases(dict(UserspaceTimestampMonotonic='1500000'))
        self.assertEqual(phases['kernel_ms'],1500)
        self.assertEqual(phases['initrd_ms'],0)

    @unittest.skipUnless(HAVE_PIL,"requires Pillow for actual boot frames")
    def test_real_release_login_clock_requires_a_keyboard_reveal(self):
        # Native KVM screenshot from v0.9.8-8 qualification, not a fabricated UI.
        with Image.open(ROOT/'tests/fixtures/boot-login-clock.png') as image:
            self.assertTrue(bench.login_clock(image))
            self.assertFalse(bench.login_controls(image))

    @unittest.skipUnless(HAVE_PIL,"requires Pillow for actual boot frames")
    def test_real_starting_frame_is_not_a_login_screen(self):
        with Image.open(ROOT/'tests/fixtures/boot-starting.png') as image:
            self.assertFalse(bench.login_clock(image))
            self.assertFalse(bench.login_controls(image))

    @unittest.skipUnless(HAVE_PIL,"requires Pillow for actual boot frames")
    def test_uniform_screens_and_a_small_brand_dot_are_not_ready(self):
        from PIL import ImageDraw
        for color in ('black','white','#F2552C'):
            image=Image.new('RGB',(1280,800),color)
            self.assertFalse(bench.login_controls(image))
            self.assertFalse(bench.login_clock(image))
        image=Image.new('RGB',(1280,800),'#242321')
        ImageDraw.Draw(image).ellipse((307,300,316,309),fill='#F2552C')
        self.assertFalse(bench.login_clock(image))

    def test_multiline_or_non_ed25519_keys_cannot_enter_a_guest_unit(self):
        for key in ('ssh-ed25519 abc monet-boot-benchmark\nExecStart=oops', 'ssh-rsa abc monet-boot-benchmark'):
            with self.assertRaises(ValueError):bench.credentials(key)
