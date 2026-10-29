"""Run only inside the isolated VM compositor created for the identity proof."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from gi.repository import Gio, GLib

root = Path(sys.argv[1]).resolve()
os.environ.update(json.loads((root / "session-env.json").read_text()))
loader = importlib.machinery.SourceFileLoader("resume", str(root / "monet-resume"))
resume = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(resume)
output = root / "collision.json"
assert not output.exists() and not Path(str(output) + ".close-first").exists()
process = subprocess.Popen([str(root / "build/collision_fixture"), str(output)],
                           stdout=(root / "collision.log").open("w"), stderr=subprocess.STDOUT)


def wait_for(predicate):
    for _ in range(50):
        assert process.poll() is None, (root / "collision.log").read_text()
        if output.exists():
            result = json.loads(output.read_text())
            if predicate(result):
                return result
        time.sleep(.2)
    raise AssertionError("Collision fixture timed out")


try:
    before = wait_for(lambda state: True)
    assert before["surface"] > 0 and not before["uuid"] and not before["error"], before
    ids = resume.kwin_script("reply(workspace.windowList().filter(w=>w.pid==%d).map(w=>String(w.internalId)));" % process.pid)
    assert len(ids) == 2 and len(set(ids)) == 2, ids
    def batch():
        return Gio.bus_get_sync(Gio.BusType.SESSION, None).call_sync(
            "org.kde.KWin", "/MonetWindowIdentity", "org.monet.WindowIdentity", "resolveWindows",
            GLib.Variant("(uau)", (process.pid, [before["surface"]])), GLib.VariantType("(as)"),
            Gio.DBusCallFlags.NONE, 500, None).unpack()[0]
    assert batch() == []
    Path(str(output) + ".close-first").touch()
    after = wait_for(lambda state: state["firstClosed"] and bool(state["uuid"]))
    assert not after["error"] and after["uuid"] in ids and after["surface"] == before["surface"], after
    remaining = resume.kwin_script("reply(workspace.windowList().filter(w=>w.pid==%d).map(w=>String(w.internalId)));" % process.pid)
    assert remaining == [after["uuid"]], remaining
    assert batch() == remaining
    proof = {"same_process_surface_collision_rejected": True,
             "remaining_connection_resolves_exactly": True, "before": before, "after": after, "ids": ids}
    (root / "collision-verified.json").write_text(json.dumps(proof, indent=2))
    print(json.dumps({key: value for key, value in proof.items() if isinstance(value, bool)}))
finally:
    process.terminate()
    process.wait(timeout=10)
