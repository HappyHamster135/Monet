"""Check a fresh isolated compositor with the native plugin explicitly disabled."""
import configparser
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
os.environ.update(json.loads((root / "session-env.json").read_text()))
loader = importlib.machinery.SourceFileLoader("resume", str(root / "monet-resume"))
resume = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(resume)

config = configparser.ConfigParser(interpolation=None)
config.read(root / "config/kwinrc")
assert config.getboolean("Plugins", "monet_window_identityEnabled") is False
properties = {}
for name in ("AvailablePlugins", "LoadedPlugins"):
    value = resume.dbus("org.kde.KWin", "/Plugins", "org.freedesktop.DBus.Properties",
                        "Get", "org.kde.KWin.Plugins", name)[0]
    properties[name] = value.variant() if hasattr(value, "variant") else value
assert "monet_window_identity" in properties["AvailablePlugins"], properties
assert "monet_window_identity" not in properties["LoadedPlugins"], properties
state = json.loads((root / "identity.json").read_text())
assert len(state["windows"]) == 2 and all(w["error"] == "org.freedesktop.DBus.Error.UnknownObject" for w in state["windows"]), state
frames = resume.kwin_script("reply(workspace.windowList().filter(w=>w.pid==%d).map(w=>String(w.internalId)));" % state["pid"])
assert len(frames) == 2 and len(set(frames)) == 2, frames
try:
    resume.dbus("org.kde.KWin", "/MonetWindowIdentity", "org.freedesktop.DBus.Introspectable", "Introspect")
except RuntimeError as error:
    assert "UnknownObject" in str(error), str(error)
else:
    raise AssertionError("Disabled plugin exported a D-Bus object")
proof = {"explicit_disabled_preference_preserved": True,
         "installed_plugin_available_but_not_loaded": True,
         "disabled_plugin_exports_no_object": True,
         "windows_remain_open": True, "state": state, "frames": frames,
         "runtime": json.loads((root / "runtime-verified.json").read_text())}
(root / "disabled-verified.json").write_text(json.dumps(proof, indent=2))
print(json.dumps({key: value for key, value in proof.items() if isinstance(value, bool)}))
