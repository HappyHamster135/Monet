"""Real Plasma widgets consume native activity events, without host services."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get('MONET_ACTIVITY_FIXTURE') and shutil.which('plasmawindowed'),
                     'native activity fixture and Plasma host')
class WidgetActivity(unittest.TestCase):
    def run_widget(self, name):
        subprocess.run([sys.executable, str(ROOT / 'tests/fixtures/widget-activity.py'), name], check=True, timeout=40)

    def test_batteries(self): self.run_widget('batteries')
    def test_quick(self): self.run_widget('quick')
    def test_system(self): self.run_widget('system')
    def test_network(self): self.run_widget('network')
    def test_storage(self): self.run_widget('storage')
    def test_played(self): self.run_widget('played')
    def test_frame(self): self.run_widget('frame')
    def test_clock(self): self.run_widget('clock')
    def test_calendar(self): self.run_widget('calendar')
    def test_placard(self): self.run_widget('placard')
    def test_sound(self): self.run_widget('sound')
    def test_stacks(self): self.run_widget('stacks')
    def test_transfers(self): self.run_widget('transfers')
    def test_worldclock(self): self.run_widget('worldclock')
    def test_weather(self): self.run_widget('weather')

    def test_user_writes_finish_while_inactive(self):
        subprocess.run([sys.executable, str(ROOT / 'tests/fixtures/activity-stores.py')], check=True, timeout=25)

    def test_wallpaper_keeps_static_image_and_pauses_network_and_animation(self):
        subprocess.run([sys.executable, str(ROOT / 'tests/fixtures/activity-wallpaper.py')], check=True, timeout=30)
