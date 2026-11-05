"""Reversible per-account registration for Zen's supported native messaging proxy."""
import configparser
import datetime
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from connector import VERSION as CONNECTOR_VERSION, newer_than, verified_bytes

EXTENSION = 'keepassxc-browser@keepassxc.org'
MONET_EXTENSION = '{d6b46926-af45-4fa5-b746-bd36f68af460}'
HOST = 'org.keepassxc.keepassxc_browser'
BEGIN = '// Monet Passwords browser connection — begin'
END = '// Monet Passwords browser connection — end'


def N_(text):
    return text


STATUS_ERROR = N_('Zen configuration could not be checked. Open Zen and try again.')


def read_metadata(path, limit=2 * 1024 * 1024):
    """Bounded configuration reads; never open browser login/key databases."""
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Zen configuration is too large to check safely.')
    return data.decode('utf-8')


def default_profile(home):
    root = home / '.var/app/app.zen_browser.zen/.zen'
    config = configparser.ConfigParser()
    if (root / 'profiles.ini').exists():
        config.read_string(read_metadata(root / 'profiles.ini', 65536))
    sections = [s for s in config if s.startswith('Profile') and config[s].get('Default') == '1']
    if len(sections) != 1:
        raise ValueError('Open your default Zen profile once, then connect it from Monet Passwords.')
    row = config[sections[0]]
    if row.get('IsRelative') != '1':
        raise ValueError('This Zen profile location needs manual setup.')
    profile = (root / row.get('Path', '')).resolve()
    if not profile.is_relative_to(root.resolve()) or profile == root.resolve():
        raise ValueError('Invalid Zen profile location.')
    if not profile.is_dir():
        raise ValueError('Open your default Zen profile once, then connect it from Monet Passwords.')
    return profile


def inspect(host, home=Path.home(), connector=None):
    """Installation metadata only. A saved pairing is not proof of a live connection."""
    connector = connector or Path(__file__).with_name('connector.xpi')
    result = dict(profile=False, configured=False, addon='missing', popup='', options='',
                  bundled=False, bundle_problem='', bundled_version='', installed_version='',
                  update_available=False, problem='')
    try:
        verified_bytes(connector)
        result.update(bundled=True, bundled_version=CONNECTOR_VERSION)
    except FileNotFoundError:
        pass
    except (OSError, ValueError):
        result['bundle_problem'] = N_('The browser connector is not installed completely. Update Monet and try again.')
    try:
        profile = default_profile(home)
        result['profile'] = True
        registry = profile / 'extensions.json'
        addons = json.loads(read_metadata(registry, 8 * 1024 * 1024)).get('addons', []) if registry.exists() else []
        addon = next((a for a in addons if a.get('id') == MONET_EXTENSION), None)
        if addon:
            result['addon'] = ('active' if addon.get('active') is True and not addon.get('userDisabled')
                               and not addon.get('appDisabled') and addon.get('signedState', 0) >= 2
                               else 'disabled')
            version = addon.get('version', '')
            result['installed_version'] = version if isinstance(version, str) else ''
            result['update_available'] = bool(result['bundled'] and newer_than(version))
        prefs = profile / 'prefs.js'
        if result['addon'] == 'active' and prefs.exists():
            # Read just the known extension's UUID, not its storage or credentials.
            match = re.search(r'^user_pref\("extensions\.webextensions\.uuids", ("(?:[^"\\]|\\.)*")\);$',
                              read_metadata(prefs), re.MULTILINE)
            mapping = json.loads(json.loads(match[1])) if match else {}
            uuid = mapping.get(MONET_EXTENSION, '')
            if isinstance(uuid, str) and re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', uuid):
                result['popup'] = f'moz-extension://{uuid}/popups/popup.html'
                result['options'] = f'moz-extension://{uuid}/options/options.html'
        files = plan(host, home)
        manifest = home / '.mozilla/native-messaging-hosts' / f'{HOST}.json'
        current = json.loads(read_metadata(manifest)) if manifest.exists() else {}
        prefs_path = profile / 'user.js'
        override = home / '.local/share/flatpak/overrides/app.zen_browser.zen'
        permissions = configparser.ConfigParser()
        if override.exists(): permissions.read_string(read_metadata(override))
        result['configured'] = (current.get('path') == str(Path(host).resolve())
            and MONET_EXTENSION in current.get('allowed_extensions', [])
            and prefs_path.exists() and read_metadata(prefs_path) == files[prefs_path]
            and permissions.get('Session Bus Policy', 'org.freedesktop.NativeMessagingProxy', fallback='') == 'talk')
    except ValueError as exc:
        result['problem'] = str(exc) if type(exc) is ValueError else STATUS_ERROR
    except (OSError, KeyError, TypeError, AttributeError, configparser.Error):
        result['problem'] = STATUS_ERROR
    return result


def browser_command(state, action, connector=None):
    """Only fixed browser pages or the shipped connector may be opened."""
    # An existing Zen window may be minimized. A dedicated setup window is
    # brought forward by Zen and does not replace an in-progress login tab.
    prefix = ['flatpak', 'run', 'app.zen_browser.zen', '--new-window']
    if action == 'open': return prefix
    if action == 'manage': return prefix + ['about:addons']
    if action in ('popup', 'options'):
        url = state.get(action, '')
        suffix = 'popups/popup.html' if action == 'popup' else 'options/options.html'
        if re.fullmatch(r'moz-extension://[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}/' + re.escape(suffix), url):
            return prefix + [url]
        return prefix + ['about:addons']
    if action == 'install':
        connector = connector or Path(__file__).with_name('connector.xpi')
        if not connector.is_file():
            raise ValueError('The signed Monet connector is missing from this installation. Update Monet and try again.')
        verified_bytes(connector)
        return ['flatpak', 'run', '--file-forwarding', 'app.zen_browser.zen', '--new-window', '@@u', connector.resolve().as_uri(), '@@']
    raise ValueError('This browser action is not available.')


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
        current=json.loads(read_metadata(manifest))
        if current.get('path') != str(host):
            raise ValueError('Another password manager already owns this browser connector. Disconnect it before connecting Monet.')
    files={manifest:json.dumps({'name':HOST,'description':'Monet Passwords — Zen browser connection',
                 'path':str(host),'type':'stdio','allowed_extensions':[EXTENSION,MONET_EXTENSION]},indent=2)+'\n'}
    profile = default_profile(home)
    prefs=profile/'user.js'
    text=read_metadata(prefs, 1024 * 1024) if prefs.exists() else ''
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
