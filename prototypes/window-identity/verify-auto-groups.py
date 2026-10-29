"""VM-only automatic group recovery checks; same isolated build root as verify-editor.py."""
import copy
import ast
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time
import uuid

build = Path(sys.argv[1]).resolve()
root = build / "identity"
folder = build / ("auto-groups-check-" + uuid.uuid4().hex[:8])
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
    def checkpoint():
        saved = resume.checkpoint([app], list(reversed(frames(pid))))
        groups = saved.get("groups", {}).get(app, [])
        return saved if len(groups) == 1 and len(groups[0].get("editor_windows", [])) == 2 else None
    saved = wait(checkpoint)
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


def select_tab(pid, file, window=1, beside=None):
    tabs = wait(lambda: [n for n in nodes(pid) if n.get_role() == Atspi.Role.PAGE_TAB
                and n.get_name() == file.name
                and (n.get_accessible_id() or "").startswith(f"QApplication.MainWindow#{window}.")])
    if beside is not None:
        tabs = [tab for tab in tabs if any(tab.get_parent().get_child_at_index(i).get_name() == beside.name
                for i in range(tab.get_parent().get_child_count()))]
    assert len(tabs) == 1
    press(tabs[0])


def window_number(pid, file):
    tabs = [n for n in nodes(pid) if n.get_role() == Atspi.Role.PAGE_TAB and n.get_name() == file.name]
    assert len(tabs) == 1
    return int(re.match(r"QApplication.MainWindow#(\d+)\.", tabs[0].get_accessible_id())[1])


def hidden_cursors(app, name):
    files = [folder / (name + "-cursor-%d.txt" % i) for i in range(4)]
    for i, file in enumerate(files): file.write_text(("Document %d line.\n" % i) * 30)
    shared = files[3]
    panes = [{"documents": [str(file), str(shared)], "active": 0, "cursor": cursor, "cursors": [None, hidden]}
             for file, cursor, hidden in zip(files, (5, 7, 9), (37, 81, 119))]
    for i, pane in enumerate(panes):
        line, column = divmod(pane["cursors"][1], len("Document 3 line.\n"))
        pane["selections"] = [None, {"block": False, "cursor": [line, column], "range": None, "anchor": None,
                                    "secondary": [{"cursor": [20 + i, 1], "range": None, "anchor": None}]}]
    pair = [{"id": "{" + str(uuid.uuid4()) + "}", "editor": {"views": panes[:2], "active": 0,
              "layout": {"orientation": 1, "sizes": [400, 400], "children": [0, 1]}}},
            {"id": "{" + str(uuid.uuid4()) + "}", "editor": {"views": panes[2:], "active": 0, "layout": 0}}]
    launch = editor.start(app, pair, windows=True)
    pid = launch["pid"]
    original = capture(pid)
    expected = [dict(actual, editor=saved["editor"]) for actual, saved in zip(original, pair)]
    before_frames = frames(pid)
    restored = wait(lambda: editor.capture(pid, expected, windows=True))
    assert [[{k: v for k, v in pane.items() if k not in ("scrolls", "foldings")} for pane in w["editor"]["views"]] for w in restored] == [
        w["editor"]["views"] for w in pair], restored
    assert frames(pid) == before_frames
    assert len([n for n in nodes(pid) if (n.get_accessible_id() or "").endswith(".KateViewInternal")]) == 3
    # The native boundary rejects the entire request before changing even the first pane.
    assert Atspi.Text.set_caret_offset(next(n for n in texts(pid) if Atspi.Text.get_caret_offset(n) == 5), 0)
    restored = capture(pid)
    for offsets in ([None], [0, 37], [None, True], [None, -1], [None, 2**31], [None, "37"]):
        bad = copy.deepcopy(restored)
        for w in bad: w["editor"]["layout"] = editor.layout(w["editor"], False)
        bad[0]["editor"]["views"][0]["cursor"] = 1
        bad[1]["editor"]["views"][0]["cursors"] = offsets
        assert resume.dbus(f"org.kde.{name}-{pid}", "/MainApplication", "org.kde.Kate.Application",
                           "monetEditorWindows", json.dumps(bad)) == ["null"]
        assert capture(pid) == restored
    assert wait(lambda: editor.capture(pid, expected, windows=True))
    path, off = folder / (name + "-cursor-trip.json"), folder / "off"
    # Save As during an armed switch retains hidden positions as well as the new URL.
    token = remember(app, pid, path)
    save_as(pid)
    renamed = folder / (name + "-cursor-renamed.txt")
    save_path(pid, renamed)
    wait(lambda: renamed.is_file())
    files[0] = renamed
    for cycle in range(2):
        if cycle: token = remember(app, pid, path)
        before = capture(pid)
        close(pid, before[0]["id"]); exited(pid)
        assert resume.refresh_departure(path, token, resume.departure_windows(), final=True)
        assert resume.cancel_departure(path, token)
        assert restore(path, off, token)["status"] == "documents-opened"
        pid = next(w["pid"] for w in resume.window_snapshot() if w["app"] == app)
        restored = capture(pid)
        assert [w["editor"]["views"] for w in restored] == [w["editor"]["views"] for w in before]
        assert len([n for n in nodes(pid) if (n.get_accessible_id() or "").endswith(".KateViewInternal")]) == 3
    print(name, "hidden positions survived Save As and two recoveries", flush=True)
    # A replacement seeds its own positions even when a sibling shares the document.
    old = restored[0]
    surviving = copy.deepcopy(restored[1])
    close(pid, old["id"]); wait(lambda: len(frames(pid)) == 1)
    request = {"id": old["id"], "anchor": restored[1]["id"], "editor": old["editor"], "attempt": uuid.uuid4().hex}
    new = wait(lambda: resume.replace_editor(app, pid, request))
    restored = capture(pid)
    assert next(w for w in restored if w["id"] == new)["editor"]["views"] == old["editor"]["views"]
    assert next(w for w in restored if w["id"] != new) == surviving
    replacement_number, sibling_number = window_number(pid, files[0]), window_number(pid, files[2])
    for window, beside, position in ((replacement_number, files[0], 37), (replacement_number, files[1], 81), (sibling_number, files[2], 119)):
        select_tab(pid, shared, window, beside)
        wait(lambda: any(v["documents"][v["active"]] == str(shared) and v["cursor"] == position
                         for w in capture(pid) for v in w["editor"]["views"]))
    assert sorted(Atspi.Text.get_caret_offset(n) for n in texts(pid)) == [37, 81, 119]
    shared_states = [editor.document_selection({"views": [v], "active": 0, "layout": 0}, str(shared))
                     for w in capture(pid) for v in w["editor"]["views"]]
    assert sorted(s["secondary"][0]["cursor"] for s in shared_states) == [[20, 1], [21, 1], [22, 1]]
    print(name, "three shared-document carets verified after replacement", flush=True)
    # A moved visible or hidden live cursor must never be reset by a repeated request.
    node = next(n for n in texts(pid) if Atspi.Text.get_caret_offset(n) == 119)
    assert Atspi.Text.set_caret_offset(node, 155)
    moved = capture(pid)
    request = copy.deepcopy(moved)
    for w in request:
        for view in w["editor"]["views"]: view["cursor"] = 1
    assert editor.capture(pid, request, windows=True) == moved
    select_tab(pid, files[2], sibling_number)
    moved = capture(pid)
    request = copy.deepcopy(moved)
    sibling = next(w for w in request if str(files[2]) in editor.paths(w["editor"]))
    sibling["editor"]["views"][0]["cursors"] = [None, 1]
    assert editor.capture(pid, request, windows=True) == moved
    # Keep the original selection before testing a late shared file in both windows.
    select_tab(pid, files[0], replacement_number); select_tab(pid, files[1], replacement_number)
    token = remember(app, pid, path)
    original = capture(pid)
    close(pid, original[0]["id"]); exited(pid)
    assert resume.refresh_departure(path, token, resume.departure_windows(), final=True)
    assert resume.cancel_departure(path, token)
    saved_text = shared.read_text(); shared.unlink()
    assert restore(path, off, token)["status"] == "documents-missing"
    pid = next(w["pid"] for w in resume.window_snapshot() if w["app"] == app)
    before_retry = capture(pid)
    shared.write_text(saved_text)
    for offsets in ([], [True], [-1], [2**31], ["81"]):
        request = {"id": before_retry[0]["id"], "documents": [str(shared)], "cursors": offsets}
        assert resume.dbus(f"org.kde.{name}-{pid}", "/MainApplication", "org.kde.Kate.Application",
                           "monetReopenDocuments", json.dumps(request)) == [False]
        assert capture(pid) == before_retry
    assert restore(path, off, token, manual=True)["status"] == "documents-opened"
    returned = capture(pid)
    for old, current, previous in zip(original, returned, before_retry):
        offset = editor.document_cursor(old["editor"], str(shared))
        assert editor.document_cursor(current["editor"], str(shared)) == offset
        assert [(v["documents"][v["active"]], v["cursor"]) for v in current["editor"]["views"]] == [
            (v["documents"][v["active"]], v["cursor"]) for v in previous["editor"]["views"]]
    finish(pid); editor.cleanup(launch)
    # Truncated files clamp saved offsets, including positions applied on first selection.
    shared.write_text("short")
    launch = editor.start(app, pair, windows=True); pid = launch["pid"]
    current = capture(pid)
    assert wait(lambda: editor.capture(pid, [dict(a, editor=b["editor"]) for a, b in zip(current, pair)], windows=True))
    select_tab(pid, shared, 2)
    wait(lambda: any(Atspi.Text.get_caret_offset(n) == 5 and content(n) == "short" for n in texts(pid)))
    finish(pid); editor.cleanup(launch)


