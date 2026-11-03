"""Reversible per-account registration for Zen's supported native messaging proxy."""
import configparser
import datetime
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

EXTENSION = 'keepassxc-browser@keepassxc.org'
MONET_EXTENSION = '{d6b46926-af45-4fa5-b746-bd36f68af460}'
HOST = 'org.keepassxc.keepassxc_browser'
ADDON_PAGE = 'https://addons.mozilla.org/firefox/addon/keepassxc-browser/'
BEGIN = '// Monet Passwords browser connection — begin'
END = '// Monet Passwords browser connection — end'


def configured_user_js(text):
    if BEGIN in text:
        if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(END) < text.index(BEGIN):
            raise ValueError('The existing Monet browser preference block needs review.')
        a,b=text.split(BEGIN,1); _,c=b.split(END,1); text=a.rstrip()+c
    return text.rstrip() + '\n\n' + BEGIN + '\nuser_pref("widget.use-xdg-desktop-portal.native-messaging-proxy", 1);\n' + END + '\n'


def plan(host, home=Path.home()):
    host = Path(host).resolve(strict=True)
    if not host.is_file() or not os.access(host, os.X_OK):
        raise ValueError('Install the Monet browser helper first.')
    manifest=home/'.mozilla/native-messaging-hosts'/f'{HOST}.json'
    if manifest.exists():
        current=json.loads(manifest.read_text())
        if current.get('path') != str(host):
            raise ValueError('Another password manager already owns this browser connector. Disconnect it before connecting Monet.')
    files={manifest:json.dumps({'name':HOST,'description':'Monet Passwords — Zen browser connection',
                 'path':str(host),'type':'stdio','allowed_extensions':[EXTENSION,MONET_EXTENSION]},indent=2)+'\n'}
    root=home/'.var/app/app.zen_browser.zen/.zen'
    config=configparser.ConfigParser();config.read(root/'profiles.ini')
    sections=[s for s in config if s.startswith('Profile') and config[s].get('Default')=='1']
    if len(sections)!=1:
        raise ValueError('Open your default Zen profile once, then connect it from Monet Passwords.')
    row=config[sections[0]]
    if row.get('IsRelative')!='1':raise ValueError('This Zen profile location needs manual setup.')
    profile=(root/row['Path']).resolve(strict=True)
    if not profile.is_relative_to(root.resolve()) or profile==root.resolve():raise ValueError('Invalid Zen profile location.')
    prefs=profile/'user.js'
    text=prefs.read_text() if prefs.exists() else ''
    if len(text)>1024*1024:raise ValueError('The Zen preference file is too large to update safely.')
    files[prefs]=configured_user_js(text)
    return files


def apply(host, home=Path.home()):
    if importlib.util.find_spec('nacl') is None:
        raise ValueError('The browser connector is not installed completely. Update Monet and try again.')
    files=plan(host,home)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    backup=home/'.local/state/monet/password-browser'/stamp
    backup.mkdir(parents=True,mode=0o700,exist_ok=False)
    override=home/'.local/share/flatpak/overrides/app.zen_browser.zen'
    receipt=[]
    for index,path in enumerate([*files,override]):
        if path.exists():
            shutil.copy2(path,backup/str(index));(backup/str(index)).chmod(0o600)
        receipt.append({'path':str(path),'backup':str(index) if path.exists() else None})
    (backup/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');(backup/'receipt.json').chmod(0o600)
    try:
        for path,text in files.items():
            path.parent.mkdir(parents=True,exist_ok=True)
            descriptor,temporary=tempfile.mkstemp(prefix='.monet-browser-',dir=path.parent)
            temp=Path(temporary)
            try:
                with os.fdopen(descriptor,'w') as stream:stream.write(text)
                temp.replace(path)
            finally:temp.unlink(missing_ok=True)
        subprocess.run(['flatpak','override','--user','--talk-name=org.freedesktop.NativeMessagingProxy',
                        'app.zen_browser.zen'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
    except Exception:
        for row in reversed(receipt):
            path=Path(row['path'])
            if row['backup'] is not None:shutil.copy2(backup/row['backup'],path)
            elif path.exists():path.unlink()
        raise ValueError('Zen could not be connected. The previous configuration was restored.') from None
    return backup


def main(host):
    from PySide6.QtWidgets import QApplication,QMessageBox
    from app import tr
    app=QApplication([]);app.setStyle('Fusion')
    try:
        apply(host)
        connector = Path(__file__).with_name('connector.xpi')
        command = (['flatpak','run','--file-forwarding','app.zen_browser.zen','@@u',connector.as_uri(),'@@']
                   if connector.is_file() else ['flatpak','run','app.zen_browser.zen',ADDON_PAGE])
        subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        message = (tr('Install the signed Monet Passwords connector in Zen. Open the connector and choose Connect, then approve Monet’s connection prompt. Enable single-account autofill in the connector’s settings if you want fields filled automatically.')
                   if connector.is_file() else tr('Install the signed KeePassXC-Browser connector in Zen, then restart Zen. Open the connector and choose Connect; approve the connection in Monet Passwords. Enable single-account autofill in the connector’s settings if you want fields filled automatically.'))
        QMessageBox.information(None,tr('Connect Zen'),message)
        return 0
    except Exception as exc:
        # Our setup errors contain configuration instructions only, never credentials.
        QMessageBox.warning(None,tr('Zen setup could not finish'),tr(str(exc)) if isinstance(exc,ValueError) else tr('Zen setup failed. Your saved logins were not changed.'))
        return 1
