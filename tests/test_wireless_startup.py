"""Wireless boot work uses current state, private D-Bus and disposable image roots."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.test_boot_graphics import boot

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'linux/libexec/monet-input-connect'
loader = importlib.machinery.SourceFileLoader('input_connect', str(HELPER))
inputs = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(inputs)


class InputEligibility(unittest.TestCase):
    def objects(self, **properties):
        device = dict(Paired=True, Trusted=True, Blocked=False, Connected=False, Icon='input-mouse',
                      Adapter='/adapter', UUIDs=[next(iter(inputs.INPUT_UUIDS))])
        device.update(properties)
        return {'/adapter': {inputs.ADAPTER: dict(Powered=True)},
                '/mouse': {inputs.DEVICE: device}}

    def test_paired_trusted_classic_and_le_inputs_are_eligible(self):
        for uuid in inputs.INPUT_UUIDS:
            for icon in ('input-mouse','input-keyboard'):
                self.assertEqual(list(inputs.eligible(self.objects(UUIDs=[uuid.upper()],Icon=icon))), ['/mouse'])

    def test_unknown_connected_blocked_and_audio_devices_are_not_attempted(self):
        for props in (dict(Paired=False), dict(Trusted=False), dict(Blocked=True),
                      dict(Connected=True), dict(UUIDs=[]), dict(Icon='input-gaming'),
                      dict(UUIDs=['0000110b-0000-1000-8000-00805f9b34fb'])):
            with self.subTest(props=props):
                self.assertEqual(list(inputs.eligible(self.objects(**props))), [])
        for key in ('Paired', 'Trusted', 'Blocked', 'Connected', 'Adapter', 'UUIDs', 'Icon'):
            objects = self.objects(); objects['/mouse'][inputs.DEVICE].pop(key)
            self.assertEqual(list(inputs.eligible(objects)), [], key)

    def test_adapter_state_is_required_and_radios_are_never_enabled(self):
        objects = self.objects()
        for state in (False, None):
            objects['/adapter'][inputs.ADAPTER]['Powered'] = state
            self.assertEqual(list(inputs.eligible(objects)), [])
        objects.pop('/adapter')
        self.assertEqual(list(inputs.eligible(objects)), [])


class WifiMigration(unittest.TestCase):
    SCRIPT = """#!/bin/bash
systemctl unmask wpa_supplicant.service
if [ -f /etc/NetworkManager/conf.d/99-valve-wifi-backend.conf ]; then
  rm -f /etc/NetworkManager/conf.d/99-valve-wifi-backend.conf
fi
if [ -f /etc/NetworkManager/conf.d/iwd.conf ]; then
  rm -f /etc/NetworkManager/conf.d/iwd.conf
fi
"""
    UNIT = """[Unit]