def scroll_positions(app, name):
    files = [folder / (name + "-scroll-%d.txt" % i) for i in range(3)]
    for i, file in enumerate(files):
        file.write_text("".join(f"Document {i} line {line:04d} " + "abcdefghij" * 40 + "\n" for line in range(400)))
    shared = files[2]
    pair = [{"id": "{" + str(uuid.uuid4()) + "}", "editor": {"views": [{
        "documents": [str(file), str(shared)], "active": 0, "cursor": 0, "cursors": [None, 0],
        "scrolls": [[50 + i * 40, 0, 120, False], [160 + i * 40, 0, 70, False]]}], "active": 0, "layout": 0}}
        for i, file in enumerate(files[:2])]
    launch = editor.start(app, pair, windows=True); pid = launch["pid"]
    current = capture(pid)
    request = [dict(a, editor=b["editor"]) for a, b in zip(current, pair)]
    restored = wait(lambda: editor.capture(pid, request, windows=True))
    assert [[{k: v for k, v in pane.items() if k != "foldings"} for pane in w["editor"]["views"]] for w in restored] == [
        w["editor"]["views"] for w in pair], restored
    assert len([n for n in nodes(pid) if (n.get_accessible_id() or "").endswith(".KateViewInternal")]) == 2
    bars = [n for n in nodes(pid) if n.get_role() == Atspi.Role.SCROLL_BAR and n.get_state_set().contains(Atspi.StateType.VISIBLE)]
    values = [n.get_value_iface().get_current_value() for n in bars]
    assert 50 in values and 90 in values and 120 in values, values
    # The caret is still zero: a repeated request must respect scrolling alone.
    changed = copy.deepcopy(request)
    for w in changed: w["editor"]["views"][0]["scrolls"] = [[1, 0, 0, True], [2, 0, 0, True]]
    assert wait(lambda: editor.capture(pid, changed, windows=True)) == restored
    path, off = folder / (name + "-scroll-trip.json"), folder / "off"
    token = remember(app, pid, path)
    save_as(pid)
    renamed = folder / (name + "-scroll-renamed.txt")
    save_path(pid, renamed); wait(lambda: renamed.is_file()); files[0] = renamed
    pair[0]["editor"]["views"][0]["documents"][0] = str(renamed)
    assert [w["editor"]["views"][0]["scrolls"] for w in capture(pid)] == [w["editor"]["views"][0]["scrolls"] for w in pair]
    for cycle in range(2):
        if cycle: token = remember(app, pid, path)
        before = capture(pid)
        close(pid, before[0]["id"]); exited(pid)
        assert resume.refresh_departure(path, token, resume.departure_windows(), final=True)
        assert resume.cancel_departure(path, token)
        assert restore(path, off, token)["status"] == "documents-opened"
        pid = next(w["pid"] for w in resume.window_snapshot() if w["app"] == app)
        restored = capture(pid)
        assert [w["editor"]["views"] for w in restored] == [w["editor"]["views"] for w in before], (before, restored)
    for i in range(2):
        select_tab(pid, shared, window_number(pid, files[i]))
        wait(lambda: editor.document_scroll(capture(pid)[i]["editor"], str(shared)) == [160 + i * 40, 0, 70, False])
    print(name, "vertical and horizontal scrolls survived Save As, repeat recovery and hidden-tab selection", flush=True)
    for i in range(2):
        prefix = f"QApplication.MainWindow#{window_number(pid, files[i])}."
        view = next(n for n in texts(pid) if n.get_accessible_id().startswith(prefix))
        assert Atspi.Text.set_caret_offset(view, 11 + i * 22)
        for bar in nodes(pid):
            if (bar.get_role() == Atspi.Role.SCROLL_BAR and bar.get_accessible_id().startswith(prefix)
                    and bar.get_state_set().contains(Atspi.StateType.VISIBLE)):
                vertical = bar.get_state_set().contains(Atspi.StateType.VERTICAL)
                assert bar.get_value_iface().set_current_value(160 + i * 40 if vertical else 70)
    current = capture(pid); old = current[0]
    assert [w["editor"]["views"][0]["cursor"] for w in current] == [11, 33]
    close(pid, old["id"]); wait(lambda: len(frames(pid)) == 1)
    replacement = {"id": old["id"], "anchor": current[1]["id"], "editor": old["editor"], "attempt": uuid.uuid4().hex}
    new = wait(lambda: resume.replace_editor(app, pid, replacement))
    wait(lambda: next(w for w in capture(pid) if w["id"] == new)["editor"]["views"] == old["editor"]["views"])
    assert next(w for w in capture(pid) if w["id"] == current[1]["id"]) == current[1]
    before = capture(pid)
    token = remember(app, pid, path)
    close(pid, before[0]["id"]); exited(pid)
    assert resume.refresh_departure(path, token, resume.departure_windows(), final=True)
    assert resume.cancel_departure(path, token)
    saved = renamed.read_text(); renamed.unlink()
    assert restore(path, off, token)["status"] == "documents-missing"
    pid = next(w["pid"] for w in resume.window_snapshot() if w["app"] == app)
    renamed.write_text(saved)
    assert restore(path, off, token, manual=True)["status"] == "documents-opened"
    current = capture(pid)
    owner = next(w for w in current if str(renamed) in editor.paths(w["editor"]))
    assert editor.document_scroll(owner["editor"], str(renamed)) == [50, 0, 120, False]
    select_tab(pid, renamed, window_number(pid, renamed))
    wait(lambda: editor.document_scroll(next(w for w in capture(pid) if w["id"] == owner["id"])["editor"], str(renamed)) == [50, 0, 120, False])
    # Reject malformed native metadata and late-file requests before changing a view.
    before = capture(pid)
    for scroll in ([], [0, 0, 0], [True, 0, 0, False], [0, -1, 0, False], [0, 0, 2**31, False], [0, 0, 0, 0]):
        bad = copy.deepcopy(before)
        bad[0]["editor"]["views"][0]["scrolls"][0] = scroll
        assert resume.dbus(f"org.kde.{name}-{pid}", "/MainApplication", "org.kde.Kate.Application", "monetEditorWindows", json.dumps(bad)) == ["null"]
        assert resume.dbus(f"org.kde.{name}-{pid}", "/MainApplication", "org.kde.Kate.Application", "monetReopenDocuments",
                           json.dumps({"id": before[0]["id"], "documents": [str(shared)], "scrolls": [scroll]})) == [False]
        assert capture(pid) == before
    finish(pid); editor.cleanup(launch)
    # Wrapped rows keep their canonical top column; recovery must preserve per-view wrap mode.
    for w in pair: w["editor"]["views"][0]["scrolls"] = [[50, 240, 0, True], None]
    launch = editor.start(app, pair, windows=True); pid = launch["pid"]
    current = capture(pid)
    restored = wait(lambda: editor.capture(pid, [dict(a, editor=b["editor"]) for a, b in zip(current, pair)], windows=True))
    assert all(w["editor"]["views"][0]["scrolls"][0][1] > 0 for w in restored), restored
    token = remember(app, pid, path)
    before = capture(pid)
    close(pid, before[0]["id"]); exited(pid)
    assert resume.refresh_departure(path, token, resume.departure_windows(), final=True)
    assert resume.cancel_departure(path, token)
    assert restore(path, off, token)["status"] == "documents-opened"
    pid = next(w["pid"] for w in resume.window_snapshot() if w["app"] == app)
    restored = capture(pid)
    assert [w["editor"]["views"] for w in restored] == [w["editor"]["views"] for w in before], (before, restored)
    finish(pid); editor.cleanup(launch)
    for file in files: file.write_text("short")
    launch = editor.start(app, pair, windows=True); pid = launch["pid"]
    current = capture(pid)
    restored = wait(lambda: editor.capture(pid, [dict(a, editor=b["editor"]) for a, b in zip(current, pair)], windows=True))
    wait(lambda: all(w["editor"]["views"][0]["scrolls"][0][:3] == [0, 0, 0] for w in capture(pid)))
    finish(pid); editor.cleanup(launch)


