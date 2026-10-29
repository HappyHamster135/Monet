#!/usr/bin/python3
"""Run the real patched Okular CLI in an isolated Wayland session and synthetic HOME."""
from importlib.machinery import SourceFileLoader
import copy
import json
import os
from pathlib import Path
import signal
import tempfile
import time
from PySide6.QtGui import QGuiApplication, QPainter, QPdfWriter

app = QGuiApplication([])
pdf = SourceFileLoader("pdf_restore_fixture", os.environ["MONET_PDF_HELPER"]).load_module()
config = Path(os.environ["XDG_CONFIG_HOME"])
preferences = config / "okularpartrc"
before_preferences = preferences.read_bytes() if preferences.exists() else None
processes = []


def launch(state, alter=None):
    receipt = pdf.prepare(state)
    if alter:
        path = pdf.session_path(receipt)
        altered = json.dumps(alter, ensure_ascii=True, separators=(",", ":")).replace("\\", "\\\\")
        text = path.read_text()
        path.write_text("\n".join("MonetDocumentState=" + altered if line.startswith("MonetDocumentState=") else line
                                  for line in text.splitlines()) + "\n")
    receipt["launcher"] = pdf.start(receipt)
    processes.append(receipt)
    deadline = time.monotonic() + 25
    last = None
    while time.monotonic() < deadline:
        app.processEvents()
        receipt["pid"] = pdf.discover(receipt)
        last = pdf.capture(receipt["pid"], windows=True) if receipt["pid"] else None
        if pdf.valid_windows(last):
            return receipt, last
        time.sleep(0.15)
    raise AssertionError(("Native window did not become readable", receipt, last))


try:
    # These deliberately disagree with the captured layout.
    preferences.write_text("[General]\nShellOpenFileInTabs=false\nSwitchToTabIfOpen=true\n")
    with tempfile.TemporaryDirectory(prefix="monet-pdf-restore-") as folder:
        root = Path(folder)
        paths = [root / "Water lilies % å \\.pdf", root / "Second.pdf"]
        for path in paths:
            writer = QPdfWriter(str(path))
            paint = QPainter(writer)
            for page in range(1, 5):
                if page > 1:
                    assert writer.newPage()
                paint.drawText(100, 100, "Synthetic restore page " + str(page))
            paint.end()
            del writer
        state = {"tabs": [{"path": str(paths[0]), "page": 3, "modified": False},
                          {"path": str(paths[1]), "page": 2, "modified": False},
                          {"path": str(paths[0]), "page": 4, "modified": False}], "active": 1}
        first, one = launch(state)
        assert len(one) == 1 and pdf.restored(state, one[0]["document"]), one
        second, two = launch(state)
        assert first["pid"] != second["pid"] and one[0]["id"] != two[0]["id"]
        assert len(two) == 1 and pdf.restored(state, two[0]["document"]), two
        assert pdf.capture(first["pid"], windows=True) == one
        assert pdf.alive(first) and pdf.alive(second)
        assert pdf.launching(first) and pdf.start(first) is None
        assert pdf.discover(first) == first["pid"]
        assert not pdf.alive(dict(first, pid=second["pid"]))
        assert [pid for pid in (first["pid"], second["pid"]) if pdf.alive(dict(first, pid=pid))] == [first["pid"]]
        retry = {"window": one[0]["id"], "attempt": "a"*32, "before": state,
                 "tab": dict(state["tabs"][1], page=4)}
        deadline = time.monotonic() + 10
        attempts = 0
        while True:
            attempts += 1
            result = pdf.append(first["pid"], retry)
            if result not in (None, "busy") or time.monotonic() >= deadline:
                break
            # The same request survives a slow open or lost reply, without another append identity.
            app.processEvents()
            time.sleep(0.15)
        assert result == "opened", (result, retry, pdf.capture(first["pid"], windows=True))
        appended = pdf.capture(first["pid"], windows=True)
        assert appended[0]["document"] == {"tabs": state["tabs"] + [retry["tab"]], "active": 1}, appended
        assert pdf.append(first["pid"], retry) == "opened"
        assert pdf.capture(first["pid"], windows=True) == appended
        assert pdf.append(second["pid"], retry) == "closed"
        assert pdf.capture(second["pid"], windows=True) == two
        empty = {"tabs": [], "active": -1}
        blank, windows = launch(empty)
        assert len(windows) == 1 and windows[0]["document"] == empty
        invalid = copy.deepcopy(state)
        invalid["tabs"][1]["page"] = True
        rejected, windows = launch(state, invalid)
        assert len(windows) == 1 and windows[0]["document"] == empty
        missing = copy.deepcopy(state)
        missing["tabs"][1]["path"] = str(root / "Missing.pdf")
        rejected_missing, windows = launch(state, missing)
        assert len(windows) == 1 and windows[0]["document"] == empty
        settings = preferences.read_text()
        assert "ShellOpenFileInTabs=false" in settings and "SwitchToTabIfOpen=true" in settings
        proof = {"first": one, "second": two, "duplicate_tabs": True, "page_positions": True,
                 "active_tab": True, "independent_windows": True, "original_preferences": True,
                 "empty_window": True, "malformed_state_refused": True, "missing_file_preflight": True,
                 "launch_identity": True, "dbus_append_and_lost_reply": True, "wrong_process_append_refused": True,
                 "append_attempts": attempts}
        Path(os.environ["MONET_PDF_RESTORE_EVIDENCE"]).write_text(json.dumps(proof, indent=2))
        print("Native PDF sessions: duplicate tabs, pages, active tab, two windows, preferences, empty/malformed/missing states and launch identity passed", flush=True)
finally:
    for receipt in processes:
        if pdf.alive(receipt):
            os.kill(receipt["pid"], signal.SIGTERM)
        if receipt.get("launcher"):
            try:
                os.waitpid(receipt["launcher"], 0)
            except ChildProcessError:
                pass
        pdf.cleanup(receipt)
    if before_preferences is None:
        preferences.unlink(missing_ok=True)
    else:
        preferences.write_bytes(before_preferences)
