#!/usr/bin/python3
"""Real return-controller scenario in the isolated Monet PDF VM desktop."""
from importlib.machinery import SourceFileLoader
import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import tempfile
import time
import gi
from PySide6.QtGui import QGuiApplication, QPainter, QPdfWriter

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi
Atspi.set_timeout(600, 800)

app = QGuiApplication([])
root = Path(__file__).parent
r = SourceFileLoader("pdf_return_fixture", str(root / "monet-resume")).load_module()
pdf = r.pdf_helper()
launchers, sessions, owned_pids = [], [], set()
confirmations = 0


def confirm_tabs():
    """Answer only the observed native multi-tab warning in this fixture's processes."""
    global confirmations
    desktop = Atspi.get_desktop(0)
    if desktop is None:
        return
    def click(node, depth=0):
        if depth > 4:
            return False
        if node.get_role() == Atspi.Role.PUSH_BUTTON and node.get_name() == "Close Tabs":
            assert node.get_action_iface().do_action(0)
            return True
        return any(click(node.get_child_at_index(i), depth+1) for i in range(node.get_child_count()))
    for i in range(desktop.get_child_count()):
        process = desktop.get_child_at_index(i)
        if process.get_process_id() not in owned_pids:
            continue
        for j in range(process.get_child_count()):
            dialog = process.get_child_at_index(j)
            if dialog.get_role() == Atspi.Role.DIALOG and dialog.get_name().startswith("Confirm Close"):
                if click(dialog):
                    confirmations += 1


def wait(predicate, label):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        app.processEvents()
        confirm_tabs()
        value = predicate()
        if value:
            return value
        time.sleep(.2)
    raise AssertionError(label)


def frames():
    return [w for w in r.window_snapshot() if w["app"] == r.PDF]


def no_generic(*args):
    raise AssertionError("PDF recovery used a generic app launch")


def launch(state, competing=False):
    receipt = pdf.prepare(state)
    sessions.append(receipt)
    launchers.append(pdf.start(receipt))
    if competing:
        launchers.append(pdf.start(receipt))
    pid = wait(lambda: pdf.discover(receipt), "Private native process")
    owned_pids.add(pid)
    wait(lambda: any(w["pid"] == pid for w in frames()), "Native PDF window")
    states = wait(lambda: pdf.capture(pid, windows=True), "Native PDF metadata")
    assert len(states) == 1 and pdf.restored(state, states[0]["document"]), states
    assert pdf.launching(receipt), "The launcher must retain its lock while the native process runs"
    assert pdf.start(receipt) is None
    return pid