def selections(app, name, multi=False):
    case = name + ("-multicaret" if multi else "")
    # Expose the native view action to accessibility in this disposable profile.
    # KMainWindow's D-Bus actions do not include the embedded editor's actions.
    toolbar = folder / "data/kxmlgui5/katepart/katepart5ui.rc"
    toolbar.parent.mkdir(parents=True, exist_ok=True)
    toolbar.write_text('<gui name="KatePartView" version="112"><ToolBar name="mainToolBar" noMerge="1">'
                       '<Action name="file_save"/><Action name="file_save_as"/><Action name="edit_undo"/>'
                       '<Action name="edit_redo"/><Action name="edit_select_all"/><Action name="select_char_right"/></ToolBar></gui>')
    files = [folder / (case + "-selection-%d.txt" % i) for i in range(3)]
    text = "".join(f"Line {i:03d}: café 😀 several words here.\n" for i in range(30))
    for file in files: file.write_text(text)
    shared = files[2]
    ordinary = {"block": False, "cursor": [0, 0], "range": [0, 0, 0, 12]}
    rectangular = {"block": True, "cursor": [1, 18], "range": [1, 18, 3, 5]}
    hidden = [{"block": False, "cursor": [2, 3], "range": [2, 3, 4, 8]},
              {"block": True, "cursor": [5, 70], "range": [5, 2, 8, 70]}]
    continued = dict(ordinary, cursor=[0, 1], range=[0, 1, 0, 12])
    if multi:
        ordinary = dict(ordinary, anchor=[0, 12], secondary=[
            {"cursor": [2, 3], "range": [2, 3, 2, 8], "anchor": [2, 8]},
            {"cursor": [4, 2], "range": None, "anchor": None}])
        rectangular = {"block": False, "cursor": [0, 0], "range": None, "anchor": None,
                       "secondary": [{"cursor": [3, 4], "range": [3, 4, 3, 9], "anchor": [3, 9]}]}
        hidden = [dict(hidden[0], anchor=[4, 8], secondary=[
                    {"cursor": [6, 3], "range": [6, 3, 6, 8], "anchor": [6, 8]}]),
                  {"block": False, "cursor": [8, 20], "range": [5, 2, 8, 20], "anchor": [5, 2],
                   "secondary": [{"cursor": [10, 1], "range": None, "anchor": None}]}]
        continued = dict(ordinary, cursor=[0, 1], range=[0, 1, 0, 12], secondary=[
            {"cursor": [2, 4], "range": [2, 4, 2, 8], "anchor": [2, 8]},
            {"cursor": [4, 3], "range": [4, 2, 4, 3], "anchor": [4, 2]}])
    pair = [{"id": "{" + str(uuid.uuid4()) + "}", "editor": {"views": [{
        "documents": [str(file), str(shared)], "active": 0, "cursor": 0, "cursors": [None, 0],
        "scrolls": [[0, 0, 0, False], [0, 0, 0, False]], "selections": [selection, hidden[i]]}],
        "active": 0, "layout": 0}} for i, (file, selection) in enumerate(zip(files, (ordinary, rectangular)))]
    launch = editor.start(app, pair, windows=True); pid = launch["pid"]
    current = capture(pid)
    request = [dict(a, editor=b["editor"]) for a, b in zip(current, pair)]
    restored = wait(lambda: editor.capture(pid, request, windows=True))
    assert [w["editor"]["views"][0]["selections"] for w in restored] == [w["editor"]["views"][0]["selections"] for w in pair], restored
    assert len([n for n in nodes(pid) if (n.get_accessible_id() or "").endswith(".KateViewInternal")]) == 2
    first = next(n for n in texts(pid) if n.get_accessible_id().startswith("QApplication.MainWindow#1."))
    assert Atspi.Text.get_n_selections(first) == 1
    selected = Atspi.Text.get_selection(first, 0)
    assert Atspi.Text.get_text(first, selected.start_offset, selected.end_offset) == text[:12]
    # A real selection at caret zero must protect the view from a repeated request.
    changed = copy.deepcopy(restored)
    changed[0]["editor"]["views"][0]["selections"][0] = dict(ordinary, range=[0, 1, 0, 2])
    assert editor.capture(pid, changed, windows=True) == restored
    path, off = folder / (case + "-selection-trip.json"), folder / "off"
    token = remember(app, pid, path)
    save_as(pid)
    renamed = folder / (case + "-selection-renamed.txt")
    save_path(pid, renamed); wait(lambda: renamed.is_file()); files[0] = renamed
    for cycle in range(2):
        if cycle: token = remember(app, pid, path)
        before = capture(pid)
        close(pid, before[0]["id"]); exited(pid)
        assert resume.refresh_departure(path, token, resume.departure_windows(), final=True)
        assert resume.cancel_departure(path, token)
        assert restore(path, off, token)["status"] == "documents-opened"
        pid = next(w["pid"] for w in resume.window_snapshot() if w["app"] == app)
        restored = capture(pid)
        assert [w["editor"]["views"] for w in restored] == [w["editor"]["views"] for w in before], (before, restored)
        assert len([n for n in nodes(pid) if (n.get_accessible_id() or "").endswith(".KateViewInternal")]) == 2
    # Continue the backwards selection with the editor's actual Shift+Right action.
    resume.kwin_script("const w=workspace.windowList().find(w=>String(w.internalId)==%s);"
                       "w.frameGeometry={x:0,y:0,width:1050,height:600};workspace.activeWindow=w;reply(true);"
                       % json.dumps(restored[0]["id"]))
    def continue_selection():
        buttons = [n for n in nodes(pid) if n.get_role() == Atspi.Role.PUSH_BUTTON
                   and n.get_accessible_id().startswith("QApplication.MainWindow#1.") and n.get_name() == "Select Character Right"
                   and n.get_state_set().contains(Atspi.StateType.SHOWING)]
        if len(buttons) == 1:
            press(buttons[0])
            return True
    wait(continue_selection)  # Native toolbar merging can retire an accessibility node.
    wait(lambda: editor.document_selection(capture(pid)[0]["editor"], str(renamed)) == continued)
    moved = capture(pid)
    assert editor.capture(pid, restored, windows=True) == moved
    for i in range(2):
        select_tab(pid, shared, window_number(pid, files[i]))
        assert editor.document_selection(capture(pid)[i]["editor"], str(shared)) == hidden[i]
    current = capture(pid); old = current[0]
    close(pid, old["id"]); wait(lambda: len(frames(pid)) == 1)
    request = {"id": old["id"], "anchor": current[1]["id"], "editor": old["editor"], "attempt": uuid.uuid4().hex}
    new = wait(lambda: resume.replace_editor(app, pid, request))
    returned = capture(pid)
    assert next(w for w in returned if w["id"] == new)["editor"]["views"] == old["editor"]["views"]
    assert next(w for w in returned if w["id"] == current[1]["id"]) == current[1]
    token = remember(app, pid, path)
    before = capture(pid)
    close(pid, before[0]["id"]); exited(pid)
    assert resume.refresh_departure(path, token, resume.departure_windows(), final=True)
    assert resume.cancel_departure(path, token)
    renamed.unlink()
    assert restore(path, off, token)["status"] == "documents-missing"
    pid = next(w["pid"] for w in resume.window_snapshot() if w["app"] == app)
    renamed.write_text(text)
    assert restore(path, off, token, manual=True)["status"] == "documents-opened"
    owner = next(w for w in capture(pid) if str(renamed) in editor.paths(w["editor"]))
    expected = continued
    assert editor.document_selection(owner["editor"], str(renamed)) == expected
    select_tab(pid, renamed, window_number(pid, renamed))
    assert editor.document_selection(next(w for w in capture(pid) if w["id"] == owner["id"])["editor"], str(renamed)) == expected
    before = capture(pid)
    for selection in ({}, dict(ordinary, range=[1, 0, 0, 1]), dict(ordinary, cursor=[True, 0]),
                      dict(ordinary, block=1), dict(ordinary, range=[0, -1, 1, 0]),
                      dict(ordinary, cursor=[0, 2**31]), dict(ordinary, text="must not be accepted")):
        bad = copy.deepcopy(before)
        bad[0]["editor"]["views"][0]["selections"][0] = selection
        assert resume.dbus(f"org.kde.{name}-{pid}", "/MainApplication", "org.kde.Kate.Application", "monetEditorWindows", json.dumps(bad)) == ["null"]
        assert resume.dbus(f"org.kde.{name}-{pid}", "/MainApplication", "org.kde.Kate.Application", "monetReopenDocuments",
                           json.dumps({"id": before[0]["id"], "documents": [str(shared)], "selections": [selection]})) == [False]
        assert capture(pid) == before
    assert all(file.read_text() == text for file in files)
    if multi:
        # Retry can create a narrow window whose toolbar actions overflow.
        resume.kwin_script("const w=workspace.windowList().find(w=>String(w.internalId)==%s);"
                           "w.frameGeometry={x:0,y:0,width:1050,height:600};workspace.activeWindow=w;reply(true);"
                           % json.dumps(owner["id"]))
        prior = capture(pid)
        number = window_number(pid, renamed)
        def select_all():
            buttons = [n for n in nodes(pid) if n.get_role() == Atspi.Role.PUSH_BUTTON
                       and n.get_accessible_id().startswith(f"QApplication.MainWindow#{number}.") and n.get_name() == "Select All"
                       and n.get_state_set().contains(Atspi.StateType.SHOWING)]
            if len(buttons) == 1: press(buttons[0]); return True
        wait(select_all)
        first = next(n for n in texts(pid) if n.get_accessible_id().startswith(f"QApplication.MainWindow#{number}."))
        assert Atspi.Text.remove_selection(first, 0)
        assert Atspi.Text.set_caret_offset(first, 0)
        cleared = capture(pid)
        owner = next(w for w in cleared if str(renamed) in editor.paths(w["editor"]))
        assert editor.document_selection(owner["editor"], str(renamed)) is None
        assert editor.capture(pid, prior, windows=True) == cleared
    finish(pid); editor.cleanup(launch)
    # Native clamping keeps a selection within a shortened normal document.
    for file in files: file.write_text("short")
    pair[0]["editor"]["views"][0]["documents"][0] = str(renamed)
    pair[1]["editor"]["views"][0]["selections"][0] = ordinary
    launch = editor.start(app, pair, windows=True); pid = launch["pid"]
    current = capture(pid)
    restored = wait(lambda: editor.capture(pid, [dict(a, editor=b["editor"]) for a, b in zip(current, pair)], windows=True))
    assert all(w["editor"]["views"][0]["selections"][0]["range"] == [0, 0, 0, 5] for w in restored), restored
    select_tab(pid, shared, 2)
    if multi:
        selected = editor.document_selection(capture(pid)[1]["editor"], str(shared))
        assert selected is None
        assert any(Atspi.Text.get_caret_offset(n) == 5 and content(n) == "short" for n in texts(pid))
    else:
        assert editor.document_selection(capture(pid)[1]["editor"], str(shared)) == dict(hidden[1], cursor=[0, 70], range=[0, 2, 0, 70])
    select_tab(pid, shared, 1)
    assert editor.document_selection(capture(pid)[0]["editor"], str(shared)) is None
    assert any(Atspi.Text.get_caret_offset(n) == 5 and content(n) == "short" for n in texts(pid))
    assert all(file.read_text() == "short" for file in files)
    finish(pid); editor.cleanup(launch)
    toolbar.unlink()
    print(name, "multiple cursors and anchors" if multi else "ordinary selections", "selection direction, rectangular mode, lazy shared views and Retry verified", flush=True)


