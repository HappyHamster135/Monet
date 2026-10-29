"""VM-only check of a patched editor build and the isolated identity compositor.

Argument: build root containing build/bin/libkateprivate, identity/session-env.json
and the current Monet helpers in identity/. Leaves JSON evidence in editor-check/.
"""
import copy
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import uuid

build = Path(sys.argv[1]).resolve()
root = build / "identity"
folder = build / "editor-check"
folder.mkdir()
os.environ.update(json.loads((root / "session-env.json").read_text()))
os.environ.update(XDG_CONFIG_HOME=str(root / "config"), XDG_DATA_HOME=str(folder / "data"),
                  LD_LIBRARY_PATH=str(build / "build/bin"), QT_LINUX_ACCESSIBILITY_ALWAYS_ON="1")
loader = importlib.machinery.SourceFileLoader("resume", str(root / "monet-resume"))
resume = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(resume)
editor = resume.editor_helper()


def capture(pid, count):
    for _ in range(30):
        state = editor.capture(pid, windows=True)
        if state and len(state) == count:
            return state
        time.sleep(.2)
    raise AssertionError("Editor metadata did not settle")


def close(pid, ident=None):
    resume.kwin_script("for(const w of workspace.windowList())if(w.pid==%d%s)w.closeWindow();reply(true);" %
                       (pid, "&&String(w.internalId)==" + json.dumps(ident) if ident else ""))
    for _ in range(30):
        remaining = [w for w in resume.window_snapshot() if w["pid"] == pid and (not ident or w["id"] == ident)]
        if not remaining:
            return
        time.sleep(.2)
    raise AssertionError("Fixture window did not close")


files = [folder / name for name in ("Shared.txt", "Left.txt", "Bottom.txt", "Right.txt")]
for path in files:
    path.write_text("First line for the window fixture.\nSecond line for cursor checks.\n")
files = list(map(str, files))
first = {"views": [{"documents": files[:2], "active": 0, "cursor": 4},
                   {"documents": files[2:3], "active": 0, "cursor": 9}], "active": 0,
         "layout": {"orientation": 1, "sizes": [550, 350], "children": [0, 1]}}
second = {"views": [{"documents": [files[0], files[3]], "active": 0, "cursor": 12}], "active": 0, "layout": 0}
expected = [{"id": "{" + str(uuid.uuid4()) + "}", "editor": state} for state in (first, second)]
receipt = editor.start("org.kde.kate.desktop", expected, windows=True)
pid = receipt["pid"]
actual = capture(pid, 2)
assert all(editor.same_layout(a["editor"], b["editor"]) for a, b in zip(actual, expected)), actual
assert all(v["cursor"] == 0 for w in actual for v in w["editor"]["views"]), actual
frames = [w for w in resume.window_snapshot() if w["pid"] == pid]
assert {w["id"] for w in actual} == {w["id"] for w in frames}
requests = [dict(a, editor=b["editor"]) for a, b in zip(actual, expected)]
bad = copy.deepcopy(requests)
bad[1]["id"] = "{ffffffff-ffff-ffff-ffff-ffffffffffff}"
assert editor.capture(pid, bad, windows=True) is None and capture(pid, 2) == actual
partial = editor.capture(pid, requests[1:], windows=True)
assert partial[0] == actual[0] and partial[1]["editor"]["views"][0]["cursor"] == 12
requests[1]["editor"]["views"][0]["cursor"] = 60
saved = editor.capture(pid, requests, windows=True)
assert [v["cursor"] for v in saved[0]["editor"]["views"]] == [4, 9]
assert saved[1]["editor"]["views"][0]["cursor"] == 12
close(pid)
editor.cleanup(receipt)
receipt = editor.start("org.kde.kate.desktop", saved, windows=True)
returned = capture(receipt["pid"], 2)
assert all(editor.same_layout(a["editor"], b["editor"]) for a, b in zip(returned, saved))
returned = editor.capture(receipt["pid"], [dict(a, editor=b["editor"]) for a, b in zip(returned, saved)], windows=True)
assert [w["editor"] for w in returned] == [w["editor"] for w in saved], (returned, saved)
close(receipt["pid"])
editor.cleanup(receipt)

compatibility = {}
for app, name in editor.EDITORS.items():
    state = {"views": [{"documents": files[:1], "active": 0, "cursor": 0}], "active": 0, "layout": 0}
    pair = [dict(w, editor=state) for w in expected]
    receipt = editor.start(app, pair, windows=True)
    pid = receipt["pid"]
    before = capture(pid, 2)
    token = uuid.uuid4().hex
    assert resume.dbus(f"org.kde.{name}-{pid}", "/MainApplication", "org.kde.Kate.Application", "monetDeparture", token, True) == [False]
    close(pid, before[0]["id"])
    survivor = capture(pid, 1)
    assert survivor[0]["id"] == before[1]["id"]
    assert editor.capture(pid, before[:1], windows=True) is None
    assert capture(pid, 1) == survivor
    ordinary = editor.capture(pid)
    assert editor.same_layout(ordinary, state)
    resume.dbus("org.kde.KWin", "/Plugins", "org.kde.KWin.Plugins", "UnloadPlugin", "monet_window_identity")
    try:
        assert editor.capture(pid, windows=True) is None
        assert editor.capture(pid) == ordinary
    finally:
        assert resume.dbus("org.kde.KWin", "/Plugins", "org.kde.KWin.Plugins", "LoadPlugin", "monet_window_identity") == [True]
    assert capture(pid, 1) == survivor
    assert resume.arm_editor(app, pid, token)
    close(pid)
    final = editor.departure(app, pid, token)
    assert final["supported"] and editor.same_layout(final["editor"], ordinary), final
    compatibility[name] = {"closed_window_identity_rejected": True, "missing_resolver_safe": True,
                           "legacy_single_window_receipt_unchanged": True}
    editor.departure_path(app, pid, token).unlink()
    editor.cleanup(receipt)

proof = {"native_multi_window_launch_and_reopen": True, "exact_identity": True,
         "cursor_request_atomic_validation": True, "other_window_and_nonzero_cursors_preserved": True,
         "saved": saved, "returned": returned, "compatibility": compatibility}
(folder / "verified.json").write_text(json.dumps(proof, indent=2))
print(json.dumps({key: value for key, value in proof.items() if key not in ("saved", "returned")}))
