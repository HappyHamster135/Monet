"""The real native consent dialog defaults to declining; synthetic metadata only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(os.environ.get('MONET_PASSWORDS_QT_TESTS')=='1','native Qt consent fixture')
class BrowserConsent(unittest.TestCase):
    def run_dialog(self,kind,accept):
        program='''
import io,json,sys
sys.path.insert(0,sys.argv[1])
from PySide6.QtCore import QTimer,Qt
from PySide6.QtWidgets import QDialog,QDialogButtonBox,QLabel
from PySide6.QtTest import QTest
import browser_prompt
original=QDialog.exec
checks=[]
def execute(dialog):
 def interact():
  buttons=dialog.findChild(QDialogButtonBox)
  checks.append(buttons.button(QDialogButtonBox.Cancel).isDefault())
  checks.append(not buttons.button(QDialogButtonBox.Save).isDefault())
  checks.append(any('example.invalid' in label.text() for label in dialog.findChildren(QLabel)))
  if sys.argv[3]=='accept':QTest.mouseClick(buttons.button(QDialogButtonBox.Save),Qt.LeftButton)
  else:QTest.keyClick(dialog,Qt.Key_Return)
 QTimer.singleShot(20,interact)
 return original(dialog)
QDialog.exec=execute
sys.stdin=io.TextIOWrapper(io.BytesIO(json.dumps({'kind':sys.argv[2],'site':'https://example.invalid','username':'Test account'}).encode()))
result=browser_prompt.main()
assert checks and all(checks)
sys.exit(result)
'''
        result=subprocess.run([sys.executable,'-c',program,str(ROOT/'linux/share/monet/passwords'),kind,'accept' if accept else 'cancel'],
            env=dict(os.environ,QT_QPA_PLATFORM='offscreen'),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)
    def test_enter_never_silently_saves_or_updates(self):
        for kind in ('save','update'):
            self.assertFalse(self.run_dialog(kind,False)['approved'])
    def test_explicit_save_and_update_buttons_approve(self):
        for kind in ('save','update'):
            self.assertTrue(self.run_dialog(kind,True)['approved'])
