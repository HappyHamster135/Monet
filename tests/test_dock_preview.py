"""A stale local plugin must never prevent the regular desktop from starting."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]

class DockPreview(unittest.TestCase):
    def test_valid_preview_and_mismatch_fallback_both_start_plasma(self):
        spec=importlib.util.spec_from_file_location('dock_preview',ROOT/'image/dock/preview.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            here=Path(directory);module.__file__=str(here/'preview.py')
            (here/'runtime.json').write_text(json.dumps({'files':{'fixture.so':'verified'}}))
            bundle=types.SimpleNamespace(PLUGIN='fixture.so',verify=lambda _:None,digest=lambda _:'verified')
            with patch.dict(sys.modules,{'bundle':bundle}),patch.dict(os.environ,{},clear=True),patch.object(module.os,'execv') as execute:
                module.main()
                self.assertEqual(os.environ['QT_PLUGIN_PATH'],str(here/'plugins'))
                execute.assert_called_with('/usr/bin/plasmashell',['plasmashell','--no-respawn'])
            def mismatch(_):raise ValueError('Different runtime')
            bundle.verify=mismatch
            with patch.dict(sys.modules,{'bundle':bundle}),patch.dict(os.environ,{},clear=True),patch.object(module.os,'execv') as execute:
                module.main();self.assertNotIn('QT_PLUGIN_PATH',os.environ)
                execute.assert_called_once()

if __name__=='__main__':unittest.main()
