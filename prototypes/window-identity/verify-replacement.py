"""VM-only closed-window replacement checks; same isolated build root as verify-editor.py."""
import copy
import ast
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

build = Path(sys.argv[1]).resolve()
root = build / "identity"
folder = build / ("replacement-check-" + uuid.uuid4().hex[:8])
folder.mkdir()
os.environ.update(json.loads((root / "session-env.json").read_text()))
os.environ.update(XDG_CONFIG_HOME=str(root / "config"), XDG_DATA_HOME=str(folder / "data"),
                  LD_LIBRARY_PATH=str(build / "build/bin"), QT_LINUX_ACCESSIBILITY_ALWAYS_ON="1")
os.environ["AT_SPI_BUS_ADDRESS"] = ast.literal_eval(subprocess.check_output([
    "gdbus","call","--address",f"unix:path=/run/user/{os.getuid()}/bus","--dest","org.a11y.Bus",
    "--object-path","/org/a11y/bus","--method","org.a11y.Bus.GetAddress"],text=True))[0]
loader = importlib.machinery.SourceFileLoader("resume", str(root / "monet-resume"))
resume = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(resume)
editor = resume.editor_helper()
import gi
gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, GLib
Atspi.set_timeout(1000, 1500)


def wait(check):
    for _ in range(60):
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        try:
            value = check()
        except GLib.Error:
            value = None
        if value:
            return value
        time.sleep(.1)
    raise AssertionError("Native editor state did not settle")


def capture(pid, count=2):
    return wait(lambda: (state if state and len(state) == count else None)
                if (state := editor.capture(pid, windows=True)) else None)


def nodes(pid):
    desktop = Atspi.get_desktop(0)
    apps = [desktop.get_child_at_index(i) for i in range(desktop.get_child_count())]
    apps = [a for a in apps if a.get_process_id() == pid]
    result, pending = [], list(apps)
    while pending:
        node = pending.pop(0)
        if node is None:
            continue
        try:
            role = node.get_role()
            ident = node.get_accessible_id() or ""
            if ".KateMDI::ToolView" in ident or role in (Atspi.Role.MENU, Atspi.Role.MENU_BAR,
                    Atspi.Role.LIST, Atspi.Role.TABLE, Atspi.Role.TREE, Atspi.Role.TREE_TABLE):
                continue
            count = node.get_child_count()
            if count < 0:
                continue
            assert count < 500, (node.get_name(), ident, count)
            pending.extend(node.get_child_at_index(i) for i in range(count))
            result.append(node)
            assert len(result) < 3000
        except GLib.Error:
            continue  # Native dialogs can disappear while their accessibility tree is read.
    return result


def texts(pid):
    return [n for n in nodes(pid) if (n.get_accessible_id() or "").endswith(".KateViewInternal")
            and n.get_state_set().contains(Atspi.StateType.VISIBLE)]


def content(node):
    return Atspi.Text.get_text(node, 0, -1)


def shared_text(pid, expected):
    values = texts(pid)
    return len(values) == 2 and all(content(n) == expected for n in values)


def press(node):
    try:
        assert node.get_action_iface().do_action(0)
    except GLib.Error as error:
        if "Did not receive a reply" not in str(error):
            raise
        # Qt's synchronous action reply waits for modal dialogs; each caller checks the result.


def button(pid, label, dialog="QApplication.KateSaveModifiedDialog"):
    choices = wait(lambda: [n for n in nodes(pid) if n.get_role() == Atspi.Role.PUSH_BUTTON
                   and (n.get_name() or "").replace("&", "") == label
                   and (n.get_accessible_id() or "").startswith(dialog + ".")
                   and n.get_state_set().contains(Atspi.StateType.SHOWING)])
    assert len(choices) == 1, [(n.get_name(), n.get_accessible_id()) for n in choices]
    press(choices[0])
    time.sleep(.2)  # Let the native close event unwind before sending the next UI action.


def save_as(pid):
    buttons = [n for n in nodes(pid) if n.get_accessible_id() == "QApplication.MainWindow#1.mainToolBar.QToolButton"
               and n.get_name() == "Save As"]
    assert len(buttons) == 1
    press(buttons[0])
    wait(lambda: any(n.get_accessible_id() == "QApplication.QFileDialog" for n in nodes(pid)))


