#!/usr/bin/env python3
"""VM-only disposable Zen fixture. Never use this debugging profile for real accounts.

Run setup once, then install, popup, page, inspect or verify. Pairing and access
approval are performed in the actual UI; this helper never grants vault access.
"""
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import urllib.request

PROFILE = Path.home() / ".var/app/app.zen_browser.zen/.zen/monet-passwords-preview-test"
FIXTURES = Path.home() / "monet-passwords-build/fixtures"
EXTENSION = "keepassxc-browser@keepassxc.org"
XPI = "https://addons.mozilla.org/firefox/downloads/file/5078406/keepassxc_browser-1.10.4.1.xpi"
XPI_SHA256 = "ae41157a3f017b0773abba2097d5b0056241631d0a38ad36d68d0b24b1a409c1"
SITE = "http://127.0.0.1:8765/"


class TestSite(BaseHTTPRequestHandler):
    """Serve only fixture pages; never expose the vault directory or log form contents."""
    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path == "/submitted":
            content = '<h1>Form received locally</h1><p>The test server discarded the form contents.</p><a href="/">Sign in again</a>'
        elif self.path in ("/same-frame", "/cross-frame", "/trusted-frame"):
            source = {"/same-frame": "/", "/cross-frame": "http://localhost:8765/",
                      "/trusted-frame": "http://127.0.0.1:8765/"}[self.path]
            content = f'<h1>Frame boundary test</h1><iframe title="Test sign-in" src="{source}" style="width:95%;height:500px"></iframe>'
        elif self.path == "/multi-user":
            content = '''<h1>Sign in: first step</h1><form onsubmit="event.preventDefault();location.href='/multi-password'">
<label>Username <input name="username" autocomplete="username"></label><button>Next</button></form>'''
        elif self.path == "/multi-password":
            content = '''<h1>Sign in: second step</h1><form method="post" action="/submitted">
<label>Password <input name="password" type="password" autocomplete="current-password"></label><button>Continue</button></form>'''
        elif self.path in ("/", "/signup", "/change"):
            title = {"/": "A local sign-in test", "/signup": "Create a test account", "/change": "Change a test password"}[self.path]
            autocomplete = "current-password" if self.path == "/" else "new-password"
            content = f'''<h1>{title}</h1><p>Made-up credentials only. Submitted to this local test server and discarded.</p>
<form method="post" action="/submitted"><label>Username <input name="username" autocomplete="username"></label>
<label>Password <input name="password" type="password" autocomplete="{autocomplete}"></label><button>Continue</button></form>'''
        else:
            self.send_error(404)
            return
        page = ('''<!doctype html><html lang="en"><meta charset="utf-8"><title>Monet Passwords test</title>
<style>body{font:20px sans-serif;padding:60px;background:#eee8df;color:#292c2c}label{display:block;margin:20px 0}input,button{font:inherit;padding:12px}</style>''' + content + '</html>').encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(page)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if self.path != "/submitted" or not 0 <= length <= 4096:
            self.send_error(400)
            return
        self.rfile.read(length)
        self.send_response(303)
        self.send_header("Location", "/submitted")
        self.send_header("Content-Length", "0")
        self.end_headers()


class Browser:
    def __init__(self):
        self.sock = socket.create_connection(("127.0.0.1", 2871), timeout=30)
        self.ident = 0
        self.read()
        self.call("WebDriver:NewSession", {"capabilities": {}})
        self.call("Marionette:SetContext", {"value": "chrome"})

    def read(self):
        prefix = b""
        while not prefix.endswith(b":"):
            part = self.sock.recv(1)
            if not part:
                raise EOFError()
            prefix += part
        length = int(prefix[:-1])
        data = b""
        while len(data) < length:
            part = self.sock.recv(length - len(data))
            if not part:
                raise EOFError()
            data += part
        return json.loads(data)

    def call(self, command, args=None):
        self.ident += 1
        payload = json.dumps([0, self.ident, command, args or {}]).encode()
        self.sock.sendall(str(len(payload)).encode() + b":" + payload)
        result = self.read()
        if result[2]:
            raise RuntimeError(result[2])
        return result[3]

    def js(self, script):
        return self.call("WebDriver:ExecuteScript", {"script": script, "args": [], "newSandbox": True})["value"]

    def close(self):
        self.call("WebDriver:DeleteSession")
        self.sock.close()