Before=NetworkManager.service
[Service]
Type=oneshot
ExecStart=/usr/libexec/bazzite-iwd-migration
ExecStartPost=/usr/bin/touch /var/lib/bazzite-iwd-migration.done
"""

    def fixture(self, root):
        script = root / 'usr/libexec/bazzite-iwd-migration'
        unit = root / 'usr/lib/systemd/system/bazzite-iwd-migration.service'
        script.parent.mkdir(parents=True); unit.parent.mkdir(parents=True)
        script.write_text(self.SCRIPT); unit.write_text(self.UNIT)
        boot.prepare_wifi(root)
        return script, unit

    def needed(self, root):
        condition = boot.WIFI_NEEDED.replace('/var/lib/', str(root)+'/var/lib/').replace('/etc/', str(root)+'/etc/').replace('/run/',str(root)+'/run/')
        result = subprocess.run(['/bin/sh', '-c', condition], capture_output=True, timeout=5)
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return result.returncode == 0

    def test_first_run_and_new_cleanup_still_precede_networkmanager(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); script,unit=self.fixture(root)
            self.assertTrue(self.needed(root))
            receipt=root/'var/lib/bazzite-iwd-migration.done'
            receipt.parent.mkdir(parents=True); receipt.touch()
            self.assertFalse(self.needed(root))
            for name in ('99-valve-wifi-backend.conf','iwd.conf'):
                legacy=root/'etc/NetworkManager/conf.d'/name
                legacy.parent.mkdir(parents=True,exist_ok=True); legacy.touch()
                self.assertTrue(self.needed(root)); legacy.unlink()
            mask=root/'etc/systemd/system/wpa_supplicant.service'
            mask.parent.mkdir(parents=True); mask.symlink_to('/dev/null')
            self.assertTrue(self.needed(root)); mask.unlink()
            mask.touch(); self.assertTrue(self.needed(root))
            mask.write_text('[Service]\nExecStart=/bin/true\n')
            self.assertFalse(self.needed(root))
            runtime=root/'run/systemd/system/wpa_supplicant.service'
            runtime.parent.mkdir(parents=True); runtime.symlink_to('/dev/null')
            self.assertTrue(self.needed(root)); runtime.unlink()
            self.assertEqual(script.read_text(),self.SCRIPT)
            self.assertEqual(unit.read_text(),self.UNIT)

    def test_image_guard_is_idempotent_and_changed_migrations_need_review(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); script,unit=self.fixture(root)
            dropin=unit.with_name(unit.name+'.d')/'50-monet-fast-start.conf'
            before=dropin.read_bytes(); boot.prepare_wifi(root)
            self.assertEqual(dropin.read_bytes(),before)
            script.write_text(self.SCRIPT+'\necho different-behavior\n')
            with self.assertRaises(ValueError):boot.prepare_wifi(root)
            self.assertEqual(dropin.read_bytes(),before)

    @unittest.skipUnless(shutil.which('systemd-analyze'), 'requires native systemd verification')
    def test_native_systemd_accepts_the_migration_and_nonblocking_input_service(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); script,unit=self.fixture(root)
            service=root/'usr/lib/systemd/system/monet-input-connect.service'
            service.write_text((ROOT/'linux/systemd/monet-input-connect.service').read_text()
                               .replace('@LIBEXECDIR@/monet-input-connect','/bin/true'))
            for name in ('bluetooth.service','NetworkManager.service'):
                unit.with_name(name).write_text('[Service]\nType=exec\nExecStart=/bin/true\n')
            # Neither radio activation nor a peripheral connection gates login.
            self.assertNotIn('Before=',service.read_text())
            unit.write_text(unit.read_text().replace('/usr/libexec/bazzite-iwd-migration','/bin/true'))
            result=subprocess.run(['systemd-analyze','--man=no','verify',str(unit),str(service)],
                env=dict(os.environ,SYSTEMD_UNIT_PATH=str(unit.parent)+':/usr/lib/systemd/system'),
                capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)


@unittest.skipUnless(sys.platform=='linux' and importlib.util.find_spec('gi')
                     and shutil.which('dbus-daemon'), 'requires native Gio and a private bus')
class NativeInputReconnect(unittest.TestCase):
    def run_case(self, scenario, inspect=False):
        from tools.test import private_session, stop
        with private_session() as env:
            env['DBUS_SYSTEM_BUS_ADDRESS']=env['DBUS_SESSION_BUS_ADDRESS']
            events=Path(env['HOME'])/'events.jsonl'
            server=subprocess.Popen([sys.executable,str(ROOT/'tests/fixtures/bluez-input-service.py'),
                str(events),scenario],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            try:
                self.assertTrue(select.select([server.stdout],[],[],5)[0], 'Private BlueZ did not start')
                self.assertEqual(server.stdout.readline(),b'READY\n')
                command=[sys.executable,str(HELPER),*(['--inspect'] if inspect else [])]
                if scenario=='traffic':
                    # Instrument the client in a separate process on the private
                    # bus, without adding production logging or testing switches.
                    calls=Path(env['HOME'])/'reconcile.txt'
                    runner=("import runpy; from pathlib import Path; "
                        f"m=runpy.run_path({str(HELPER)!r}); c=m['Reconnect']; f=c.reconcile; "
                        f"p=Path({str(calls)!r}); "
                        "exec('def traced(self):\\n with p.open(\"a\") as s: s.write(\"tick\\\\n\")\\n return f(self)'); "
                        "c.reconcile=traced; m['main']()")
                    command=[sys.executable,'-c',runner]
                result=subprocess.run(command,
                    env=env,capture_output=True,text=True,timeout=8)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                # PyGObject prints callback errors without changing the exit code.
                self.assertNotIn('Traceback',result.stderr)
                if scenario=='disconnect':
                    # The client can finish before the subsequent user action.
                    server.wait(timeout=5)
                if scenario=='traffic':
                    self.assertLessEqual(len(calls.read_text().splitlines()),3)
                records=[json.loads(line) for line in events.read_text().splitlines()]
                self.assertEqual(sum(r['event']=='GetManagedObjects' for r in records),1)
                return records,result.stdout
            finally:
                stop(server)
                self.assertNotIn('Traceback',server.stderr.read().decode())
                server.stdout.close();server.stderr.close()

    def test_existing_inputs_connect_once_without_scanning_or_pairing(self):
        records,_=self.run_case('ready')
        self.assertEqual([r['event'] for r in records],['GetManagedObjects','Connect'])

    def test_power_and_object_events_trigger_prompt_connection(self):
        for scenario,event in (('power-on','powered'),('added','added')):
            with self.subTest(scenario=scenario):
                records,_=self.run_case(scenario)
                times={r['event']:r['time'] for r in records}
                self.assertEqual(sum(r['event']=='Connect' for r in records),1)
                self.assertGreaterEqual(times['Connect'],times[event])
                self.assertLess(times['Connect']-times[event],1)

    def test_user_disconnect_and_untrusted_devices_are_respected(self):
        for scenario in ('disconnect','untrusted'):
            with self.subTest(scenario=scenario):
                records,_=self.run_case(scenario)
                self.assertNotIn('Connect',[r['event'] for r in records])
                if scenario=='disconnect':
                    self.assertIn('user-disconnect',[r['event'] for r in records])

    def test_existing_bluez_attempt_is_not_retried(self):
        records,_=self.run_case('in-progress')
        self.assertEqual(sum(r['event']=='Connect' for r in records),1)

    def test_inspection_is_read_only(self):
        records,output=self.run_case('ready',inspect=True)
        self.assertNotIn('Connect',[r['event'] for r in records])
        self.assertEqual(json.loads(output),dict(known_inputs=1,connected_inputs=0,eligible_inputs=1))

    def test_hid_data_and_signal_strength_do_not_trigger_reconciliation(self):
        records,_=self.run_case('traffic')
        self.assertEqual(sum(r['event']=='Connect' for r in records),1)

    def test_link_connected_signal_does_not_end_pending_profile_setup(self):
        records,_=self.run_case('deferred-reply')
        self.assertEqual([r['event'] for r in records],
                         ['GetManagedObjects','Connect','connected-reply'])
