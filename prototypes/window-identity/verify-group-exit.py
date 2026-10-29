"""VM-only native group-close checks; same isolated build root as verify-editor.py."""
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
folder = build / ("group-exit-check-" + uuid.uuid4().hex[:8])
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


proof = {}
for app, name in editor.EDITORS.items():
    path = folder / (name + "-shared.txt")
    path.write_text("Saved shared document.\n")
    state = {"views":[{"documents":[str(path)],"active":0,"cursor":0}],"active":0,"layout":0}
    pair = [{"id":"{"+str(uuid.uuid4())+"}","editor":copy.deepcopy(state)} for _ in range(2)]
    launch = editor.start(app, pair, windows=True)
    pid = launch["pid"]
    before = capture(pid)
    visible = wait(lambda: texts(pid))
    assert len(visible) == 2
    unsaved = "Shared unsaved buffer: " + name + "\n"
    assert visible[0].get_editable_text_iface().set_text_contents(unsaved)
    wait(lambda: shared_text(pid, unsaved))
    token = uuid.uuid4().hex
    assert resume.arm_editor(app, pid, token, windows=True)
    close(pid, before[0]["id"])
    button(pid, "Cancel")
    assert [w["id"] for w in capture(pid)] == [w["id"] for w in before]
    wait(lambda: shared_text(pid, unsaved))
    assert path.read_text() == "Saved shared document.\n"
    assert not editor.departure_path(app,pid,token).exists()

    # Cancel Monet while the native save prompt is still open, then accept Save.
    close(pid, before[0]["id"])
    wait(lambda: any(n.get_accessible_id() == "QApplication.KateSaveModifiedDialog" for n in nodes(pid)))
    resume.disarm_editor(app,pid,token)
    button(pid,"Save")
    wait(lambda: path.read_text() == unsaved)
    assert [w["id"] for w in capture(pid)] == [w["id"] for w in before]
    assert not editor.departure_path(app,pid,token).exists()

    # A failed recovery write leaves both windows open; retry closes the whole group.
    token = uuid.uuid4().hex
    assert resume.arm_editor(app,pid,token,windows=True)
    save_as(pid)
    button(pid,"Cancel","QApplication.QFileDialog")
    assert all(editor.paths(w["editor"]) == [str(path)] for w in capture(pid))
    save_as(pid)
    renamed = folder / (name + "-renamed.txt")
    save_path(pid,renamed)
    wait(lambda: renamed.is_file())
    assert path.read_text() == renamed.read_text() == unsaved
    assert all(editor.paths(w["editor"]) == [str(renamed)] for w in capture(pid))
    receipt_path = editor.departure_path(app,pid,token)
    receipt_path.mkdir(mode=0o700)
    close(pid,before[1]["id"])
    assert [w["id"] for w in capture(pid)] == [w["id"] for w in before]
    receipt_path.rmdir()
    resume.dbus("org.kde.KWin","/Plugins","org.kde.KWin.Plugins","UnloadPlugin","monet_window_identity")
    close(pid,before[0]["id"])
    assert len([w for w in resume.window_snapshot() if w["pid"] == pid]) == 2
    assert not receipt_path.exists()
    assert resume.dbus("org.kde.KWin","/Plugins","org.kde.KWin.Plugins","LoadPlugin","monet_window_identity") == [True]
    first_text = "First save while closing: " + name + "\n"
    assert resume.dbus(f"org.kde.{name}-{pid}","/MainApplication","org.kde.Kate.Application","openInput",first_text,"") == [True]
    close(pid,before[0]["id"])
    button(pid,"Save")
    button(pid,"Cancel","QApplication.QFileDialog")
    assert [w["id"] for w in capture(pid)] == [w["id"] for w in before]
    assert not receipt_path.exists()
    button(pid,"Save")
    first_save = folder / (name + "-first-save.txt")
    save_path(pid,first_save)
    exited(pid)
    assert first_save.read_text() == first_text
    final = editor.departure(app,pid,token,windows=True)
    assert [w["id"] for w in final["windows"]] == [w["id"] for w in before]
    assert all(str(renamed) in editor.paths(w["editor"]) and str(path) not in editor.paths(w["editor"]) for w in final["windows"])
    assert sum(str(first_save) in editor.paths(w["editor"]) for w in final["windows"]) == 1
    reopened = editor.start(app,final["windows"],windows=True)
    returned = capture(reopened["pid"])
    assert all(editor.same_layout(a["editor"],b["editor"]) for a,b in zip(returned,final["windows"]))
    wait(lambda: sorted(content(n) for n in texts(reopened["pid"])) == sorted([unsaved,first_text]))
    for window in returned:
        close(reopened["pid"],window["id"])
    exited(reopened["pid"])
    editor.cleanup(launch)
    editor.cleanup(reopened)
    receipt_path.unlink()
    proof[name] = {"shared_unsaved_buffer_survived_veto":True,"late_save_after_cancel_kept_all_windows":True,
                   "receipt_failure_vetoed_whole_group":True,"missing_identity_vetoed_whole_group":True,
                   "group_receipt_and_reopen":True,"shared_save_as_and_first_save_paths":True,
                   "cancelled_save_choosers_preserved_group":True}

