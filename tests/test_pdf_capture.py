"""Okular patch validation; live tab/window coverage belongs to the native VM fixture."""
from importlib.machinery import SourceFileLoader
from pathlib import Path
import copy
import json
import os
import tempfile
import unittest
from unittest.mock import patch as mock_patch


ROOT = Path(__file__).resolve().parents[1]
patch = SourceFileLoader("pdf_patch", str(ROOT / "image/pdf-recovery/patch.py")).load_module()
pdf = SourceFileLoader("pdf_session", str(ROOT / "linux/libexec/monet-pdf-session")).load_module()


class Metadata(unittest.TestCase):
    def state(self):
        return {"tabs": [{"path": "/home/j/Water lilies % å.pdf", "page": 3, "modified": False}], "active": 0}

    def test_local_documents_empty_windows_and_duplicate_tabs(self):
        state = self.state()
        self.assertTrue(pdf.valid(state))
        state["tabs"].append(dict(state["tabs"][0], page=7, modified=True))
        state["active"] = 1
        self.assertTrue(pdf.valid(state))
        self.assertTrue(pdf.valid({"tabs": [], "active": -1}))
        self.assertFalse(pdf.valid({"tabs": [], "active": 0}))

    def test_rejects_unsafe_paths_pages_and_unsupported_metadata(self):
        for key, values in {"path": ["https://site/a.pdf", "../a.pdf", "/tmp/../a.pdf", "//remote/a.pdf", "/tmp/a\n.pdf", "/a\ud800", "/" + "a"*4096],
                            "page": [0, -1, True, 1.5, 1000001], "modified": [1, "yes", None]}.items():
            for value in values:
                with self.subTest(key=key, value=repr(value)):
                    state = self.state()
                    state["tabs"][0][key] = value
                    self.assertFalse(pdf.valid(state))
        state = self.state()
        state["tabs"][0]["contents"] = "must not enter checkpoint"
        self.assertFalse(pdf.valid(state))

    def test_complete_unique_window_identity_and_bounds(self):
        state = self.state()
        item = {"id": "{11111111-2222-3333-4444-555555555555}", "document": state}
        self.assertTrue(pdf.valid_windows([item]))
        self.assertFalse(pdf.valid_windows([item, copy.deepcopy(item)]))
        self.assertFalse(pdf.valid_windows([dict(item, id="{00000000-0000-0000-0000-000000000000}")]))
        self.assertFalse(pdf.valid_windows([dict(item, id="not-an-id")]))
        self.assertFalse(pdf.valid_windows([item]*17))
        self.assertFalse(pdf.valid(dict(state, active=True)))
        self.assertFalse(pdf.valid(dict(state, tabs=state["tabs"]*33)))


