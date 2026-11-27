"""Load the real desktop widget in an isolated Plasma host."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('plasmawindowed'), 'requires Plasma widget host')
class DesktopGpuPolicy(unittest.TestCase):
    def test_laptop_gpu_is_not_subscribed_until_explicitly_enabled(self):
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            package = stage/'data/plasma/plasmoids/org.monet.system'
            shutil.copytree(ROOT/'linux/share/plasma/plasmoids/org.monet.system', package)
            ui = package/'contents/ui'
            for source in (ROOT/'linux/share/monet/widgets').iterdir():
                if source.is_file(): shutil.copy2(source, ui/source.name)
            helper = stage/'monet-graphics-use'
            helper.write_text('#!/bin/sh\nprintf \'%s\\n\' \'{"version":1,"sleepingDevices":["gpu1"]}\'\n')
            helper.chmod(0o755)
            policy = ui/'GraphicsPolicy.qml'
            policy.write_text(policy.read_text().replace('@LIBEXECDIR@', str(stage)))
            main = ui/'main.qml'
            code = main.read_text()
            start = code.index('    id: root')
            code = code[:start] + '''
    property int fixtureStep: 0
    Timer {
        interval: 400; repeat: true; running: root.fixtureStep < 3
        onTriggered: {
            if (!gpuPolicy.ready || !root.dashboardSampling) { console.log("MONET_GPU_WAIT", gpuPolicy.ready, root.dashboardSampling); return }
            console.log("MONET_GPU_PROBE " + JSON.stringify({step:root.fixtureStep,
                cpu:cpu.item !== null, intel:gpu0.item !== null, nvidia:gpu1.item !== null,
                formatted:typeof memoryUsed.formattedValue === "string"}))
            if (root.fixtureStep === 0) gpuPolicy.monitorDedicatedGraphics = true
            else if (root.fixtureStep === 1) gpuPolicy.monitorDedicatedGraphics = false
            root.fixtureStep++
        }
    }
''' + code[start:]
            main.write_text(code)
            env = dict(os.environ, XDG_DATA_HOME=str(stage/'data'), QT_QPA_PLATFORM='offscreen',
                       QT_QUICK_BACKEND='software', QT_FORCE_STDERR_LOGGING='1', QT_LOGGING_RULES='qml.debug=true')
            process = subprocess.Popen(['plasmawindowed', 'org.monet.system'], env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                _, errors = process.communicate(timeout=4)
            except subprocess.TimeoutExpired:
                process.terminate()
                try: _, errors = process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill(); _, errors = process.communicate()
            lines = [json.loads(line.split('MONET_GPU_PROBE ', 1)[1]) for line in errors.splitlines()
                     if 'MONET_GPU_PROBE ' in line]
            self.assertEqual(lines, [dict(step=0, cpu=True, intel=True, nvidia=False, formatted=True),
                                    dict(step=1, cpu=True, intel=True, nvidia=True, formatted=True),
                                    dict(step=2, cpu=True, intel=True, nvidia=False, formatted=True)], errors)
            for error in ('Binding loop', 'TypeError:', 'ReferenceError:', 'Cannot override', 'is not a type', 'Unable to assign'):
                self.assertNotIn(error, errors)