def save_path(pid, path):
    fields = wait(lambda: [n for n in nodes(pid) if n.get_accessible_id() == "QApplication.QFileDialog.fileNameEdit"])
    assert len(fields) == 1 and fields[0].get_editable_text_iface().set_text_contents(str(path))
    button(pid,"Save","QApplication.QFileDialog")


def close(pid, ident):
    resume.kwin_script("const w=workspace.windowList().find(w=>w.pid==%d&&String(w.internalId)==%s);"
                       "if(w)w.closeWindow();reply(!!w);" % (pid, json.dumps(ident)))


def exited(pid):
    wait(lambda: not any(w["pid"] == pid for w in resume.window_snapshot()))


def action(pid, name, command):
    resume.dbus(f"org.kde.{name}-{pid}", f"/{name}/MainWindow_1", "org.kde.KMainWindow", "activateAction", command)


def frames(pid):
    return [w for w in resume.window_snapshot() if w["pid"] == pid]


def remember(app, pid, path):
    saved = resume.checkpoint([app], list(reversed(frames(pid))))
    assert len(saved["groups"][app]) == 1 and len(saved["groups"][app][0]["editor_windows"]) == 2
    resume.atomic_write(path, saved)
    current = resume.departure_windows()
    target = next(w for w in current if w["pid"] == pid and w["normal"])
    resume.prepare_editor_close(path, saved["id"], target, current)
    group = resume.read_state(path)["groups"][app][0]
    assert group["closing"]["windows"] is True
    return saved["id"]


def restore(path, off, token, manual=False):
    def unexpected(_):
        raise AssertionError("Automatic groups must use the native session launcher")
    resume.restore(path, off, lambda: [], lambda _: True, unexpected, request=token if manual else None)
    return resume.return_status(path, off)["items"][0]


def finish(pid):
    for window in capture(pid, len(frames(pid))):
        close(pid, window["id"])
    exited(pid)


def state(path, cursor=0):
    return {"views": [{"documents": [str(path)], "active": 0, "cursor": cursor}], "active": 0, "layout": 0}


def replace(app, pid, request):
    return resume.dbus(f"org.kde.{editor.EDITORS[app]}-{pid}", "/MainApplication",
                       "org.kde.Kate.Application", "monetReplaceWindow", json.dumps(request))[0]


