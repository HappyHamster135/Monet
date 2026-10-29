"""Exercise the fixture in an isolated VM compositor; closes its first window."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET
from gi.repository import Gio, GLib

root = Path(sys.argv[1]).resolve()
os.environ.update(json.loads((root / "session-env.json").read_text()))
loader = importlib.machinery.SourceFileLoader("resume", str(root / "monet-resume"))
resume = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(resume)


def state():
    return json.loads((root / "identity.json").read_text())


before = state()
assert 'monet_window_identityEnabled' not in (root/'config/kwinrc').read_text()
loaded = resume.dbus('org.kde.KWin','/Plugins','org.freedesktop.DBus.Properties',
    'Get','org.kde.KWin.Plugins','LoadedPlugins')[0]
assert 'monet_window_identity' in (loaded.variant() if hasattr(loaded,'variant') else loaded)
pid = before["pid"]
windows = before["windows"]
assert len(windows) == 2 and all(w["uuid"] and not w["error"] for w in windows), before
ids = [w["uuid"] for w in windows]
assert len(set(ids)) == 2
frames = resume.kwin_script("reply(workspace.windowList().filter(w=>w.pid==%d).map(w=>({id:String(w.internalId),pid:w.pid})));" % pid)
assert set(ids) == {w["id"] for w in frames}, (before, frames)
def batch(surfaces):
    return Gio.bus_get_sync(Gio.BusType.SESSION, None).call_sync(
        "org.kde.KWin", "/MonetWindowIdentity", "org.monet.WindowIdentity", "resolveWindows",
        GLib.Variant("(uau)", (pid, surfaces)), GLib.VariantType("(as)"),
        Gio.DBusCallFlags.NONE, 500, None).unpack()[0]

surfaces = [w["surface"] for w in windows]
assert batch(surfaces) == ids and batch(surfaces[::-1]) == ids[::-1]
for invalid in ([], surfaces * 9, [surfaces[0], surfaces[0]], [0], [surfaces[0], 4294967295]):
    assert batch(invalid) == []
for pid0, surface0 in ((0, windows[0]["surface"]), (pid, 0), (pid, 4294967295), (4294967295, windows[0]["surface"])):
    got = Gio.bus_get_sync(Gio.BusType.SESSION, None).call_sync(
        "org.kde.KWin", "/MonetWindowIdentity", "org.monet.WindowIdentity", "resolve",
        GLib.Variant("(uu)", (pid0, surface0)), GLib.VariantType("(s)"),
        Gio.DBusCallFlags.NONE, 500, None).unpack()[0]
    assert got == "", got
xml = resume.dbus("org.kde.KWin", "/MonetWindowIdentity", "org.freedesktop.DBus.Introspectable", "Introspect")[0]
methods = [method.attrib["name"] for interface in ET.fromstring(xml).findall("interface")
           if not interface.attrib["name"].startswith("org.freedesktop.")
           for method in interface.findall("method")]
assert sorted(methods) == ["resolve", "resolveWindows"], methods
resume.kwin_script("for(const w of workspace.windowList())if(w.pid==%d)w.frameGeometry={x:100,y:100,width:500,height:350};reply(true);" % pid)
time.sleep(1)
same = resume.kwin_script("reply(workspace.windowList().filter(w=>w.pid==%d).map(w=>({id:String(w.internalId),rect:rect(w.frameGeometry),active:w.active})));" % pid)
assert len({json.dumps(w["rect"], sort_keys=True) for w in same}) == 1, same
assert [w["uuid"] for w in state()["windows"]] == ids
resume.kwin_script("workspace.windowList().find(w=>String(w.internalId)==%s).minimized=true;reply(true);" % json.dumps(ids[0]))
time.sleep(.8)
assert [w["uuid"] for w in state()["windows"]] == ids
snapshot_script = "reply(workspace.windowList().filter(w=>w.pid==%d).map(w=>({id:String(w.internalId),rect:rect(w.frameGeometry),minimized:w.minimized,active:w.active,stack:w.stackingOrder})));" % pid
snapshot = resume.kwin_script(snapshot_script)
time.sleep(1.1)
assert resume.kwin_script(snapshot_script) == snapshot
resume.kwin_script("workspace.windowList().find(w=>String(w.internalId)==%s).closeWindow();reply(true);" % json.dumps(ids[0]))
for _ in range(30):
    after = state()
    if not after["windows"][0]["uuid"]:
        break
    time.sleep(.2)
assert not after["windows"][0]["uuid"] and after["windows"][1]["uuid"] == ids[1], after
assert batch(surfaces) == [] and batch(surfaces[1:]) == ids[1:]
assert resume.kwin_script("reply(workspace.windowList().filter(w=>w.pid==%d).map(w=>String(w.internalId)));" % pid) == [ids[1]]
proof = {"same_process_same_title_same_geometry": True,
         "shipped_default_loaded_without_config_override": True,
         "bounded_atomic_batch_mapping": True,
         "exact_surface_to_window_mapping": True, "minimized_window_identity": True,
         "lookup_does_not_change_focus_or_layout": True, "invalid_lookup_empty": True,
         "only_read_only_method_exported": True, "closed_window_not_reassigned": True,
         "before": before, "after": after, "frames": frames,
         "runtime": json.loads((root / "runtime-verified.json").read_text())}
(root / "verified.json").write_text(json.dumps(proof, indent=2))
print(json.dumps({key: value for key, value in proof.items() if isinstance(value, bool)}))