# Losing the controller during a prompt must invalidate that prompt, even after a new arm.
app = "org.kde.kate.desktop"
launch = editor.start(app,pair,windows=True)
pid = launch["pid"]
before = capture(pid)
assert texts(pid)[0].get_editable_text_iface().set_text_contents("Controller-loss fixture.\n")
old_token, token = uuid.uuid4().hex, uuid.uuid4().hex
child = subprocess.Popen([sys.executable,"-c",
    "import sys,signal,importlib.machinery,importlib.util; "
    "l=importlib.machinery.SourceFileLoader('r',sys.argv[1]); "
    "r=importlib.util.module_from_spec(importlib.util.spec_from_loader(l.name,l)); l.exec_module(r); "
    "print(r.arm_editor(sys.argv[2],int(sys.argv[3]),sys.argv[4],windows=True),flush=True); signal.pause()",
    str(root/"monet-resume"),app,str(pid),old_token],stdout=subprocess.PIPE,text=True)
assert child.stdout.readline().strip() == "True"
close(pid,before[0]["id"])
wait(lambda:any(n.get_accessible_id() == "QApplication.KateSaveModifiedDialog" for n in nodes(pid)))
child.terminate()
child.wait(timeout=5)
wait(lambda:resume.dbus(f"org.kde.kate-{pid}","/MainApplication","org.kde.Kate.Application","monetDepartureWindows",token,True) == [True])
resume.disarm_editor(app,pid,old_token)
button(pid,"Save")
assert [w["id"] for w in capture(pid)] == [w["id"] for w in before]
assert not editor.departure_path(app,pid,old_token).exists()
assert not editor.departure_path(app,pid,token).exists()
action(pid,"kate","view_new_view")
capture(pid,3)
close(pid,before[0]["id"])
capture(pid,3)
assert not editor.departure_path(app,pid,token).exists()
resume.disarm_editor(app,pid,token)
token = uuid.uuid4().hex
assert resume.arm_editor(app,pid,token,windows=True)
close(pid,before[0]["id"])
exited(pid)
assert len(editor.departure(app,pid,token,windows=True)["windows"]) == 3
editor.departure_path(app,pid,token).unlink()
editor.cleanup(launch)
proof["controller_loss_and_changed_group"] = True

# The existing single-window close path also respects a cancellation during its save dialog.
launch = editor.start(app,state)
pid = launch["pid"]
before = capture(pid,1)
assert texts(pid)[0].get_editable_text_iface().set_text_contents("Legacy cancellation fixture.\n")
token = uuid.uuid4().hex
assert resume.arm_editor(app,pid,token)
token = uuid.uuid4().hex
assert resume.arm_editor(app,pid,token)  # A legacy controller's stale token can be replaced.
close(pid,before[0]["id"])
wait(lambda:any(n.get_accessible_id() == "QApplication.KateSaveModifiedDialog" for n in nodes(pid)))
resume.disarm_editor(app,pid,token)
button(pid,"Save")
assert capture(pid,1)[0]["id"] == before[0]["id"]
assert not editor.departure_path(app,pid,token).exists()
close(pid,before[0]["id"])
exited(pid)
editor.cleanup(launch)
proof["legacy_close_respects_late_cancellation"] = True

(build / "group-exit-verified.json").write_text(json.dumps(proof,indent=2))
print(json.dumps(proof))
