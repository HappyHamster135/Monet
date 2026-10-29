"""VM-only targeted late-file recovery; never read or edit anything outside these fixtures."""
import ast
import copy
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
folder = build / ("retry-check-" + uuid.uuid4().hex[:8])
folder.mkdir()
os.environ.update(json.loads((root / "session-env.json").read_text()))
os.environ.update(XDG_CONFIG_HOME=str(root / "config"), XDG_DATA_HOME=str(folder / "data"),
                  LD_LIBRARY_PATH=str(build / "build/bin"), QT_LINUX_ACCESSIBILITY_ALWAYS_ON="1")
os.environ["AT_SPI_BUS_ADDRESS"] = ast.literal_eval(subprocess.check_output([
    "gdbus", "call", "--address", f"unix:path=/run/user/{os.getuid()}/bus", "--dest", "org.a11y.Bus",
    "--object-path", "/org/a11y/bus", "--method", "org.a11y.Bus.GetAddress"], text=True))[0]
loader = importlib.machinery.SourceFileLoader("resume", str(root / "monet-resume"))
resume = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(resume)
editor = resume.editor_helper()
reply_errors, native_dbus = [], resume.dbus
def observed_dbus(*args):
    try:
        return native_dbus(*args)
    except RuntimeError as error:
        if args[3] == "monetReopenDocuments":
            reply_errors.append(str(error))
        raise
resume.dbus = observed_dbus
import gi
gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, GLib
Atspi.set_timeout(1000, 1500)


def wait(check):
    for _ in range(60):
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        try:
            result = check()
        except GLib.Error:
            result = None
        if result:
            return result
        time.sleep(.1)
    raise AssertionError("Native retry fixture did not settle")


def capture(pid, count=2):
    return wait(lambda: state if (state := editor.capture(pid, windows=True)) and len(state) == count else None)


def texts(pid):
    desktop = Atspi.get_desktop(0)
    apps = [desktop.get_child_at_index(i) for i in range(desktop.get_child_count())]
    pending = [a for a in apps if a.get_process_id() == pid]
    result, seen = [], 0
    while pending:
        node = pending.pop(0)
        if node is None:
            continue
        try:
            ident, role = node.get_accessible_id() or "", node.get_role()
            if ".KateMDI::ToolView" in ident or role in (Atspi.Role.MENU, Atspi.Role.MENU_BAR,
                    Atspi.Role.LIST, Atspi.Role.TABLE, Atspi.Role.TREE, Atspi.Role.TREE_TABLE):
                continue
            if ident.endswith(".KateViewInternal") and node.get_state_set().contains(Atspi.StateType.VISIBLE):
                result.append(node)
            count = node.get_child_count()
            if count < 0:
                continue
            assert count < 500 and seen < 3000
            seen += 1
            pending.extend(node.get_child_at_index(i) for i in range(count))
        except GLib.Error:
            continue
    return result


def contents(node):
    return Atspi.Text.get_text(node, 0, -1)


def state(path, cursor=0):
    return {"views": [{"documents": [str(path)], "active": 0, "cursor": cursor}], "active": 0, "layout": 0}


def close(pid, name):
    resume.dbus(f"org.kde.{name}-{pid}", f"/{name}/MainWindow_1", "org.kde.KMainWindow", "activateAction", "file_save_all")
    resume.kwin_script("for(const w of workspace.windowList())if(w.pid==%d)w.closeWindow();reply(true);" % pid)
    wait(lambda: not any(w["pid"] == pid for w in resume.window_snapshot()))