proof = {}
for app, name in editor.EDITORS.items():
    files = [folder / (name + "-" + label + ".txt") for label in ("sibling", "first", "second", "third")]
    for index, file in enumerate(files):
        file.write_text(("Saved fixture %d.\n" % index) * 40)
    layout = {"views": [state(p, 20 + i * 20)["views"][0] for i, p in enumerate(files[1:])], "active": 1,
              "layout": {"orientation": 1, "sizes": [400, 600], "children": [0,
                  {"orientation": 2, "sizes": [300, 500], "children": [1, 2]}]}}
    pair = [{"id": "{" + str(uuid.uuid4()) + "}", "editor": s} for s in (state(files[0]), layout)]
    launch = editor.start(app, pair, windows=True)
    pid = launch["pid"]
    original = capture(pid)
    assert editor.capture(pid, [{"id": original[1]["id"], "editor": layout}], windows=True)
    path, off = folder / (name + "-trip.json"), folder / "off"
    token = remember(app, pid, path)
    close(pid, original[0]["id"]); exited(pid)
    assert resume.refresh_departure(path, token, resume.departure_windows(), final=True)
    assert resume.cancel_departure(path, token)
    contents_on_disk = [p.read_text() for p in files]
    for file in files[1:]: file.unlink()
    assert restore(path, off, token)["status"] == "documents-missing"
    saved = resume.read_state(path)
    group = saved["groups"][app][0]
    first_owner = group["editor_owners"][original[0]["id"]]
    lost_owner = group["editor_owners"][original[1]["id"]]
    pid = first_owner["pid"]
    close(pid, lost_owner["id"])
    wait(lambda: len(frames(pid)) == 1)
    assert capture(pid, 1)[0]["id"] == first_owner["id"]
    for file, text in zip(files[1:3], contents_on_disk[1:3]): file.write_text(text)

    # Reuse a late file which the person already opened and edited in the surviving window.
    resume.dbus(f"org.kde.{name}-{pid}", "/MainApplication", "org.kde.Kate.Application", "openUrl", files[1].as_uri(), "")
    visible = wait(lambda: [n for n in texts(pid) if content(n) == contents_on_disk[1]])
    assert len(visible) == 1
    unsaved = ("Unsaved shared buffer in " + name + ".\n") * 40
    assert visible[0].get_editable_text_iface().set_text_contents(unsaved)
    wait(lambda: any(content(n) == unsaved for n in texts(pid)))
    expected = editor.available(layout, [str(p) for p in files[1:]])
    request = {"id": lost_owner["id"], "anchor": first_owner["id"], "editor": expected}
    before = capture(pid, 1)
    before_frames = frames(pid)
    bad = [dict(request, anchor=lost_owner["id"]), dict(request, id=first_owner["id"]), dict(request, text="secret")]
    bad += [dict(request, attempt=value) for value in (None, True, "", "a" * 31, "A" * 32, "a" * 32 + "\n")]
    for edit in (lambda s: s.update(active=True), lambda s: s["views"][0].update(documents=["https://private.invalid/file"]),
                 lambda s: s.update(layout={"children": [0, 0], "sizes": [100, 100], "orientation": 1}),
                 lambda s: s["views"][0].update(cursor=1.5),
                 lambda s: s["views"][0].update(documents=[str(files[1])] * 101),
                 lambda s: s.update(layout={"children": [0, 1], "sizes": [0, 100], "orientation": 1}),
                 lambda s: s["views"][0].update(documents=[str(files[3])])):
        item = copy.deepcopy(request); edit(item["editor"]); bad.append(item)
    for invalid in bad:
        assert replace(app, pid, invalid) == ""
        assert capture(pid, 1) == before
    watch = uuid.uuid4().hex
    assert resume.arm_editor(app, pid, watch, windows=True)
    assert replace(app, pid, request) == ""
    resume.disarm_editor(app, pid, watch)
    resume.dbus("org.kde.KWin", "/Plugins", "org.kde.KWin.Plugins", "UnloadPlugin", "monet_window_identity")
    assert replace(app, pid, request) == ""
    assert resume.dbus("org.kde.KWin", "/Plugins", "org.kde.KWin.Plugins", "LoadPlugin", "monet_window_identity") == [True]

    # Simulate losing the first reply after the native operation has created its window.
    native_replace, requests = resume.replace_editor, []
    def uncertain(app, pid, value):
        requests.append(copy.deepcopy(value))
        result = native_replace(app, pid, value)
        return None if len(requests) == 1 else result
    resume.replace_editor = uncertain
    result = restore(path, off, token, manual=True)
    resume.replace_editor = native_replace
    assert result["status"] == "documents-missing" and result["missing"] == [files[3].name], result
    assert len(requests) >= 2 and all(value == requests[0] for value in requests)
    group = resume.read_state(path)["groups"][app][0]
    owner = group["editor_owners"][original[1]["id"]]
    assert owner["pid"] == pid and owner["id"] not in (first_owner["id"], lost_owner["id"])
    returned = capture(pid)
    sibling = next(w for w in returned if w["id"] == first_owner["id"])
    replacement = next(w for w in returned if w["id"] == owner["id"])
    assert sibling == before[0]
    assert editor.same_layout(replacement["editor"], expected)
    assert [v["cursor"] for v in replacement["editor"]["views"]] == [v["cursor"] for v in expected["views"]]
    wait(lambda: [content(n) for n in texts(pid)].count(unsaved) == 2)
    assert files[1].read_text() == contents_on_disk[1]
    after_first = next(w for w in frames(pid) if w["id"] == first_owner["id"])
    (folder / (name + "-survivor.json")).write_text(json.dumps({"before": before_frames[0], "after": after_first}, indent=2))
    assert {k: v for k, v in after_first.items() if k != "stack"} == {k: v for k, v in before_frames[0].items() if k != "stack"}, (before_frames[0], after_first)
    prior = resume.desktop_snapshot()
    resume.kwin_script("workspace.activeWindow=windows().find(w=>String(w.internalId)===%s);reply(true);" % json.dumps(owner["id"]))
    prior["scene"]["cursor"]["x"] += 1
    resume.restore_replacement_focus(prior, owner["id"])
    assert next(w for w in frames(pid) if w["id"] == owner["id"])["active"]
    resume.kwin_script("workspace.activeWindow=windows().find(w=>String(w.internalId)===%s);reply(true);" % json.dumps(first_owner["id"]))
    prior = resume.desktop_snapshot()
    unrelated = next(w for w in prior["windows"] if w["app"] == "org.monet.WindowIdentityTest.desktop")
    resume.kwin_script("workspace.activeWindow=windows().find(w=>String(w.internalId)===%s);reply(true);" % json.dumps(unrelated["id"]))
    resume.restore_replacement_focus(prior, owner["id"])
    assert next(w for w in resume.window_snapshot() if w["id"] == unrelated["id"])["active"]
    resume.kwin_script("workspace.activeWindow=windows().find(w=>String(w.internalId)===%s);reply(true);" % json.dumps(first_owner["id"]))
    assert replace(app, pid, requests[0]) == owner["id"]
    assert replace(app, pid, dict(requests[0], attempt=uuid.uuid4().hex)) == ""
    changed = copy.deepcopy(requests[0]); changed["editor"]["views"][0]["cursor"] += 1
    assert replace(app, pid, changed) == ""
    assert len(frames(pid)) == 2
    close(pid, owner["id"])
    wait(lambda: len(frames(pid)) == 1)
    assert replace(app, pid, requests[0]) == "closed"
    assert replace(app, pid, changed) == ""  # Changed requests cannot claim the original receipt.
    files[3].write_text(contents_on_disk[3])
    restore(path, off, token)
    assert len(frames(pid)) == 1
    # Close a successfully created window before its reply reaches the recovery caller.
    closed_requests, closed_ids = [], []
    def closed_before_reply(app, pid, value):
        closed_requests.append(copy.deepcopy(value))
        result = native_replace(app, pid, value)
        if result is not None and not closed_ids:
            assert result != "closed"
            close(pid, result)
            wait(lambda: len(frames(pid)) == 1)
            closed_ids.append(result)
            return None
        return result
    resume.replace_editor = closed_before_reply
    result = restore(path, off, token, manual=True)
    resume.replace_editor = native_replace
    assert result["status"] == "partly-restored" and result["retry"] and result["missingCount"] == 0, result
    assert len(closed_ids) == 1 and len(closed_requests) >= 2 and all(value == closed_requests[0] for value in closed_requests)
    assert len(frames(pid)) == 1
    group = resume.read_state(path)["groups"][app][0]
    assert not group["editor_replacements"]
    assert group["pending_windows"][original[1]["id"]] == [str(files[3])]
    restore(path, off, token)
    assert len(frames(pid)) == 1
    result = restore(path, off, token, manual=True)
    assert result["status"] == "documents-opened", result
    current = capture(pid)
    assert next(w for w in current if w["id"] == first_owner["id"]) == before[0]
    last = next(w for w in current if w["id"] != first_owner["id"])
    assert editor.paths(last["editor"]) == [str(files[3])]
    assert last["id"] != owner["id"]
    restore(path, off, token, manual=True)
    assert capture(pid) == current
    action(pid, name, "file_save_all")
    wait(lambda: files[1].read_text() == unsaved)
    legacy = {"id": last["id"], "anchor": first_owner["id"], "editor": last["editor"]}
    close(pid, last["id"])
    wait(lambda: len(frames(pid)) == 1)
    legacy_id = wait(lambda: replace(app, pid, legacy))
    assert legacy_id not in ("closed", last["id"], first_owner["id"])
    assert replace(app, pid, legacy) == legacy_id
    close(pid, legacy_id)
    wait(lambda: len(frames(pid)) == 1)
    assert replace(app, pid, legacy) == "closed"
    finish(pid); editor.cleanup(launch)
    proof[name] = {"closed_missing_window_recreated_in_same_process": True, "nested_layout_and_cursors": True,
                   "shared_unsaved_buffer_reused": True, "survivor_frame_focus_and_state_preserved": True,
                   "lost_reply_did_not_duplicate": True, "stale_closed_replacement_did_not_reopen": True,
                   "second_closed_generation_recovered": True, "invalid_and_unavailable_identity_rejected": True}
    proof[name]["focus_guard_respects_other_window_and_pointer_mismatch"] = True
    proof[name]["closed_before_confirmation_waits_for_new_explicit_retry"] = True
    proof[name]["new_attempt_cannot_duplicate_a_live_window"] = True
    proof[name]["legacy_request_and_closed_receipt"] = True
    (folder / "proof.json").write_text(json.dumps(proof, indent=2))
    print(name, "replacement checks passed", flush=True)
(root / "replacement-verified.json").write_text(json.dumps({"folder": str(folder), "checks": proof}, indent=2))
print(json.dumps(proof, indent=2))