def folding(app, name, persistent=False):
    case = name + ("-persistent" if persistent else "")
    toolbar = folder / "data/kxmlgui5/katepart/katepart5ui.rc"
    toolbar.parent.mkdir(parents=True, exist_ok=True)
    toolbar.write_text('<gui name="KatePartView" version="112"><ToolBar name="mainToolBar" noMerge="1">'
                       '<Action name="file_save"/><Action name="file_save_as"/>'
                       '<Action name="folding_toggle_current"/><Action name="folding_expandtoplevel"/></ToolBar></gui>')
    files = [folder / (case + "-folding-%d.py" % i) for i in range(3)]
    text = 'def outer():\n    if True:\n        value = "café 😀"\n        print(value)\n    return 1\n\ndef sibling():\n    return 2\n\n'
    text += ''.join('# More lines %d\n' % i for i in range(70))
    for file in files: file.write_text(text)
    shared = files[2]
    def digest(file):
        data = file.read_bytes()
        return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    outer = dict(startLine=0, startColumn=0, endLine=5, endColumn=0, flags=2)
    inner = dict(startLine=1, startColumn=4, endLine=3, endColumn=20, flags=2)
    other = dict(startLine=6, startColumn=0, endLine=8, endColumn=0, flags=2)
    if persistent:
        for span in (outer, inner, other): span["flags"] = 3
    def folds(ranges):
        return dict(checksum=digest(shared), ranges=ranges)
    hidden = [folds([inner]), folds([outer, inner, other])]
    pair = [{"id": "{" + str(uuid.uuid4()) + "}", "editor": {"views": [{
        "documents": [str(file), str(shared)], "active": 0, "cursor": 0, "cursors": [None, 0],
        "foldings": [folds(ranges), hidden[i]]}], "active": 0, "layout": 0}}
        for i, (file, ranges) in enumerate(zip(files, ([outer, inner], [other])))]
    launch = editor.start(app, pair, windows=True); pid = launch["pid"]
    current = capture(pid)
    restored = wait(lambda: editor.capture(pid, [dict(a, editor=b["editor"]) for a, b in zip(current, pair)], windows=True))
    assert [w["editor"]["views"][0]["foldings"] for w in restored] == [w["editor"]["views"][0]["foldings"] for w in pair], restored
    assert len([n for n in nodes(pid) if (n.get_accessible_id() or "").endswith(".KateViewInternal")]) == 2
    # An edit before Save As must get the newly saved checksum in the final receipt.
    first = next(n for n in texts(pid) if n.get_accessible_id().startswith("QApplication.MainWindow#1."))
    extra = '# Saved during switching\n'
    assert first.get_editable_text_iface().insert_text(Atspi.Text.get_character_count(first), extra, len(extra))
    assert Atspi.Text.set_caret_offset(first, 0)
    path, off = folder / (case + "-folding-trip.json"), folder / "off"
    token = remember(app, pid, path)
    save_as(pid)
    renamed = folder / (case + "-folding-renamed.py")
    save_path(pid, renamed); wait(lambda: renamed.is_file()); files[0] = renamed
    expected = dict(checksum=digest(renamed), ranges=[outer, inner])
    assert editor.document_folding(capture(pid)[0]["editor"], str(renamed)) == expected
    for cycle in range(2):
        if cycle: token = remember(app, pid, path)
        before = capture(pid)
        close(pid, before[0]["id"]); exited(pid)
        assert resume.refresh_departure(path, token, resume.departure_windows(), final=True)
        assert resume.cancel_departure(path, token)
        assert restore(path, off, token)["status"] == "documents-opened"
        pid = next(w["pid"] for w in resume.window_snapshot() if w["app"] == app)
        restored = capture(pid)
        assert [w["editor"]["views"] for w in restored] == [w["editor"]["views"] for w in before], (before, restored)
        assert len([n for n in nodes(pid) if (n.get_accessible_id() or "").endswith(".KateViewInternal")]) == 2
    resume.kwin_script("const w=workspace.windowList().find(w=>String(w.internalId)==%s);"
                       "w.frameGeometry={x:0,y:0,width:1050,height:600};workspace.activeWindow=w;reply(true);"
                       % json.dumps(restored[0]["id"]))
    def view_action(label):
        def activate():
            buttons = [n for n in nodes(pid) if n.get_role() == Atspi.Role.PUSH_BUTTON
                       and n.get_accessible_id().startswith("QApplication.MainWindow#1.") and n.get_name() == label
                       and n.get_state_set().contains(Atspi.StateType.SHOWING)]
            if len(buttons) == 1: press(buttons[0]); return True
        wait(activate)
    view_action("Toggle Current Node")
    parent_open = [dict(outer, flags=1), inner] if persistent else [inner]
    wait(lambda: editor.document_folding(capture(pid)[0]["editor"], str(renamed)) == dict(expected, ranges=parent_open))
    if persistent:
        first = next(n for n in texts(pid) if n.get_accessible_id().startswith("QApplication.MainWindow#1."))
        assert Atspi.Text.set_caret_offset(first, len(text.splitlines(True)[0]) + 4)
        view_action("Toggle Current Node")
        assert Atspi.Text.set_caret_offset(first, 0)
    else:
        view_action("Unfold Toplevel Nodes")
    fully_open = [dict(outer, flags=1), dict(inner, flags=1)] if persistent else []
    wait(lambda: editor.document_folding(capture(pid)[0]["editor"], str(renamed)) == dict(expected, ranges=fully_open))
    unfolded = capture(pid)
    assert editor.capture(pid, restored, windows=True) == unfolded  # Unfolding at caret zero is a later user choice.
    for i in range(2):
        select_tab(pid, shared, window_number(pid, files[i]))
        assert editor.document_folding(capture(pid)[i]["editor"], str(shared)) == hidden[i]
    current = capture(pid); old = current[0]
    close(pid, old["id"]); wait(lambda: len(frames(pid)) == 1)
    new = wait(lambda: resume.replace_editor(app, pid, {"id": old["id"], "anchor": current[1]["id"],
                           "editor": old["editor"], "attempt": "f" * 32}))
    returned = capture(pid)
    assert next(w for w in returned if w["id"] == new)["editor"]["views"] == old["editor"]["views"]
    assert next(w for w in returned if w["id"] == current[1]["id"]) == current[1]
    token = remember(app, pid, path); before = capture(pid)
    close(pid, before[0]["id"]); exited(pid)
    assert resume.refresh_departure(path, token, resume.departure_windows(), final=True)
    assert resume.cancel_departure(path, token)
    shared.unlink()
    assert restore(path, off, token)["status"] == "documents-missing"
    pid = next(w["pid"] for w in resume.window_snapshot() if w["app"] == app)
    shared.write_text(text)
    assert restore(path, off, token, manual=True)["status"] == "documents-opened"
    for i, file in enumerate(files[:2]):
        number = window_number(pid, file)
        select_tab(pid, shared, number)
        owner = next(w for w in capture(pid) if str(file) in editor.paths(w["editor"]))
        assert editor.document_folding(owner["editor"], str(shared)) == hidden[i]
    before = capture(pid)
    bad_foldings = [{}, folds([dict(inner, flags=True)]), folds([outer, dict(inner, endLine=9)]),
                    folds([outer, outer]), folds([dict(inner, endColumn=2**31)]), dict(hidden[0], text="private"),
                    folds([dict(outer, startLine=i, endLine=3000-i) for i in range(65)])]
    for bad_folding in bad_foldings:
        bad = copy.deepcopy(before); bad[0]["editor"]["views"][0]["foldings"][0] = bad_folding
        assert resume.dbus(f"org.kde.{name}-{pid}", "/MainApplication", "org.kde.Kate.Application", "monetEditorWindows", json.dumps(bad)) == ["null"]
        assert resume.dbus(f"org.kde.{name}-{pid}", "/MainApplication", "org.kde.Kate.Application", "monetReopenDocuments",
                           json.dumps({"id": before[0]["id"], "documents": [str(shared)], "foldings": [bad_folding]})) == [False]
        assert capture(pid) == before
    assert [file.read_text() for file in files] == [text + extra, text, text]
    finish(pid); editor.cleanup(launch)
    # Changed files must not inherit ranges with an obsolete checksum, even on lazy creation.
    for file in files: file.write_text('changed\n')
    pair[0]["editor"]["views"][0]["documents"][0] = str(renamed)
    launch = editor.start(app, pair, windows=True); pid = launch["pid"]
    current = capture(pid)
    wait(lambda: editor.capture(pid, [dict(a, editor=b["editor"]) for a, b in zip(current, pair)], windows=True))
    for i, file in enumerate(files[:2]):
        owner = capture(pid)[i]
        assert not editor.document_folding(owner["editor"], str(file))["ranges"]
        assert editor.document_folding(owner["editor"], str(shared)) is None
        select_tab(pid, shared, i + 1)
        assert editor.document_folding(capture(pid)[i]["editor"], str(shared)) == dict(checksum=digest(shared), ranges=[])
    assert all(file.read_text() == 'changed\n' for file in files)
    finish(pid); editor.cleanup(launch); toolbar.unlink()
    print(name, "persistent" if persistent else "ordinary", "nested folding, Save As, lazy shared views, later unfolding and Retry verified", flush=True)