class Patch(unittest.TestCase):
    def tree(self, root):
        (root / "shell").mkdir()
        (root / "shell/shell.h").write_text("#include <QAction>\n    Q_SCRIPTABLE bool canOpenDocs(int numDocs, int desktop);\n    bool queryClose() override;\n    void openNewTab(const QUrl &url, const QString &serializedOptions);")
        (root / "shell/CMakeLists.txt").write_text("add_executable(okular ${okular_SRCS})")
        (root / "shell/shell.cpp").write_text('''#include "shell.h"
bool Shell::queryClose()
{
    for (int i = 0; i < m_tabs.size(); ++i) {
        KParts::ReadWritePart *const part = m_tabs[i].part;

        // To resolve confusion
        if (!part->queryClose()) {
            return false;
        }
    }
    return true;
}
        QDBusConnection::sessionBus().registerObject(QStringLiteral("/okularshell"), this, QDBusConnection::ExportScriptableSlots);
void Shell::readProperties(const KConfigGroup &group)
{
}
void Shell::openNewTab(const QUrl &url, const QString &serializedOptions)
{
    if (activateTabIfAlreadyOpen) {
    }
}
''')

    def test_patch_is_once_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.tree(root)
            patch.apply(root)
            self.assertIn("monetDocumentWindows", (root / "shell/shell.h").read_text())
            self.assertIn("Shell::monetDocumentState", (root / "shell/shell.cpp").read_text())
            before = {p: p.read_bytes() for p in (root / "shell").iterdir()}
            with self.assertRaises(ValueError):
                patch.apply(root)
            self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_changed_source_does_not_partially_patch(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.tree(root)
            (root / "shell/CMakeLists.txt").write_text("changed target")
            before = {p: p.read_bytes() for p in (root / "shell").iterdir()}
            with self.assertRaises(ValueError):
                patch.apply(root)
            self.assertEqual(before, {p: p.read_bytes() for p in before})


class Receipts(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.runtime = Path(self.folder.name)
        self.runtime.chmod(0o700)
        (self.runtime / "monet-pdf").mkdir(mode=0o700)
        env = mock_patch.dict(os.environ, XDG_RUNTIME_DIR=str(self.runtime))
        env.start()
        self.addCleanup(env.stop)
        self.token, self.pid = "a" * 32, os.getpid()
        self.window = "{11111111-2222-3333-4444-555555555555}"
        self.path = pdf.departure_path(self.pid, self.token, self.window)
        self.receipt = {"version": 1, "id": self.token, "pid": self.pid, "window": self.window,
                        "app": pdf.APP, "supported": True, "document": Metadata().state()}

    def write(self, value):
        self.path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        self.path.chmod(0o600)

    def read(self):
        return pdf.departure(self.pid, self.token, self.window)

    def test_final_document_and_explicit_unsupported_receipt(self):
        self.write(self.receipt)
        self.assertEqual(self.read(), self.receipt)
        unsupported = dict(self.receipt, supported=False, document=None)
        self.write(unsupported)
        self.assertEqual(self.read(), unsupported)

    def test_receipts_belong_to_exact_trip_process_and_window(self):
        for key, value in {"version": True, "id": "b"*32, "pid": self.pid+1, "window": "wrong",
                           "app": "other.desktop", "supported": 1, "document": None, "extra": 1}.items():
            with self.subTest(key=key):
                self.write(dict(self.receipt, **{key: value}))
                with self.assertRaises(ValueError):
                    self.read()
        self.write(dict(self.receipt, supported=False))
        with self.assertRaises(ValueError):
            self.read()

    def test_nonprivate_links_special_and_oversized_files_are_refused(self):
        self.write(self.receipt)
        self.path.chmod(0o644)
        with self.assertRaises(ValueError):
            self.read()
        self.path.unlink()
        other = self.runtime / "other"
        other.write_text("{}")
        self.path.symlink_to(other)
        with self.assertRaises(OSError):
            self.read()
        self.path.unlink()
        os.mkfifo(self.path, 0o600)
        with self.assertRaises(ValueError):
            self.read()
        self.path.unlink()
        self.path.write_bytes(b" " * 600001)
        self.path.chmod(0o600)
        with self.assertRaises(ValueError):
            self.read()
        self.path.parent.chmod(0o755)
        with self.assertRaises(ValueError):
            self.read()


class PrivateSession(unittest.TestCase):
    def test_retry_request_binds_an_attempt_to_exact_window_and_saved_tab(self):
        state = Metadata().state()
        request = {"window": "{11111111-2222-3333-4444-555555555555}", "attempt": "a"*32,
                   "before": state, "tab": state["tabs"][0]}
        self.assertTrue(pdf.valid_append(request))
        for key, value in {"window": "wrong", "attempt": "short", "before": None, "tab": {}, "extra": 1}.items():
            with self.subTest(key=key):
                self.assertFalse(pdf.valid_append(dict(request, **{key: value})))
        self.assertFalse(pdf.valid_append(dict(request, tab=dict(request["tab"], modified=True))))
        with mock_patch.object(pdf, "endpoint", side_effect=FileNotFoundError):
            self.assertIsNone(pdf.append(os.getpid(), request))
        with mock_patch.object(pdf, "endpoint", return_value=None):
            self.assertIsNone(pdf.append(os.getpid(), request))

    def test_missing_files_keep_duplicate_tabs_and_active_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            available = Path(folder) / "Present å.pdf"
            missing = Path(folder) / "Missing.pdf"
            available.touch()
            state = {"tabs": [{"path": str(available), "page": 2, "modified": True},
                              {"path": str(missing), "page": 3, "modified": False},
                              {"path": str(available), "page": 4, "modified": False}], "active": 2}
            result = pdf.available(state)
            self.assertEqual([t["page"] for t in result["tabs"]], [2, 4])
            self.assertEqual(result["active"], 1)
            self.assertFalse(any(t["modified"] for t in result["tabs"]))
            self.assertTrue(state["tabs"][0]["modified"])
            self.assertEqual(pdf.available(state, [1]), {"tabs": [], "active": -1})
            for pending in ([2, 0], [0, 0], [-1], [3], [True]):
                with self.assertRaises(ValueError):
                    pdf.available(state, pending)

    def test_private_session_does_not_overwrite_native_session_or_preferences(self):
        with tempfile.TemporaryDirectory() as folder, mock_patch.dict(os.environ, XDG_CONFIG_HOME=folder):
            root = Path(folder)
            document = root / "Water lilies å \\.pdf"
            document.touch()
            native = root / "okularrc"
            native.write_text("keep my preferences")
            state = {"tabs": [{"path": str(document), "page": 3, "modified": False}], "active": 0}
            receipt = pdf.prepare(state)
            path = pdf.session_path(receipt)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertIn("MonetDocumentState=", path.read_text())
            self.assertEqual(native.read_text(), "keep my preferences")
            self.assertFalse(pdf.alive(dict(receipt, pid=os.getpid())))
            with mock_patch.object(pdf.subprocess, "Popen") as launch:
                pdf.start(receipt)
                command = launch.call_args.args[0]
                self.assertEqual(command[:2], ["flock", "--nonblock"])
                self.assertEqual(command[2], str(path))
                self.assertEqual(command[3:], ["okular", "--session", path.name[len("okular_"):-1]])
            pdf.cleanup(receipt)
            self.assertFalse(path.exists())
            self.assertTrue(native.exists())
            for name in ("../okularrc", "okular_monet-invalid_", str(native)):
                self.assertIsNone(pdf.session_path({"session": name}))

    def test_confirmation_distinguishes_pages_from_newer_live_work(self):
        state = Metadata().state()
        newer = copy.deepcopy(state)
        newer["tabs"][0]["page"] = 4
        self.assertTrue(pdf.same_documents(state, newer))
        self.assertFalse(pdf.restored(state, newer))
        self.assertTrue(pdf.restored(state, copy.deepcopy(state)))
        self.assertFalse(pdf.same_documents(state, {"tabs": [], "active": -1}))


if __name__ == "__main__":
    unittest.main()
