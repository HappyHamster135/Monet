"""The greeter borrows only the last internal brightness, never a display layout."""
import importlib.machinery
import importlib.util
import unittest
import os
import tempfile
import configparser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('login_brightness',str(ROOT/'linux/libexec/monet-login-brightness'))
b = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name,loader));loader.exec_module(b)


class LoginBrightness(unittest.TestCase):
    def test_greeter_power_does_not_add_new_idle_or_profile_brightness_resets(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'powerdevilrc'
            path.write_text('[AC][Performance]\nPowerProfile=balanced\n')
            b.greeter_power(path,os.getuid(),os.getgid())
            parser=configparser.ConfigParser();parser.read(path)
            self.assertEqual(parser['AC][Performance']['PowerProfile'],'balanced')
            for profile in ['AC','Battery','LowBattery']:
                self.assertEqual(parser[profile+'][Display']['UseProfileSpecificDisplayBrightness'],'false')
                self.assertEqual(parser[profile+'][Display']['TurnOffDisplayWhenIdle'],'false')
                self.assertEqual(parser[profile+'][SuspendAndShutdown']['AutoSuspendAction'],'0')
            self.assertEqual(path.stat().st_mode & 0o777,0o600)

    def test_internal_identity_and_last_level_preserve_login_and_external_settings(self):
        profile=[dict(name='outputs',data=[dict(connectorName='eDP-1',edidHash='panel',brightness=.2,scale=2,highDynamicRange=True),dict(connectorName='DP-1',edidHash='monitor',brightness=.8)])]
        screen=dict(connectorName='eDP-2',edidHash='panel',brightness=1,scale=1.5,highDynamicRange=False)
        monitor=dict(connectorName='DP-1',edidHash='monitor',brightness=.7)
        saved=[dict(name='outputs',data=[screen,monitor]),dict(name='setups',data=['keep'])]
        self.assertTrue(b.seed(profile,saved,.2))
        self.assertEqual(screen,dict(connectorName='eDP-2',edidHash='panel',brightness=.2,scale=1.5,highDynamicRange=False))
        self.assertEqual(monitor['brightness'],.7)
        self.assertEqual(saved[1]['data'],['keep'])
        self.assertFalse(b.seed(profile,saved,.2))

    def test_first_greeter_config_contains_only_display_identity_and_brightness(self):
        saved=[]
        profile=[dict(name='outputs',data=[dict(connectorName='eDP-1',edidHash='panel',uuid='id',brightness=.3,scale=2,mode={'unexpected':True})])]
        self.assertTrue(b.seed(profile,saved,.3))
        self.assertEqual(saved,[dict(name='outputs',data=[dict(connectorName='eDP-1',edidHash='panel',uuid='id',brightness=.3)])])
        for value in [True,None,-1,2,float('nan'),float('inf')]:
            self.assertFalse(b.seed(profile,saved,value))