try:
    with tempfile.TemporaryDirectory(prefix="monet-pdf-return-") as folder:
        work = Path(folder)
        paths = [work / name for name in ("Water lilies.pdf", "Late å %.pdf", "Other.pdf")]
        for path in paths:
            writer = QPdfWriter(str(path))
            paint = QPainter(writer)
            for page in range(1, 5):
                if page > 1:
                    assert writer.newPage()
                paint.drawText(100, 100, "Synthetic return page " + str(page))
            paint.end()
            del writer
        hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        def state(items, active=0):
            return {"tabs": [{"path": str(paths[i]), "page": page, "modified": False} for i, page in items], "active": active}
        states = [state([(0, 3), (1, 2), (0, 4)], 1), state([(0, 1), (2, 4)]), state([(2, 2)])]
        pids = [launch(s, competing=i == 0) for i, s in enumerate(states)]
        assert len(frames()) == 3, frames()
        initial = frames()
        rectangles = [{"x": 30 + i*320, "y": 40 + i*80, "width": 700-i*20, "height": 590-i*20} for i in range(3)]
        for pid, rect in zip(pids, rectangles):
            r.kwin_script("const w=windows().find(w=>w.pid===" + str(pid) + "); w.frameGeometry=" + json.dumps(rect) + "; reply(true);")
        time.sleep(.5)
        initial = frames()
        checkpoint = r.checkpoint([r.PDF], initial)
        path, off = work / "trip.json", work / "disabled"
        r.atomic_write(path, checkpoint)
        for pid in pids[:2]:
            windows = r.departure_windows()
            target = next(w for w in windows if w.get("pid") == pid)
            r.prepare_pdf_close(path, checkpoint["id"], target, windows)
            print("Waiting for native Close Tabs confirmation", pid, flush=True)
            r.departure_windows(target["id"])
            wait(lambda: not any(w["pid"] == pid for w in frames()), "Protected normal PDF close")
        assert r.refresh_departure(path, checkpoint["id"], r.departure_windows(), final=True)
        final = r.read_state(path)
        assert all(not g.get("closing") and not g.get("final_unverified") for g in final["groups"][r.PDF])
        hidden = paths[1].with_suffix(".unplugged")
        paths[1].rename(hidden)
        survivor = next(w for w in frames() if w["pid"] == pids[2])
        survivor_state = pdf.capture(pids[2], windows=True)
        assert r.cancel_departure(path, checkpoint["id"])
        r.restore(path, off, lambda: [], lambda _: True, no_generic)
        returned = frames()
        owned_pids.update(w["pid"] for w in returned)
        assert len(returned) == 3, returned
        assert pdf.capture(pids[2], windows=True) == survivor_state
        current_survivor = next(w for w in returned if w["id"] == survivor["id"])
        assert current_survivor["rect"] == survivor["rect"]
        saved = r.read_state(path)
        groups = saved["groups"][r.PDF]
        partial = next(g for g in groups if g.get("pending"))
        assert partial["pending"] == [1], groups
        owner = partial["pdf_owner"]
        available = pdf.capture(owner["pid"], windows=True)[0]["document"]
        assert [t["page"] for t in available["tabs"]] == [3, 4], available
        report = r.read_return(path)["items"][r.PDF]
        assert report["documents"] == 5 and report["missingCount"] == 1, report
        for group in groups:
            original, target = group["windows"][0], group["pdf_owner"]
            current = next(w for w in returned if w["id"] == target["id"])
            assert all(abs(current["rect"][k]-original["rect"][k]) <= 1 for k in ("x", "y", "width", "height")), (original, current)
        hidden.rename(paths[1])
        r.restore(path, off, lambda: [], lambda _: True, no_generic)
        assert pdf.capture(owner["pid"], windows=True)[0]["document"] == available
        append = pdf.append
        def lose_reply(pid, request):
            result = append(pid, request)
            assert result == "opened", result
            raise OSError("Synthetic controller loss after native append")
        pdf.append = lose_reply
        try:
            r.restore(path, off, lambda: [], lambda _: True, no_generic, selected=r.PDF)
        finally:
            pdf.append = append
        saved = r.read_state(path)
        assert any(g.get("pdf_retry") for g in saved["groups"][r.PDF]), saved
        appended = pdf.capture(owner["pid"], windows=True)
        assert len(appended[0]["document"]["tabs"]) == 3
        ids = {w["id"] for w in frames()}
        restarted = SourceFileLoader("pdf_return_restarted", str(root / "monet-resume")).load_module()
        restarted.restore(path, off, lambda: [], lambda _: True, no_generic)
        assert not path.exists(), restarted.read_state(path)
        assert pdf.capture(owner["pid"], windows=True) == appended
        restarted.restore(path, off, lambda: [], lambda _: True, no_generic)
        assert {w["id"] for w in frames()} == ids
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest for p, digest in hashes.items())
        proof = {"protected_close_final_receipts": True, "cancelled_switch_return": True,
                 "surviving_window_unchanged": True, "duplicate_tabs_and_pages": True,
                 "missing_file_pending": True, "explicit_retry_only": True,
                 "lost_append_reply_controller_reload": True, "no_duplicate_windows_or_tabs": True,
                 "window_geometry": True, "exclusive_private_launch": True, "saved_contents_preserved": True,
                 "native_close_confirmations": confirmations,
                 "before": checkpoint, "after": returned, "report": restarted.read_return(path)}
        Path(os.environ["MONET_PDF_RETURN_EVIDENCE"]).write_text(json.dumps(proof, indent=2))
        print("PDF return controller: protected close, cancellation, pages/geometry, survivor, missing file, exclusive launch and interrupted retry passed", flush=True)
finally:
    print("Closing synthetic PDF windows; native Close Tabs confirmations may be shown", flush=True)
    for w in frames():
        if w["pid"] in owned_pids:
            r.departure_windows(w["id"])
    wait(lambda: not any(w["pid"] in owned_pids for w in frames()), "Synthetic PDF windows closed")
    for pid in launchers:
        if pid:
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass  # subprocess may already have reaped the completed launcher.
    for receipt in sessions:
        pdf.cleanup(receipt)
