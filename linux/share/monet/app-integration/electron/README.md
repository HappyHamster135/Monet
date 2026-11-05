# Monet app logins for Electron

This local integration lets an **app developer** add Monet's native account picker
and save prompt. It works without an accessibility tree, including in a Flatpak
with permission to contact the broker. Users do not install an extension or set
up a separate vault. It does not retrofit autofill into unmodified third-party
apps. The package is not published to npm; it follows the repository's GPL-3.0-or-later
license. Other clients can implement the documented D-Bus interface independently.

The user first enables **Settings → Passwords → Save and fill app logins**.
The service stays off by default. An absent, disabled, locked or busy service
returns a status; the app's normal sign-in must keep working.

## Main-process use

Vendor this directory with your application, run `npm ci --ignore-scripts
--omit=optional` there at build time, and bundle the locked runtime dependencies.
The source is also shipped at `/usr/share/monet/app-integration/electron` in the
OS image; copy it into your app's build tree before installing dependencies.
The connection must originate in the real Electron main process: launching a
helper process would give that helper a different authenticated app identity.

```js
// Trusted main-process code, after constructing your login BrowserWindow.
const {createIntegration} = require('./vendor/monet-app-logins');

const monet = createIntegration({
  allowedDocuments: ['https://accounts.example.com']
});

// Attach this to an explicit native menu/button action owned by the main process.
// loginWindow is your own BrowserWindow, never an ID supplied by a web page.
async function fillFromMonet() {
  const result = await monet.fill(loginWindow.webContents, {
    username: '#email',
    password: '#password',
    service: '#server' // Omit this selector if the form has no server field.
  });
  // result contains only status. Do not automatically submit the form.
  showNativeStatus(result.status);
}

// Optional: after your existing trusted authentication code reports success.
// Keep this asynchronous; consent must not block the normal sign-in flow.
async function offerSuccessfulLogin(username, password, server) {
  return monet.offer(loginWindow.webContents, {
    username, password, service: server || '', kind: 'login'
  });
}
```

Use `contextIsolation: true`, `sandbox: true`, and `nodeIntegration: false` in
the window's web preferences. Keep the integration and its selectors in trusted
main-process code. Do not expose it through `contextBridge`, arbitrary renderer
IPC, a remote debugging port or a global keyboard shortcut. A renderer must not
choose a WebContents, allowed document, selector, app identity or vault key.
Application authors remain responsible for their renderer/navigation security.

`fill` supports one visible standard HTML form in the main document, with one
username input and one empty `type="password" autocomplete="current-password"`
input. Optional server and read-only username controls are supported. It does
not support custom password widgets, shadow DOM, iframes, registration or password
change autofill. `offer` accepts `login`, `register` or `change` after the app's
own successful operation. Limits: username 320, password 4,096 and service 200
characters. Do not pass credentials through command lines or log them.

## Document and consent boundaries

HTTPS scopes use their origin; local `file:` pages use their exact path.
`app:`, `tauri:`, `capacitor:` and `ionic:` URLs use their host. HTTP is accepted
only on loopback. URL credentials, opaque documents and remote HTTP are rejected.
Use explicit origins/files in `allowedDocuments`; queries/fragments are not saved.
Accounts remain separate for each authenticated executable/package or Flatpak ID
and document scope. Changing installation path or app packaging can change identity.

The broker authenticates the D-Bus caller with kernel process information. For
these document methods it trusts that app's main process to supply its document;
it cannot independently inspect an inaccessible page. An app cannot assert a
different app identity. Do not treat document scopes as isolation between mutually
untrusted pages sharing a compromised main process.

Filling always opens Monet's native chooser. Credentials are sent only after the
user opens saved logins and explicitly chooses **Fill selected account**. Before
writing, the integration checks the full live URL, original input nodes, their
values/attributes, form action/method and submit controls. Navigation, replaced
fields, typed passwords, changed accounts/servers and expired requests cancel
filling. Both values are set in an isolated world before dispatching input/change
events. Sign in remains the user's action. No clipboard or global typing is used.
The filled application necessarily receives the chosen password; JavaScript cannot
guarantee memory zeroization. The helper returns only a status to its caller.

The transport uses D-Bus `NO_AUTO_START`, bounds waiting to 105 seconds and closes
the connection after each call. Navigation or a lost main-process connection
cancels pending fill consent. Do not continuously retry declined/failed requests.

## Flatpak packaging

Bundle the client and its dependencies into the app. Add the one named session
bus permission to the app manifest's `finish-args`:

```yaml
- --talk-name=org.monet.PasswordOffers1
```

No unrestricted session bus, host filesystem, command execution or accessibility
permission is needed for this integration. Monet's **Review app support** control
does not grant this permission; the app must ship the integration itself.

For accessibility-based save detection, **Review app support** can separately set
`ACCESSIBILITY_ENABLED=1` for a selected installed Flatpak. This addresses Chromium's
native accessibility startup gate; it does not add the missing EditableText setter
to Chromium. The setting is reversible, and the app must be reopened manually.

## Local validation

`tests/test_electron_integration.py` exercises a real Electron 43.8.7 main process,
private D-Bus broker, native Monet consent and dummy vault, with accessibility
disabled. The same fixture runs as an actually installed Flatpak with only the
named broker permission. Eleven scenarios cover fill, read-only usernames, typed
passwords, navigation and mutations during consent. See
[`docs/PASSWORDS.md`](../../../../../docs/PASSWORDS.md) for broker methods and limits.