proof = {}
for app, name in editor.EDITORS.items():
    first, shared, late = [folder / (name + suffix) for suffix in ("-first.txt", "-shared.txt", "-late [x].txt")]
    first.write_text("First document remains selected.\n")
    bottom = folder / (name + "-bottom.txt")
    bottom.write_text("The target pane keeps its selection and cursor.\n")
    shared.write_text("Saved shared buffer.\n")
    late.write_text("Late file contents.\n")
    expected = [{"id": "{" + str(uuid.uuid4()) + "}", "editor": value}
                for value in (state(first, 5), state(shared, 7))]
    expected[0]["editor"]["views"].append(state(bottom, 9)["views"][0])
    expected[0]["editor"].update(active=1, layout={"orientation": 1, "sizes": [500, 400], "children": [0, 1]})
    launch = editor.start(app, expected, windows=True)
    pid = launch["pid"]
    before = capture(pid)
    before = editor.capture(pid, [dict(a, editor=b["editor"]) for a, b in zip(before, expected)], windows=True)
    shared_view = wait(lambda: [n for n in texts(pid) if contents(n) == shared.read_text()])[0]
    unsaved = "Shared unsaved changes must survive: " + name + "\n"
    assert shared_view.get_editable_text_iface().set_text_contents(unsaved)
    wait(lambda: any(contents(n) == unsaved for n in texts(pid)))
    before = capture(pid)
    resume.kwin_script("workspace.activeWindow=workspace.windowList().find(w=>String(w.internalId)==%s);reply(true);" % json.dumps(before[1]["id"]))
    geometry = "reply(workspace.windowList().filter(w=>w.pid==%d).map(w=>({id:String(w.internalId),active:w.active,rect:rect(w.frameGeometry)})));" % pid
    frame_before = resume.kwin_script(geometry)

    def raw(request):
        return resume.dbus(f"org.kde.{name}-{pid}", "/MainApplication", "org.kde.Kate.Application",
                           "monetReopenDocuments", json.dumps(request))
    good = {"id": before[0]["id"], "documents": [str(late)]}
    for bad in (dict(good, id="{ffffffff-ffff-ffff-ffff-ffffffffffff}"),
                dict(good, documents=[str(late), str(folder / "absent.txt")]),
                dict(good, documents=[str(folder)]), dict(good, documents=[str(late)] * 2),
                dict(good, documents=[str(late)] * 101), dict(good, documents=[]),
                dict(good, documents=[1]), dict(good, documents=["https://example.org/private"]),
                dict(good, documents=["/control\npath"]), dict(good, text="must not be accepted")):
        assert raw(bad) == [False], bad
        assert capture(pid) == before

    prior_errors = len(reply_errors)
    accepted = resume.reopen_editor(app, pid, before[0]["id"], [str(shared), str(late)])
    assert accepted or reply_errors[prior_errors:] == ["org.freedesktop.DBus.Error.NoReply"], reply_errors[prior_errors:]
    after = capture(pid)
    assert after[1] == before[1], (before, after)
    assert after[0]["editor"]["views"][0] == before[0]["editor"]["views"][0]
    assert after[0]["editor"]["views"][1]["documents"] == [str(bottom), str(shared), str(late)], after
    assert after[0]["editor"]["views"][1]["active"] == before[0]["editor"]["views"][1]["active"]
    assert after[0]["editor"]["views"][1]["cursor"] == before[0]["editor"]["views"][1]["cursor"]
    assert after[0]["editor"]["layout"] == before[0]["editor"]["layout"]
    assert after[0]["editor"]["active"] == before[0]["editor"]["active"]
    assert resume.kwin_script(geometry) == frame_before
    assert shared.read_text() == "Saved shared buffer.\n"
    assert any(contents(n) == unsaved for n in texts(pid))
    assert resume.reopen_editor(app, pid, before[0]["id"], [str(shared), str(late)])
    assert capture(pid) == after
    alias = folder / (name + "-first-alias.txt")
    alias.symlink_to(first)
    assert resume.reopen_editor(app, pid, before[0]["id"], [str(alias)])
    assert capture(pid) == after

    resume.dbus("org.kde.KWin", "/Plugins", "org.kde.KWin.Plugins", "UnloadPlugin", "monet_window_identity")
    try:
        assert raw(good) == [False]
    finally:
        assert resume.dbus("org.kde.KWin", "/Plugins", "org.kde.KWin.Plugins", "LoadPlugin", "monet_window_identity") == [True]
    assert capture(pid) == after
    # Reveal the newly shared tab only after proving retry preserved the selected views.
    resume.dbus(f"org.kde.{name}-{pid}", f"/{name}/MainWindow_1", "org.kde.KMainWindow", "activateAction", "view_next_tab")
    wait(lambda: len([n for n in texts(pid) if contents(n) == unsaved]) == 2)
    resume.dbus(f"org.kde.{name}-{pid}", f"/{name}/MainWindow_1", "org.kde.KMainWindow", "activateAction", "view_next_tab")
    wait(lambda: any(contents(n) == late.read_text() for n in texts(pid)))
    close(pid, name)
    assert shared.read_text() == unsaved
    editor.cleanup(launch)
    proof[name] = {"exact_inactive_window_target": True, "shared_unsaved_buffer_reused": True,
                   "selection_cursor_geometry_focus_preserved": True, "retry_and_alias_without_duplicates": True,
                   "invalid_requests_and_missing_resolver_rejected": True, "before": before, "after": after}

    # The production recovery caller must use this operation after an initially missing file returns.
    late.unlink()
    original = state(first, 5)
    original["views"][0]["documents"].append(str(late))
    saved = {"version": 2, "id": uuid.uuid4().hex, "boot": "earlier-boot", "apps": [app],
             "groups": {app: [{"editor": original, "windows": []}]}}
    checkpoint, off = folder / (name + "-trip.json"), folder / "off"
    resume.atomic_write(checkpoint, saved)
    def restore(manual):
        job = resume.restore_editors(checkpoint, saved, app, off, resume.window_snapshot(),
                                     lambda _: (_ for _ in ()).throw(AssertionError("Unexpected generic launch")), manual)
        while True:
            try:
                next(job)
            except StopIteration as finished:
                return finished.value
            time.sleep(.15)
    assert not restore(False)
    group = saved["groups"][app][0]
    assert group["pending"] == [str(late)] and group["status"] == "documents-missing"
    owner = group["editor_owner"]
    initial = capture(owner["pid"], 1)
    assert editor.paths(initial[0]["editor"]) == [str(first)]
    late.write_text("The previously missing file is available again.\n")
    assert not restore(False) and capture(owner["pid"], 1) == initial
    calls, original_dbus = [], resume.dbus
    def tracked(*args):
        calls.append(args[3])
        return original_dbus(*args)
    resume.dbus = tracked
    try:
        assert restore(True)
    finally:
        resume.dbus = original_dbus
    final = capture(owner["pid"], 1)
    assert final[0]["id"] == owner["id"] and group["editor_owner"] == owner
    assert group["pending"] == [] and group["status"] == "documents-opened"
    assert "monetReopenDocuments" in calls and "openUrl" not in calls
    assert final[0]["editor"]["views"][0]["documents"] == [str(first), str(late)]
    assert final[0]["editor"]["views"][0]["cursor"] == initial[0]["editor"]["views"][0]["cursor"]
    assert restore(True) and capture(owner["pid"], 1) == final
    resume.dbus(f"org.kde.{name}-{owner['pid']}", f"/{name}/MainWindow_1", "org.kde.KMainWindow", "activateAction", "view_next_tab")
    wait(lambda: any(contents(n) == late.read_text() for n in texts(owner["pid"])))
    close(owner["pid"], name)
    proof[name]["production_missing_file_retry_uses_exact_window"] = True
    proof[name]["automatic_retry_leaves_late_files_alone"] = True
    proof[name]["completed_retry_is_idempotent"] = True

(folder / "verified.json").write_text(json.dumps(proof, indent=2))
(folder / "reply-errors.json").write_text(json.dumps(reply_errors))
print(json.dumps({name: {key: value for key, value in result.items() if isinstance(value, bool)} for name, result in proof.items()}))