def setup():
    if not Path("/usr/libexec/xdg-native-messaging-proxy").is_file():
        raise SystemExit("This fixture requires the system native-messaging proxy.")
    PROFILE.mkdir(exist_ok=False)
    FIXTURES.mkdir(exist_ok=True)
    prefs = {
        "zen.welcome-screen.seen": True,
        "browser.shell.checkDefaultBrowser": False,
        "browser.startup.homepage_override.mstone": "ignore",
        "browser.startup.page": 0,
        "browser.warnOnQuitShortcut": False,
        "datareporting.policy.dataSubmissionPolicyBypassNotification": True,
        "widget.use-xdg-desktop-portal.native-messaging-proxy": 1,
        "marionette.port": 2871,
    }
    (PROFILE / "user.js").write_text("\n".join(f"user_pref({json.dumps(k)}, {json.dumps(v)});" for k, v in prefs.items()))
    xpi = urllib.request.urlopen(XPI, timeout=30).read()
    if hashlib.sha256(xpi).hexdigest() != XPI_SHA256:
        raise SystemExit("Extension checksum mismatch")
    (PROFILE / "keepassxc.xpi").write_bytes(xpi)
    env = dict(os.environ, DBUS_SESSION_BUS_ADDRESS=f"unix:path=/run/user/{os.getuid()}/bus",
               XDG_RUNTIME_DIR=f"/run/user/{os.getuid()}", WAYLAND_DISPLAY="wayland-0", MOZ_ENABLE_WAYLAND="1")
    with (FIXTURES / "browser.log").open("w") as log:
        subprocess.Popen(["flatpak", "run", "--talk-name=org.freedesktop.NativeMessagingProxy",
                          "app.zen_browser.zen", "--new-instance", "--profile", str(PROFILE),
                          "--marionette", "--remote-allow-system-access", SITE],
                         env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    with (FIXTURES / "web.log").open("w") as log:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "serve"], stdin=subprocess.DEVNULL,
                         stdout=log, stderr=log, start_new_session=True)
    print("Disposable browser starting; native-messaging permission applies to this launch only.")


def run(mode):
    browser = Browser()
    try:
        if mode == "install":
            print(browser.call("Addon:Install", {"path": str(PROFILE / "keepassxc.xpi"), "temporary": False}))
        elif mode == "popup":
            print(browser.js('''const {ExtensionParent} = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
const ext = ExtensionParent.GlobalManager.getExtension("keepassxc-browser@keepassxc.org");
let w = Services.wm.getMostRecentWindow("navigator:browser");
w.openTrustedLinkIn(ext.baseURI.resolve("popups/popup.html"), "tab"); return true;'''))
        elif mode in ("page", "other-site", "signup", "change", "same-frame", "cross-frame", "trusted-frame", "multi-user"):
            browser.call("Marionette:SetContext", {"value": "content"})
            url = {"page": SITE, "other-site": "http://localhost:8765/",
                   "trusted-frame": "http://localhost:8765/trusted-frame"}.get(mode, SITE + mode)
            browser.call("WebDriver:Navigate", {"url": url})
        elif mode == "inspect":
            browser.call("Marionette:SetContext", {"value": "content"})
            print(browser.js("return {url:location.href,text:document.body.innerText};"))
        elif mode == "empty":
            browser.call("Marionette:SetContext", {"value": "content"})
            result = browser.js('''return {site:location.href,
username:document.querySelector('[name=username]')?.value === '',
password:document.querySelector('[name=password]')?.value === ''};''')
            assert result["site"] in (SITE, "http://localhost:8765/"), result
            assert result["username"] and result["password"], result
            print("PASS: both fixture fields are empty.")
        elif mode == "verify":
            browser.call("Marionette:SetContext", {"value": "content"})
            result = browser.js('''return {site:location.href,
username:document.querySelector('[name=username]').value === 'monet-demo',
password:document.querySelector('[name=password]').value === 'Monet-demo-only-1028!'};''')
            assert result == {"site": SITE, "username": True, "password": True}, result
            print("PASS: real extension filled both fixture fields on the local page.")
    finally:
        browser.close()


if __name__ == "__main__":
    if sys.argv[1] == "setup":
        setup()
    elif sys.argv[1] == "serve":
        HTTPServer(("127.0.0.1", 8765), TestSite).serve_forever()
    else:
        run(sys.argv[1])
