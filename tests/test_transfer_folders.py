"""Completion folder actions use the file manager, never a downloaded file."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from tests.test_files_tools import files_tools


class CompatibilityFolders(unittest.TestCase):
    def invoke(self, request):
        tool=files_tools();output=io.StringIO()
        with patch.object(sys,'argv',[str(tool.__file__),'--open-folder',json.dumps(request).encode().hex()]),redirect_stdout(output):
            result=tool.main()
        return result,json.loads(output.getvalue())
    def test_local_file_is_selected_and_directory_is_opened_with_literal_arguments(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);file=folder/'Downloaded $(touch NO) # å.desktop';file.write_text('never execute')
            with patch('subprocess.Popen') as start:
                code,result=self.invoke(dict(url=file.as_uri(),directory=False));self.assertEqual(code,0);self.assertTrue(result['ok'])
                self.assertEqual(start.call_args.args[0],['dolphin','--select',file.as_uri()])
                code,result=self.invoke(dict(url=folder.as_uri(),directory=True));self.assertEqual(code,0)
                self.assertEqual(start.call_args.args[0],['dolphin',folder.as_uri()])
    def test_changed_folder_and_nonfilesystem_uris_never_launch_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            file=Path(temporary)/'replaced';file.touch()
            with patch('subprocess.Popen') as start:
                for request in [dict(url=file.as_uri(),directory=True),dict(url='javascript:alert(1)'),dict(url='https://example.com/download'),dict(url='applications:app.desktop')]:
                    code,result=self.invoke(request);self.assertEqual(code,1);self.assertFalse(result['ok'])
                start.assert_not_called()


@unittest.skipUnless(os.environ.get('MONET_LAUNCHER_FIXTURE'),'native launcher test image')
class NativeFolders(unittest.TestCase):
    def test_real_kio_folder_resolution_filemanager_dispatch_and_cancellation(self):
        root=Path(os.environ['MONET_LAUNCHER_FIXTURE']).parent
        subprocess.run(['sh',str(root/'run.sh'),str(root/'folder-test')],check=True,timeout=100)
    def test_completed_real_operations_open_the_right_folder_after_reopening_transfers(self):
        root=Path(__file__).resolve().parents[1]
        subprocess.run([sys.executable,str(root/'tests/fixtures/transfers-completion.py')],check=True,timeout=75)
