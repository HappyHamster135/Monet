"""CLI previews keep Settings, Games, widgets and desktop shortcuts together."""
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest
import contextlib
import io
import json
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]


def load(name,path):
    loader=importlib.machinery.SourceFileLoader(name,str(path))
    module=importlib.util.module_from_spec(importlib.util.spec_from_loader(name,loader))
    loader.exec_module(module)
    return module


class SwitchPreview(unittest.TestCase):
    def test_release_guard_uses_monet_version_not_fedora_version_id(self):
        p=load('release_guard',ROOT/'tools/install-desktop-preview.py')
        with tempfile.TemporaryDirectory() as tmp:
            release=Path(tmp)/'os-release'
            release.write_text('NAME="Monet"\nVERSION="0.9.6"\nVERSION_ID=45\n')
            self.assertTrue(p.running_monet_version('0.9.6',release))
            self.assertFalse(p.running_monet_version('0.9.5',release))
            release.write_text('NAME="Bazzite"\nVERSION="0.9.6"\nVERSION_ID=45\n')
            self.assertFalse(p.running_monet_version('0.9.6',release))

    def test_empty_package_roots_are_removed_and_restoration_recreates_them(self):
        p=load('retire_package_roots',ROOT/'tools/install-desktop-preview.py')
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as out:
            root=Path(tmp);p.DATA=root/'data';p.STATE=root/'state';p.CONFIG=root/'config';p.HELPERS=root/'helpers'
            shell=p.DATA/'plasma/shells/org.kde.plasma.desktop'
            metadata=shell/'metadata.json';main=shell/'contents/views/Desktop.qml'
            personal=p.DATA/'plasma/plasmoids/personal/metadata.json'
            p.apply({metadata:(b'metadata',0o644),main:(b'QML',0o644),personal:(b'initial',0o644)})
            personal.write_text('personal changes')
            p.retire(True, launchers_only=True)
            self.assertTrue(shell.exists())
            out.truncate(0);out.seek(0);p.retire(True)
            result=json.loads(out.getvalue())
            self.assertFalse(shell.exists())  # Empty roots still shadow packaged Plasma.
            self.assertEqual(personal.read_text(),'personal changes')
            p.restore(Path(result['receipt']))
            self.assertEqual(metadata.read_bytes(),b'metadata')
            self.assertEqual(main.read_bytes(),b'QML')
            # Repair an interrupted older retirement with no remaining file changes.
            metadata.unlink();main.unlink()
            p.retire(True)
            self.assertFalse(shell.exists())

    def test_retirement_unwinds_layers_keeps_edits_and_is_reversible(self):
        p=load('retire_preview', ROOT/'tools/install-desktop-preview.py')
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as out:
            root=Path(tmp)
            p.DATA=root/'data';p.STATE=root/'state';p.HELPERS=root/'helpers';p.PRIVATE=root/'private';p.CONFIG=root/'config'
            original=p.DATA/'applications/personal.desktop'; original.parent.mkdir(parents=True)
            original.write_bytes(b'personal before preview')
            added=p.DATA/'applications/new.desktop'
            edited=p.CONFIG/'personal'; edited.parent.mkdir(parents=True)
            p.apply({original:(b'first',0o644), added:(b'new',0o644), edited:(b'initial',0o644)})
            p.apply({original:(b'second',0o644), added:(b'newest',0o644)})
            edited.write_text('my later edit')
            changes,kept=p.retirement_plan()
            self.assertEqual(set(changes),{original,added});self.assertEqual(kept,[str(edited)])
            self.assertEqual(original.read_bytes(),b'second')  # planning has no side effects
            out.truncate(0);out.seek(0);p.retire(True)
            result=json.loads(out.getvalue())
            self.assertEqual(original.read_bytes(),b'personal before preview')
            self.assertFalse(added.exists());self.assertEqual(edited.read_text(),'my later edit')
            self.assertEqual(p.retirement_plan()[0],{})
            p.restore(Path(result['receipt']))
            self.assertEqual(original.read_bytes(),b'second');self.assertEqual(added.read_bytes(),b'newest')
            self.assertEqual(edited.read_text(),'my later edit')
            # Retire entry points now, keeping code the live shell still uses.
            payload=p.HELPERS/'quick'
            p.apply({payload:(b'live helper',0o755)})
            p.retire(True, launchers_only=True)
            self.assertFalse(added.exists())
            self.assertEqual(payload.read_bytes(),b'live helper')
            p.retire(True)
            self.assertFalse(payload.exists())
            self.assertEqual(edited.read_text(),'my later edit')

    def test_retirement_rejects_damaged_backups_before_changing_anything(self):
        p=load('retire_damaged_preview', ROOT/'tools/install-desktop-preview.py')
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);p.DATA=root/'data';p.STATE=root/'state';p.CONFIG=root/'config';p.HELPERS=root/'helpers'
            target=p.DATA/'file';target.parent.mkdir();target.write_text('before')
            p.apply({target:(b'preview',0o644)})
            receipt=next((p.STATE/'monet/desktop-preview').glob('*/receipt.json'))
            (receipt.parent/'0').write_text('damaged')
            with self.assertRaises(ValueError):p.retire(True)
            self.assertEqual(target.read_text(),'preview')

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
            self.assertIn(f'Exec={p.HELPERS}/monet-passwords', plan[p.DATA/'applications/monet-passwords.desktop'][0].decode())
            self.assertIn(f'DATADIR = \'{p.PRIVATE}\'', plan[p.HELPERS/'monet-passwords'][0].decode())
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
