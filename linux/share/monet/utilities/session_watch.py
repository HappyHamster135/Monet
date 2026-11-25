"""Watch a selected file, including replacements and committed SQLite WAL writes."""
import json
from pathlib import Path
import sys

from PySide6.QtCore import QCoreApplication, QFileSystemWatcher, QObject, QSocketNotifier, QTimer
from agents import DATABASE_SUFFIXES, display


def signature(path):
    try:
        st = path.stat()
        return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
    except OSError:
        return None


class Watch(QObject):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.files = [path]
        if path.suffix.lower() in DATABASE_SUFFIXES:
            self.files.append(Path(str(path) + "-wal"))
        self.fs = QFileSystemWatcher(self)
        self.timer = QTimer(self, interval=650, singleShot=True)
        self.timer.timeout.connect(self.update)
        self.fs.fileChanged.connect(self.schedule)
        self.fs.directoryChanged.connect(self.schedule)
        self.last = None
        self.sent = None
        self.update()

    def schedule(self, _):
        if not self.timer.isActive():
            self.timer.start()

    def update(self):
        # Qt drops file watches after rename/unlink. The directory reports recreation.
        parent = self.path.parent
        while parent != parent.parent and not parent.is_dir():
            parent = parent.parent
        desired = {str(parent)}
        for path in self.files:
            if path.is_file():
                desired.add(str(path))
        active = set(self.fs.files() + self.fs.directories())
        if active - desired:
            self.fs.removePaths(sorted(active - desired))
        if desired - active:
            self.fs.addPaths(sorted(desired - active))
        state = tuple(signature(p) for p in self.files)
        if state != self.last:
            self.last = state
            text = display(self.path)
            if text != self.sent:
                self.sent = text
                print(json.dumps(text), flush=True)


if __name__ == "__main__":
    app = QCoreApplication([])
    path = json.loads(sys.stdin.buffer.readline())
    if not isinstance(path, str) or not Path(path).is_absolute():
        sys.exit(2)
    eof = QSocketNotifier(sys.stdin.fileno(), QSocketNotifier.Read)
    eof.activated.connect(app.quit)
    watch = Watch(Path(path))
    sys.exit(app.exec())
