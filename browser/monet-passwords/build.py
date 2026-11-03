#!/usr/bin/python3
"""Reproducible local connector candidate. No upload, signing or installation."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

UPSTREAM_SHA256='ae41157a3f017b0773abba2097d5b0056241631d0a38ad36d68d0b24b1a409c1'
UPSTREAM_ID='keepassxc-browser@keepassxc.org'
MONET_ID='{d6b46926-af45-4fa5-b746-bd36f68af460}'
ROOT=Path(__file__).resolve().parents[2]

def build(upstream, output, preview=False, fixture=False):
    if hashlib.sha256(upstream.read_bytes()).hexdigest()!=UPSTREAM_SHA256:raise ValueError('Unexpected upstream connector archive')
    with zipfile.ZipFile(upstream) as z:
        files={n:z.read(n) for n in z.namelist() if not n.endswith('/') and not n.startswith('META-INF/')}
    def replace(path, old, new):
        text=files[path].decode()
        if text.count(old)!=1:raise ValueError('Unsupported upstream hook: '+path)
        files[path]=text.replace(old,new).encode()
    manifest=json.loads(files['manifest.json'])
    manifest['name']='Monet Passwords (local preview)' if preview else 'Monet Passwords'
    manifest['description']='Save and autofill Monet logins. Monet asks before saving or updating a password.'
    manifest['author']='Monet contributors; based on KeePassXC-Browser by the KeePassXC Team'
    manifest['version']='1.10.4.2' if preview else '0.1.0'
    manifest['browser_specific_settings']=manifest.pop('applications',manifest.get('browser_specific_settings',{}))
    manifest['browser_specific_settings']['gecko']['id']=UPSTREAM_ID if preview else MONET_ID
    manifest['browser_specific_settings']['gecko']['strict_min_version']='140.0'
    # Mozilla includes local native messaging in its data-transmission taxonomy.
    manifest['browser_specific_settings']['gecko']['data_collection_permissions']={'required':['authenticationInfo','browsingActivity']}
    manifest['browser_action']['default_title']='Monet Passwords'
    manifest['background']['scripts'].insert(manifest['background']['scripts'].index('background/credentials.js'), 'background/automatic-submit.js')
    files['background/automatic-submit.js']=Path(__file__).with_name('automatic-submit.js').read_bytes()
    files['manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    replace('background/keepass.js', "keepass.currentKeePassXC = '';", "keepass.currentKeePassXC = '';\nkeepass.monetNativeConsent = false;")
    replace('background/keepass.js', "keepass.databaseHash = parsed.hash || '';", "keepass.databaseHash = parsed.hash || '';\n                keepass.monetNativeConsent = parsed.monet?.nativeConsent === true;")
    replace('background/client.js', "    keepass.databaseHash = '';", "    keepass.databaseHash = '';\n    keepass.monetNativeConsent = false;")
    replace('background/keepass.js', 'const [ entryId, username, password, url, group, groupUuid ] = args;', 'const [ entryId, username, password, url, group, groupUuid, monetAutomatic = false ] = args;')
    replace('background/keepass.js', '        if (entryId) {', '        if (monetAutomatic && keepass.monetNativeConsent) messageData.monetAutomatic = true;\n\n        if (entryId) {')
    replace('background/keepass.js', '            let successMessage = response.error;', '            if (monetAutomatic) return {prompted: response.monetPrompted === true, saved: response.error === "success"};\n            let successMessage = response.error;')
    replace('background/event.js', "    'get_connected_database': kpxcEvent.onGetConnectedDatabase,", "    'get_connected_database': kpxcEvent.onGetConnectedDatabase,\n    'monet_native_consent': () => keepass.monetNativeConsent === true,")
    replace('background/credentials.js', 'const credentials = {};', '''const credentials = {};
const monetSubmissions = new MonetSubmissionGate(async (tab, candidate) => {
    if (!keepass.monetNativeConsent) return;
    return await keepass.updateCredentials(tab, [candidate.uuid, candidate.username, candidate.password, candidate.url, null, null, true]);
});''')
    replace('background/credentials.js', '    const [ submitted, username, password, url, oldCredentials ] = args;', '''    if (keepass.monetNativeConsent) {
        await credentials.clearSubmittedCredentials(tab.id);
        try { await monetSubmissions.submit(tab, args); } catch (_) { /* No credential/error logging. */ }
        return;
    }
    const [ submitted, username, password, url, oldCredentials ] = args;''')
    replace('content/banner.js', 'kpxcBanner.create = async function(credentials = {}) {', '''kpxcBanner.create = async function(credentials = {}) {
    // A native Monet dialog is already handling the submission.
    if (await sendMessage('monet_native_consent')) return;''')
    replace('content/keepassxc-browser.js', '        kpxc.settings.showLoginNotifications);', "        kpxc.settings.showLoginNotifications && !await sendMessage('monet_native_consent'));")
    if fixture:
        replace('background/client.js', "'org.keepassxc.keepassxc_browser'", "'org.monet.passwords.fixture'")
    # Preserve upstream attribution; the preview identity is never a signing candidate.
    files['MONET-NOTICE.txt']=('Monet Passwords is derived from KeePassXC-Browser 1.10.4.1.\n'
        'Upstream: https://github.com/keepassxreboot/keepassxc-browser\n'
        'Combined license: GPL-3.0-only. Modified source/build inputs: browser/monet-passwords in Monet.\n'
        + ('LOCAL TEMPORARY PREVIEW ONLY. Do not submit this upstream add-on ID for signing.\n' if preview else '')).encode()
    files['LICENSE']=Path(__file__).with_name('LICENSE.upstream').read_bytes()
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,(2026,11,3,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,data)
    return hashlib.sha256(output.read_bytes()).hexdigest()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('upstream',type=Path);p.add_argument('output',type=Path);p.add_argument('--temporary-preview',action='store_true');p.add_argument('--fixture',action='store_true');a=p.parse_args()
    if a.fixture and not a.temporary_preview:p.error('Fixtures are temporary previews only')
    print(build(a.upstream,a.output,a.temporary_preview,a.fixture))
