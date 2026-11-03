"""CLI previews keep Settings, Games, widgets and desktop shortcuts together."""
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]


def load(name,path):
    loader=importlib.machinery.SourceFileLoader(name,str(path))
    module=importlib.util.module_from_spec(importlib.util.spec_from_loader(name,loader))
    loader.exec_module(module)
    return module


class SwitchPreview(unittest.TestCase):
    def test_remembered_cli_routes_every_surface_and_includes_restore_helpers(self):
        p=load('switch_preview',ROOT/'tools/install-desktop-preview.py')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            p.DATA=root/'data';p.STATE=root/'state';p.HELPERS=root/'helpers';p.PRIVATE=root/'private';p.CONFIG=root/'config'
            prefix=root/'cli'
            marker=p.STATE/'monet/desktop-preview/cli-prefix'
            marker.parent.mkdir(parents=True);marker.write_text(str(prefix)+'\n')
            desktop=p.DATA/'applications/monet-windows.desktop'
            desktop.parent.mkdir(parents=True)
            desktop.write_text('[Desktop Entry]\nName=My Windows\nIcon=custom\nExec=/usr/bin/monet windows --confirm\n')
            with patch.object(p,'cli_prefix',return_value=prefix):
                plan=p.plan()
            self.assertIn(f'Exec={prefix}/bin/monet windows --confirm',plan[desktop][0].decode())
            self.assertIn('Name=My Windows',plan[desktop][0].decode())
            for helper in ('monet-quick','monet-games'):
                self.assertIn(f'BINDIR = "{prefix}/bin"',plan[p.HELPERS/helper][0].decode())
            self.assertIn(f'DATADIR = "{p.PRIVATE}"',plan[p.HELPERS/'monet-games'][0].decode())
            self.assertEqual(plan[p.PRIVATE/'monet/games'][0],p.DATA/'monet/games')
            self.assertIn(f'Exec={p.HELPERS}/monet-session', plan[p.CONFIG/'autostart/monet-session.desktop'][0].decode())
            session = plan[p.HELPERS/'monet-session'][0].decode()
            self.assertIn(f'"{p.HELPERS}/monet-quick" trip-apps-again', session)
            self.assertIn('"$LIBEXECDIR/monet-profile"', session)  # image-owned helpers stay installed
            self.assertIn(f'Exec={p.HELPERS}/monet-settings passwords', plan[p.DATA/'applications/monet-passwords.desktop'][0].decode())
            played=p.DATA/'plasma/plasmoids/org.monet.played/contents/ui/main.qml'
            self.assertIn(f'{prefix}/bin/monet',plan[played][0].decode())
            for name in ('monet-quick','monet-resume','monet-files-session','monet-editor-session','monet-browser-session','monet-pdf-session'):
                path=p.HELPERS/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(plan[path][0])
            q=load('complete_preview_quick',p.HELPERS/'monet-quick');r=q.resume_helper()
            for helper in (r.files_helper,r.editor_helper,r.browser_helper,r.pdf_helper):
                self.assertTrue(Path(helper().__file__).is_file())
            self.assertEqual(desktop.read_text().splitlines()[-1],'Exec=/usr/bin/monet windows --confirm')

    def test_missing_or_user_writable_cli_is_rejected_before_planning(self):
        p=load('switch_preview_validation',ROOT/'tools/install-desktop-preview.py')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaises(FileNotFoundError): p.cli_prefix(root/'missing')
            for name in ('bin/monet','libexec/monet-leave','libexec/monet-quick'):
                path=root/name;path.parent.mkdir(exist_ok=True);path.write_text('#!/bin/sh\n');path.chmod(0o777)
            with self.assertRaises(ValueError): p.cli_prefix(root)
