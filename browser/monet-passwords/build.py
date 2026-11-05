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
    manifest['version']='1.10.4.3' if preview else '0.1.1'
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
    replace('background/client.js', "    keepass.databaseHash = '';", "    keepass.databaseHash = '';\n    keepass.monetNativeConsent = false;\n    monetSubmissions.clearFlow();")
    replace('background/client.js', 'keepassClient.onNativeMessage = function(response) {', '''keepassClient.onNativeMessage = function(response) {
    if (response.action === kpActions.DATABASE_LOCKED) monetSubmissions.clearFlow();''')
    replace('background/keepass.js', 'const [ entryId, username, password, url, group, groupUuid ] = args;', 'const [ entryId, username, password, url, group, groupUuid, monetAutomatic = false ] = args;')
    replace('background/keepass.js', '        if (entryId) {', '        if (monetAutomatic && keepass.monetNativeConsent) messageData.monetAutomatic = true;\n\n        if (entryId) {')
    replace('background/keepass.js', '            let successMessage = response.error;', '            if (monetAutomatic) return {prompted: response.monetPrompted === true, saved: response.error === "success"};\n            let successMessage = response.error;')
    replace('background/event.js', "    'get_connected_database': kpxcEvent.onGetConnectedDatabase,", "    'get_connected_database': kpxcEvent.onGetConnectedDatabase,\n    'monet_native_consent': () => keepass.monetNativeConsent === true,")
    replace('background/event.js', 'kpxcEvent.onMessage = async function(request, sender) {', '''kpxcEvent.onMessage = async function(request, sender) {
    if (request.action === 'monet_username_step' || request.action === 'monet_get_username_step') {
        // Only the actual top-level content script may carry account context.
        if (!keepass.monetNativeConsent || sender.frameId !== 0 || !sender.tab
            || !monetSubmissions.flowOrigin(sender.tab, sender.url)) return '';
        const args = request.args || [];
        return request.action === 'monet_username_step'
            ? monetSubmissions.rememberUsername(sender.tab, args[0], sender.url)
            : monetSubmissions.username(sender.tab, sender.url);
    }''')
    replace('background/tabs.js', 'tabs.onRemoved = async function(tabId, _removeInfo) {', '''tabs.onRemoved = async function(tabId, _removeInfo) {
    monetSubmissions.clearFlow(tabId);''')
    replace('background/tabs.js', '    if (changeInfo.url) {', '''    if (changeInfo.url) {
        monetSubmissions.username(tab, changeInfo.url); // Clears context when the origin changes.''')
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
    replace('content/form.js', "    let passwordValue = '';", '''    let passwordValue = '';
    if (usernameValue && !passwordField && !passwordInputs?.length) {
        await sendMessage('monet_username_step', [usernameValue]);
    }''')
    replace('content/form.js', '        return usernameField.value || usernameField.placeholder;', '        return usernameField.value;')
    replace('content/form.js', 'kpxcForm.getNewPassword = function(passwordInputs = []) {', '''kpxcForm.getNewPassword = function(passwordInputs = []) {
    const fresh = passwordInputs.filter(p => kpxcFields.hasAutocomplete(p, 'new-password'));
    if (fresh.length) return fresh[0].value && fresh.every(p => p.value === fresh[0].value) ? fresh[0].value : '';''')
    replace('content/form.js', '''    // Use the first text field in the form if only username input is missing''', '''    const submitter = e.submitter || (e.type === 'click' ? this : null);
    if (form && !form.noValidate && !submitter?.formNoValidate && !form.checkValidity()) {
        kpxcForm.submitTriggered = false;
        return;
    }

    // Use the first text field in the form if only username input is missing''')
    form_source = files['content/form.js'].decode()
    start = form_source.index('kpxcForm.getUsernameValue = async function(usernameField) {')
    end = form_source.index('// Initializes form and attaches the submit button', start)
    replace('content/form.js', form_source[start:end], '''kpxcForm.getUsernameValue = async function(usernameField) {
    if (usernameField) return usernameField.value;
    // One round trip: submission may navigate away immediately.
    const [usernameStep, pageUuid] = await Promise.all([
        sendMessage('monet_get_username_step'), sendMessage('page_get_login_id')
    ]);
    if (usernameStep) return usernameStep;
    if (kpxc.credentials.length === 1) return kpxc.credentials[0].login;
    return kpxc.credentials.find(c => c.uuid === pageUuid)?.login || '';
};

''')
    replace('content/form.js', '''    // If the form username differs (input has removed etc.) use the username stored in the submitted object''', '''    // A password-change page may omit the account name. A unique current
    // password match identifies it; ambiguous accounts require an explicit choice.
    if (!usernameValue && passwordInputs?.length > 1) {
        const current = passwordInputs.find(p => kpxcFields.hasAutocomplete(p, 'current-password'));
        const matches = current?.value ? kpxc.credentials.filter(c => c.password === current.value) : [];
        if (matches.length === 1) usernameValue = matches[0].login;
        else if (kpxc.credentials.length > 1) {
            kpxcUI.createNotification('warning', tr('monetChooseAccount'));
            kpxcForm.submitTriggered = false;
            return;
        }
    }

    // If the form username differs (input has removed etc.) use the username stored in the submitted object''')
    messages = json.loads(files['_locales/en/messages.json'])
    messages['monetChooseAccount'] = {'message': 'Choose the saved account from the password field’s Monet menu before updating its password.'}
    files['_locales/en/messages.json'] = (json.dumps(messages, ensure_ascii=False, indent=2) + '\n').encode()
    replace('content/fields.js', 'const kpxcFields = {};', '''const kpxcFields = {};
// Upstream's field menus set autocomplete="off". Keep the semantic hints in
// a page-local WeakMap so old passwords never fill a new-password field.
kpxcFields.monetAutocomplete = new WeakMap();
kpxcFields.hasAutocomplete = function(field, token) {
    if (!field) return false;
    const current = (field.autocomplete || '').toLowerCase();
    if (current !== 'off') kpxcFields.monetAutocomplete.set(field, current);
    return (kpxcFields.monetAutocomplete.get(field) || current).split(/\\s+/).includes(token);
};''')
    replace('content/fields.js', '''        if (input.getLowerCaseAttribute('type') === 'password') {''', '''        kpxcFields.hasAutocomplete(input, ''); // Capture hints before field menus change them.
        if (input.getLowerCaseAttribute('type') === 'password') {''')
    replace('content/fields.js', '''kpxcFields.getExistingCombination = function(combination) {''', '''kpxcFields.getExistingCombination = function(combination) {
    // Password-change fields must not replace the current-password target.
    if (kpxcFields.hasAutocomplete(combination.password, 'new-password')) return combination;''')
    replace('content/keepassxc-browser.js', '''    if (kpxc.settings.autoFillSingleEntry && kpxc.credentials.length === 1) {
        kpxcFill.fillFromAutofill();
        return;
    }''', '''    if (kpxc.settings.autoFillSingleEntry && await kpxcFill.fillFromAutofill()) return;''')
    start = files['content/fill.js'].decode().index('kpxcFill.fillFromAutofill = async function() {')
    end = files['content/fill.js'].decode().index('// Fill requested by selecting credentials from the popup', start)
    replace('content/fill.js', files['content/fill.js'].decode()[start:end], '''kpxcFill.fillFromAutofill = async function() {
    const isNew = field => kpxcFields.hasAutocomplete(field, 'new-password');
    const combination = kpxc.combinations.find(c => kpxcFields.hasAutocomplete(c.password, 'current-password'))
        || kpxc.combinations.find(c => c.password && !isNew(c.password))
        || kpxc.combinations.find(c => c.username && !c.password);
    if (!combination) return false;
    const username = combination.username?.value || await sendMessage('monet_get_username_step');
    const matches = username ? kpxc.credentials.filter(c => c.login === username) : kpxc.credentials;
    if (matches.length !== 1) return false;
    const selected = matches[0];
    await sendMessage('page_set_login_id', selected.uuid);
    await kpxcFill.fillInCredentials(combination, selected.login, selected.uuid);
    sendMessage('popup_login', [{text: `${selected.login} (${selected.name})`, uuid: selected.uuid}]);
    return true;
};

''')
    replace('content/fill.js', '    // Fill password\n', '''    // Never put an old password into a new-password/confirmation field.
    if (kpxcFields.hasAutocomplete(combination.password, 'new-password')) {
        combination = {...combination, password: null};
    }
    // Fill password
''')
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
