"""Named scratchpads shared by the Utilities windows and the desktop notch."""
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from PySide6.QtCore import QObject, Signal

from actions import tr


class Pads(QObject):
    changed = Signal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.db = None

    def connect(self):
        if self.db is not None:
            return self.db
        directory = Path(os.environ.get("XDG_DATA_HOME") or Path.home()/".local/share") / "monet/scratchpads"
        directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        db = sqlite3.connect(directory / "pads.sqlite3", timeout=1)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            with db:
                version = db.execute("PRAGMA user_version").fetchone()[0]
                if version == 0:
                    db.execute("CREATE TABLE pads (id TEXT PRIMARY KEY, name TEXT NOT NULL, body TEXT NOT NULL, revision INTEGER NOT NULL)")
                    old = self.settings.value("scratchpad", "", type=str)
                    self.add(db, tr("Pad %1").replace("%1", "1"), old)
                    db.execute("PRAGMA user_version=1")
                elif version != 1:
                    raise ValueError("unknown scratchpad format")
        except Exception:
            db.close()
            raise
        self.db = db
        # Migration committed. A deleted migrated note must not survive in the old settings.
        if self.settings.contains("scratchpad"):
            self.settings.remove("scratchpad")
            self.settings.sync()
        return db

    @staticmethod
    def add(db, name, body=""):
        ident = uuid4().hex
        db.execute("INSERT INTO pads VALUES(?,?,?,1)", (ident, name, body))
        return ident

    def next_name(self, db):
        names = {row[0] for row in db.execute("SELECT name FROM pads")}
        for number in range(1, len(names) + 2):
            name = tr("Pad %1").replace("%1", str(number))
            if name not in names:
                return name

    def request(self, action, ident="", revision=0, value=""):
        if not isinstance(ident, str) or type(revision) is not int or not isinstance(value, str):
            return {"ok": False}
        try:
            db = self.connect()
            if action in ("view", "select"):
                result = self.view(db, ident)
                if action == "select":
                    self.settings.setValue("lastScratchpad", result["pad"]["id"])
                return result
            db.execute("BEGIN IMMEDIATE")
            with db:
                row = db.execute("SELECT * FROM pads WHERE id=?", (ident,)).fetchone()
                copied = False
                if action == "new":
                    ident = self.add(db, self.next_name(db))
                elif action == "save":
                    if row and row["body"] == value:
                        return self.view(db, ident)
                    if not row or row["revision"] != revision:
                        # Another open editor changed or deleted this note. Keep both drafts.
                        name = row["name"] if row else tr("Scratchpad")
                        ident = self.add(db, tr("%1 (recovered)").replace("%1", name), value)
                        copied = True
                    else:
                        db.execute("UPDATE pads SET body=?, revision=revision+1 WHERE id=?", (value, ident))
                elif action in ("rename", "delete") and row:
                    if row["revision"] != revision:
                        return dict(self.view(db, ident), ok=False, problem="changed")
                    if action == "rename":
                        name = value.strip()
                        if not name or len(name) > 100 or any(ord(c) < 32 for c in name):
                            return {"ok": False, "problem": "name"}
                        db.execute("UPDATE pads SET name=?, revision=revision+1 WHERE id=?", (name, ident))
                    else:
                        db.execute("DELETE FROM pads WHERE id=?", (ident,))
                        if not db.execute("SELECT 1 FROM pads LIMIT 1").fetchone():
                            self.add(db, self.next_name(db))
                        ident = ""
                else:
                    return {"ok": False, "problem": "gone"}
                result = self.view(db, ident)
            if action == "new":
                self.settings.setValue("lastScratchpad", ident)
            self.changed.emit()
            return dict(result, recovered=copied)
        except (sqlite3.Error, OSError, ValueError, OverflowError):
            return {"ok": False, "problem": "storage"}

    def view(self, db, ident):
        choices = [dict(row) for row in db.execute("SELECT id,name FROM pads ORDER BY rowid")]
        wanted = ident or self.settings.value("lastScratchpad", "")
        row = db.execute("SELECT * FROM pads WHERE id=?", (wanted,)).fetchone()
        if not row:
            row = db.execute("SELECT * FROM pads ORDER BY rowid LIMIT 1").fetchone()
        return {"ok": True, "pads": choices, "pad": dict(row)}

    def for_notch(self, payload):
        try:
            data = json.loads(payload)
            if not isinstance(data, dict) or data.get("action") not in ("view", "select", "new", "save"):
                return '{"ok":false}'
            result = self.request(data["action"], data.get("id", ""), data.get("revision", 0), data.get("value", ""))
        except (ValueError, TypeError):
            return '{"ok":false}'
        return json.dumps(result, ensure_ascii=False)
