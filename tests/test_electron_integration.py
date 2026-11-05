"""Real main-process D-Bus calls, native Monet consent, isolated-world fill."""
import importlib.util
import os
from pathlib import Path
import select
import subprocess
import time
import unittest
from unittest.mock import patch

from tests import test_app_login_bus as bus_fixture

ROOT = bus_fixture.ROOT


@unittest.skipUnless(os.environ.get('MONET_ELECTRON_BINARY') and os.environ.get('MONET_TEST_ELECTRON_DBUS'),
                     'explicit Electron integration runtime')
class ElectronIntegration(unittest.TestCase):
    setUp=bus_fixture.AppLoginBus.setUp
    tearDown=bus_fixture.AppLoginBus.tearDown
    launch=bus_fixture.AppLoginBus.launch
    wait=bus_fixture.AppLoginBus.wait
    service=bus_fixture.AppLoginBus.service
    busy=bus_fixture.AppLoginBus.busy

    def cases(self, sandboxed):
        old=os.environ.get('APP_LOGIN_FIXTURE_FILL_DELAY')
        os.environ['APP_LOGIN_FIXTURE_FILL_DELAY']='900'
        try:self.service('save')
        finally:
            if old is None:os.environ.pop('APP_LOGIN_FIXTURE_FILL_DELAY',None)
            else:os.environ['APP_LOGIN_FIXTURE_FILL_DELAY']=old
        reader,writer=os.pipe()
        display=self.launch(['Xvfb','-displayfd',str(writer),'-screen','0','1280x800x24','-nolisten','tcp'],pass_fds=(writer,))
        os.close(writer)
        self.assertTrue(select.select([reader],[],[],5)[0]);number=os.read(reader,100).decode().strip();os.close(reader)
        sdk=ROOT/'linux/share/monet/app-integration/electron'
        env=dict(os.environ,DISPLAY=':'+number,MONET_ELECTRON_CLIENT=str(sdk),ACCESSIBILITY_ENABLED='0')
        modes=('fill','readonly','typed','changed-page','changed-action','changed-field','changed-name','changed-type','typed-during','changed-user','changed-service')
        for mode in modes:
            with self.subTest(mode=mode,sandboxed=sandboxed):
                args=[os.environ['MONET_ELECTRON_BINARY'],'--no-sandbox','--disable-gpu','--disable-dev-shm-usage',str(ROOT/'tests/fixtures/electron-login/bridge.cjs'),'--fixture='+mode]
                fixture=None
                if sandboxed:
                    spec=importlib.util.spec_from_file_location('sandbox_fixture',ROOT/'tests/fixtures/flatpak-fixture.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
                    # Flatpak needs the fixture's private display while constructing its sandbox.
                    with patch.dict(os.environ,env):
                        fixture,args=mod.command(args[0],args[1:],(Path(args[0]).parent,sdk,ROOT/'tests/fixtures/electron-login',Path(env['MONET_TEST_ELECTRON_DBUS']).parent),talk=('org.monet.PasswordOffers1',))
                try:
                    result=subprocess.run(args,env=env,capture_output=True,text=True,timeout=25)
                    self.assertEqual(result.returncode,0,result.stderr[-1500:])
                    self.assertNotIn('synthetic-app-only',result.stdout+result.stderr)
                finally:
                    if fixture:fixture.cleanup()
                self.wait(lambda:not self.busy())

    def test_real_electron_native_picker_and_form_boundaries(self):self.cases(False)


@unittest.skipUnless(os.environ.get('MONET_FLATPAK_INTEGRATION')=='1','explicit isolated Flatpak runtime')
class FlatpakElectronIntegration(ElectronIntegration):
    def test_real_electron_native_picker_and_form_boundaries(self):self.cases(True)