proof = {}
for app, name in editor.EDITORS.items():
    selections(app, name, multi=True)
    folding(app, name, persistent=True)
    file = folder / (name + "-shared.txt")
    file.write_text("Saved shared document.\n")
    state = {"views": [{"documents": [str(file)], "active": 0, "cursor": 0}], "active": 0, "layout": 0}
    pair = [{"id": "{" + str(uuid.uuid4()) + "}", "editor": copy.deepcopy(state)} for _ in range(2)]
    launch = editor.start(app, pair, windows=True)
    pid = launch["pid"]
    before = capture(pid)
    for index, window in enumerate(before):
        rect = {"x": 20 + index * 530, "y": 25 + index * 70, "width": 490, "height": 500}
        resume.kwin_script("const w=workspace.windowList().find(w=>String(w.internalId)==%s);"
                           "w.frameGeometry=%s;reply(true);" % (json.dumps(window["id"]), json.dumps(rect)))
    time.sleep(.5)
    path, off = folder / (name + "-trip.json"), folder / "off"
    token = remember(app, pid, path)
    saved_frames = {w["id"]: w for w in resume.read_state(path)["groups"][app][0]["windows"]}
    unsaved = "Shared unsaved during automatic departure: " + name + "\n"
    assert wait(lambda: texts(pid))[0].get_editable_text_iface().set_text_contents(unsaved)
    wait(lambda: shared_text(pid, unsaved))
    close(pid, before[0]["id"])
    button(pid, "Cancel")
    assert [w["id"] for w in capture(pid)] == [w["id"] for w in before]
    assert resume.cancel_departure(path, token)
    assert restore(path, off, token)["status"] == "already-running"
    assert [w["id"] for w in capture(pid)] == [w["id"] for w in before]
    wait(lambda: shared_text(pid, unsaved))
    assert file.read_text() == "Saved shared document.\n"

    # A new switch commits Save As and the first save of an untitled tab to their windows.
    token = remember(app, pid, path)
    save_as(pid)
    renamed = folder / (name + "-renamed.txt")
    save_path(pid, renamed)
    wait(lambda: renamed.is_file())
    first_text = "First save during automatic departure: " + name + "\n"
    assert resume.dbus(f"org.kde.{name}-{pid}", "/MainApplication", "org.kde.Kate.Application",
                       "openInput", first_text, "") == [True]
    close(pid, before[1]["id"])
    button(pid, "Save")
    first = folder / (name + "-first.txt")
    save_path(pid, first)
    exited(pid)
    assert resume.refresh_departure(path, token, resume.departure_windows(), final=True)
    final = resume.read_state(path)["groups"][app][0]["editor_windows"]
    assert all(str(renamed) in editor.paths(w["editor"]) and str(file) not in editor.paths(w["editor"]) for w in final)
    assert sum(str(first) in editor.paths(w["editor"]) for w in final) == 1
    assert first.read_text() == first_text and renamed.read_text() == unsaved
    assert resume.cancel_departure(path, token)
    result = restore(path, off, token)
    assert result["status"] == "documents-opened", result
    current_frames = [w for w in resume.window_snapshot() if w["app"] == app]
    assert len(current_frames) == 2 and len({w["pid"] for w in current_frames}) == 1
    returned_pid = current_frames[0]["pid"]
    returned = capture(returned_pid)
    assert all(editor.same_layout(a["editor"], b["editor"]) for a, b in zip(final, returned))
    wait(lambda: sorted(content(n) for n in texts(returned_pid)) == sorted([unsaved, first_text]))
    time.sleep(.6)
    placed = {w["id"]: w for w in frames(returned_pid)}
    for old, new in zip(final, returned):
        expected = resume.placed_rect(saved_frames[old["id"]], placed[new["id"]]["area"])
        assert all(abs(placed[new["id"]]["rect"][k] - value) <= 2 for k, value in expected.items()), (expected, placed[new["id"]])
    restore(path, off, token, manual=True)
    assert [w["id"] for w in capture(returned_pid)] == [w["id"] for w in returned]
    finish(returned_pid)
    editor.cleanup(launch)

    # A temporarily missing second window remains a separate empty native window.
    late = folder / (name + "-late.txt")
    late.write_text("Returned second-window document.\n")
    pair[0]["editor"] = state
    pair[1]["editor"] = dict(state, views=[dict(state["views"][0], documents=[str(late)])])
    launch = editor.start(app, pair, windows=True)
    pid = launch["pid"]
    original = capture(pid)
    for index, window in enumerate(original):
        # Leave room for KWrite's document-view minimum width when its empty pane gains a file.
        rect = {"x": 20 + index * 400, "y": 30 + index * 60, "width": 620, "height": 520}
        resume.kwin_script("const w=workspace.windowList().find(w=>String(w.internalId)==%s);"
                           "w.frameGeometry=%s;reply(true);" % (json.dumps(window["id"]), json.dumps(rect)))
    time.sleep(.5)
    token = remember(app, pid, path)
    close(pid, original[0]["id"])
    exited(pid)
    assert resume.refresh_departure(path, token, resume.departure_windows(), final=True)
    assert resume.cancel_departure(path, token)
    late.unlink()
    parked = file.with_suffix(".parked")
    file.rename(parked)
    result = restore(path, off, token)
    assert result["status"] == "documents-missing" and result["missingCount"] == 2, result
    assert not any(w["app"] == app for w in resume.window_snapshot())
    parked.rename(file)
    result = restore(path, off, token, manual=True)
    assert result["status"] == "documents-missing" and result["missing"] == [late.name], result
    group = resume.read_state(path)["groups"][app][0]
    owner = group["editor_owners"][original[1]["id"]]
    returned_pid = owner["pid"]
    current = capture(returned_pid)
    assert current[1]["id"] == owner["id"] and current[1]["editor"] is None
    assert not late.exists()
    first_window = copy.deepcopy(current[0])
    before_frames = frames(returned_pid)
    late.write_text("Returned second-window document.\n")
    restore(path, off, token)
    assert capture(returned_pid) == current
    result = restore(path, off, token, manual=True)
    assert result["status"] == "documents-opened", result
    current = capture(returned_pid)
    assert current[0] == first_window
    assert current[1]["id"] == owner["id"] and editor.paths(current[1]["editor"]) == [str(late)]
    after_frames = frames(returned_pid)
    (folder / (name + "-retry-frames.json")).write_text(json.dumps({"before": before_frames, "after": after_frames}, indent=2))
    assert after_frames == before_frames, (before_frames, after_frames)
    wait(lambda: "Returned second-window document.\n" in [content(n) for n in texts(returned_pid)])
    restore(path, off, token, manual=True)
    assert capture(returned_pid) == current
    finish(returned_pid)
    editor.cleanup(launch)
    # A large missing-file set can return to one pane without changing its current layout.
    bulk = [folder / (name + "-bulk-%03d.txt" % i) for i in range(197)]
    for i, document in enumerate(bulk): document.write_text("Late document %d.\n" % i)
    target = copy.deepcopy(state)
    target["views"][0].update(documents=[str(file), str(late), *map(str, bulk)], cursor=5)
    large = [dict(pair[0], editor=target), pair[1]]
    launch = editor.start(app, large, windows=True)
    pid = launch["pid"]
    original = capture(pid)
    assert sum(len(v["documents"]) for w in original for v in w["editor"]["views"]) == 200
    assert editor.capture(pid, [dict(original[0], editor=target)], windows=True)
    token = remember(app, pid, path)
    close(pid, original[0]["id"]); exited(pid)
    assert resume.refresh_departure(path, token, resume.departure_windows(), final=True)
    assert resume.cancel_departure(path, token)
    for document in bulk: document.unlink()
    assert restore(path, off, token)["status"] == "documents-missing"
    group = resume.read_state(path)["groups"][app][0]
    assert len(group["pending_windows"][original[0]["id"]]) == 197
    owner = group["editor_owners"][original[0]["id"]]
    pid = owner["pid"]
    current = capture(pid)
    shared_saved = late.read_text()
    shared_view = wait(lambda: [n for n in texts(pid) if content(n) == shared_saved])[0]
    shared_unsaved = "Shared buffer during large Retry: " + name + "\n"
    assert shared_view.get_editable_text_iface().set_text_contents(shared_unsaved)
    wait(lambda: any(content(n) == shared_unsaved for n in texts(pid)))
    resume.kwin_script("workspace.activeWindow=workspace.windowList().find(w=>String(w.internalId)==%s);reply(true);" % json.dumps(current[1]["id"]))
    before_large, before_large_frames = capture(pid), frames(pid)
    for i, document in enumerate(bulk): document.write_text("Late document %d.\n" % i)
    restore(path, off, token)
    assert capture(pid) == before_large
    assert restore(path, off, token, manual=True)["status"] == "documents-opened"
    after_large = capture(pid)
    assert after_large[1] == before_large[1]
    actual, prior = after_large[0]["editor"], before_large[0]["editor"]
    assert actual["layout"] == prior["layout"] and actual["active"] == prior["active"]
    assert actual["views"][0] == dict(prior["views"][0], documents=prior["views"][0]["documents"] + list(map(str, bulk)),
                                      cursors=prior["views"][0]["cursors"] + [None] * len(bulk),
                                      scrolls=prior["views"][0]["scrolls"] + [None] * len(bulk),
                                      foldings=prior["views"][0]["foldings"] + [None] * len(bulk))
    assert frames(pid) == before_large_frames
    assert late.read_text() == shared_saved
    wait(lambda: any(content(n) == shared_unsaved for n in texts(pid)))
    extra = folder / (name + "-over-budget.txt")
    extra.write_text("This must stay unopened.\n")
    assert resume.reopen_editor(app, pid, owner["id"], [str(extra)]) is False
    assert capture(pid) == after_large
    restore(path, off, token, manual=True)
    assert capture(pid) == after_large
    action(pid, name, "file_save_all")
    wait(lambda: late.read_text() == shared_unsaved)
    saved_large = capture(pid)
    def without_folding(windows):
        result = copy.deepcopy(windows)
        for window in result:
            for view in window["editor"]["views"]: view.pop("foldings", None)
        return result
    assert without_folding(saved_large) == without_folding(after_large)
    saved_bytes = late.read_bytes()
    assert editor.document_folding(saved_large[1]["editor"], str(late)) == {
        "checksum": hashlib.sha1(b'blob ' + str(len(saved_bytes)).encode() + b'\0' + saved_bytes).hexdigest(), "ranges": []}
    close(pid, owner["id"])
    wait(lambda: len(frames(pid)) == 1)
    replacement_request = {"id": owner["id"], "anchor": after_large[1]["id"], "editor": actual, "attempt": uuid.uuid4().hex}
    replacement_id = wait(lambda: resume.replace_editor(app, pid, replacement_request))
    assert replacement_id not in ("closed", owner["id"], after_large[1]["id"])
    replaced = capture(pid)
    assert editor.same_layout(next(w for w in replaced if w["id"] == replacement_id)["editor"], actual)
    assert next(w for w in replaced if w["id"] == saved_large[1]["id"]) == saved_large[1]
    finish(pid); editor.cleanup(launch)

    # Empty source windows are intentional, unlike windows whose files are unavailable.
    empty = [dict(w, editor=None) for w in pair]
    launch = editor.start(app, empty, windows=True)
    pid = launch["pid"]
    original = capture(pid)
    assert all(w["editor"] is None for w in original)
    token = remember(app, pid, path)
    close(pid, original[0]["id"])
    exited(pid)
    assert resume.refresh_departure(path, token, resume.departure_windows(), final=True)
    assert resume.cancel_departure(path, token)
    assert restore(path, off, token)["status"] == "documents-opened"
    returned_pid = next(w["pid"] for w in resume.window_snapshot() if w["app"] == app)
    assert all(w["editor"] is None for w in capture(returned_pid))
    finish(returned_pid)
    editor.cleanup(launch)
    hidden_cursors(app, name)
    scroll_positions(app, name)
    selections(app, name)
    folding(app, name)
    proof[name] = {"automatic_capture_departure_recovery": True, "cancel_preserved_shared_unsaved_buffers": True,
                   "save_as_and_first_save_in_correct_windows": True, "exact_window_placement": True,
                   "missing_window_placeholder": True, "late_file_retry_exact_owner": True,
                   "automatic_and_repeated_retry_no_duplicates": True,
                   "all_missing_waits_without_blank_launch": True, "intentional_empty_windows_reopen": True,
                   "large_late_batch_preserves_pane_sibling_and_unsaved_buffer": True,
                   "full_200_entry_group_captured_and_recovered": True, "process_budget_overflow_refused": True,
                   "large_closed_window_replacement": True,
                   "hidden_cursors_save_as_repeat_recovery_and_replacement": True,
                   "shared_document_positions_per_pane_and_window": True,
                   "late_file_positions_preserve_selection": True,
                   "hidden_views_stay_lazy_and_live_cursors_preserved": True,
                   "malformed_cursor_requests_refused_and_truncated_files_clamped": True,
                   "scrolls_save_as_repeat_hidden_shared_replacement_and_late_retry": True,
                   "scroll_only_user_changes_preserved": True, "wrapped_top_column_and_mode_preserved": True,
                   "invalid_scrolls_rejected_and_shorter_files_clamped": True,
                   "selections_save_as_lazy_shared_replacement_and_retry": True,
                   "selection_direction_and_rectangular_virtual_columns": True,
                   "later_selections_preserved_invalid_refused_and_short_files_clamped": True,
                   "folding_save_as_lazy_shared_replacement_and_retry": True,
                   "nested_folding_and_later_unfolding_preserved": True,
                   "changed_files_and_malformed_folding_refused": True,
                   "persistent_folding_flags_survive_recovery_and_unfolding": True,
                   "multiple_cursors_and_anchors_save_as_lazy_shared_replacement_retry": True}
    (folder / "proof.json").write_text(json.dumps(proof, indent=2))
    print(name, "automatic group checks passed", flush=True)
(root / "auto-groups-verified.json").write_text(json.dumps({"folder": str(folder), "checks": proof}, indent=2))
print(json.dumps(proof, indent=2))
