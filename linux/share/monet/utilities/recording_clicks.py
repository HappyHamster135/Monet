"""Editable zoom suggestions from primary clicks inside a Spectacle take."""
from dataclasses import astuple
import json
from math import hypot
import os
from pathlib import Path
import socket
import struct

from PySide6.QtCore import QFileDevice, QIODevice, QSaveFile, QStandardPaths
from PySide6.QtDBus import QDBusConnection
from PySide6.QtNetwork import QLocalServer
from recording_zoom import Zoom


class ClickGroups:
    def __init__(self):
        self.items = []

    def add(self, ms, x, y):
        if ms < 0 or not (0 <= x < 1 and 0 <= y < 1):
            return
        if self.items:
            first, last, cx, cy = self.items[-1]
            if ms < last:
                return
            if ms - last < 1600 and hypot(cx-x, cy-y) < .135:
                self.items[-1] = (first, ms, cx, cy)
                return
            if ms - last < 480:
                return
        # Bound preview and FFmpeg expression size on all-day captures.
        if len(self.items) < 256:
            self.items.append((ms, ms, x, y))


def suggestions(groups, duration):
    # The panel indicator itself may be the last click of a full-screen take.
    usable = [g for g in groups if 0 <= g[0] <= duration - 480]
    result = []
    for i, (first, last, x, y) in enumerate(usable):
        start = max(0, first - 400)
        end = min(duration, last + 1800)
        if i:
            start = max(start, (usable[i-1][1] + first) // 2)
        if i + 1 < len(usable):
            end = min(end, (last + usable[i+1][0]) // 2)
        if end > start:
            result.append(Zoom(start, end, x, y))
    return result


class TakeZooms:
    """Store only edits and clustered points; a renamed video keeps its edits."""
    def __init__(self, video):
        stat = video.stat()
        key = f"{stat.st_dev:x}-{stat.st_ino:x}-{stat.st_size:x}-{stat.st_mtime_ns:x}"
        root = Path(QStandardPaths.writableLocation(QStandardPaths.GenericStateLocation))
        self.path = root / "monet" / "recording-zooms" / (key + ".json")
        self.groups = []
        self.edited = None

    def read(self):
        try:
            if self.path.stat().st_size > 1024*1024:
                return False
            data = json.loads(self.path.read_bytes())
            groups = data["groups"]
            if len(groups) > 256:
                return False
            last = -1
            for start, end, x, y in groups:
                if not (isinstance(start, int) and isinstance(end, int) and last < start <= end
                        and 0 <= x < 1 and 0 <= y < 1):
                    return False
                last = end
            edits = data["edited"]
            edited = None if edits is None else [Zoom(*row) for row in edits]
            if edited and any(a.end > b.start for a, b in zip(edited, edited[1:])):
                return False
            self.groups, self.edited = groups, edited
            return True
        except (OSError, KeyError, ValueError, TypeError):
            return False

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            data = json.dumps(dict(groups=self.groups,
                                   edited=None if self.edited is None else [astuple(z) for z in self.edited])).encode()
            output = QSaveFile(str(self.path))
            if not output.open(QIODevice.WriteOnly):
                return False
            if not output.setPermissions(QFileDevice.ReadOwner | QFileDevice.WriteOwner):
                output.cancelWriting()
                return False
            return output.write(data) == len(data) and output.commit()
        except OSError:
            return False


class ClickReceiver:
    """A private socket for the compositor recording this editor's child."""
    def __init__(self, job):
        self.server = QLocalServer(job)
        self.server.setSocketOptions(QLocalServer.AbstractNamespaceOption)
        self.server.setMaxPendingConnections(2)
        self.server.newConnection.connect(self.accept)
        self.socket = None
        self.ready = False
        self.groups = ClickGroups()
        job.started.connect(lambda: self.server.listen(f"monet-recording-clicks-{os.getuid()}-{job.processId()}"))

    def accept(self):
        peer = self.server.nextPendingConnection()
        if peer is None:
            return
        bus = QDBusConnection.sessionBus().interface()
        pid = bus.servicePid("org.kde.KWin") if bus else None
        try:
            with socket.fromfd(peer.socketDescriptor(), socket.AF_UNIX, socket.SOCK_STREAM) as fd:
                owner, uid, _ = struct.unpack("3i", fd.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            valid = pid is not None and pid.isValid() and owner == pid.value() and uid == os.getuid()
        except (TypeError, OSError, ValueError):
            valid = False
        if not valid or self.socket is not None:
            peer.abort()
            peer.deleteLater()
            return
        self.socket = peer
        peer.setReadBufferSize(65536)
        peer.readyRead.connect(self.read)
        self.read()

    def read(self):
        while self.socket and self.socket.canReadLine():
            line = bytes(self.socket.readLine(96)).strip()
            if line == b"ready":
                self.ready = True
            elif self.ready:
                try:
                    ms, x, y = line.split()
                    self.groups.add(int(ms), float(x), float(y))
                except (ValueError, OverflowError):
                    continue

    def finish(self):
        self.read()
        self.server.close()
        if self.socket:
            self.socket.close()
        return self.groups.items if self.ready else None
