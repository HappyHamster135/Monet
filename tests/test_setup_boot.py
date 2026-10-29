"""The ISO packaging gate must reject unsigned or inconsistent boot payloads."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name != 'nt' and shutil.which('cmp'), 'Linux ISO build tools')
class BootPackaging(unittest.TestCase):
    def test_missing_signer_and_mismatched_usb_payload_fail_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            iso = folder / 'setup.iso'
            iso.touch()
            tool = folder / 'tool'
            tool.write_text('''#!/usr/bin/env python3
import os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
if name == 'xorriso':
    if '-pvd_info' in sys.argv:
        print("Volume id: Monet-test")
    else:
        work = Path(sys.argv[-1]).parent
        for name in ['BOOTX64.EFI','grubx64.efi','mmx64.efi','grub.cfg']:
            (work/'efi'/name).write_text('CDLABEL=Monet-test' if name=='grub.cfg' else name)
        (work/'vmlinuz').touch()
        for name in ['eltorito_efi.img','gpt_efi.img']: (work/'boot'/name).touch()
elif name == 'sbverify':
    if os.environ.get('BROKEN') == 'unsigned':
        print('No signature table present')
    else:
        print('CN=Microsoft UEFI CA 2023' if sys.argv[-1].endswith('BOOTX64.EFI') else 'OU=Fedora Secure Boot CA')
elif name == 'mtype':
    name = sys.argv[-1].split('/')[-1]
    value = 'CDLABEL=Monet-test' if name=='grub.cfg' else name
    if os.environ.get('BROKEN') == 'usb-copy' and name=='mmx64.efi': value='wrong MokManager'
    sys.stdout.write(value)
''')
            tool.chmod(0o755)
            for name in ['xorriso','sbverify','mtype']: (folder/name).symlink_to(tool)
            for broken in ['', 'unsigned', 'usb-copy']:
                with self.subTest(broken=broken):
                    env = dict(os.environ, PATH=str(folder)+os.pathsep+os.environ['PATH'], BROKEN=broken)
                    result = subprocess.run(['bash', str(ROOT/'image/setup/check-boot.sh'), str(iso), 'Monet-test'],
                                            env=env, capture_output=True, text=True, timeout=15)
                    if broken: self.assertNotEqual(result.returncode, 0, result.stdout)
                    else: self.assertEqual(result.returncode, 0, result.stderr)
