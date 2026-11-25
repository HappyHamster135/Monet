"""Per-output sleep and wake on the open Wayland Display page."""
from pathlib import Path

from PySide6.QtCore import QAbstractListModel, QModelIndex, QSocketNotifier, Qt, Slot
from PySide6.QtGui import QGuiApplication


def load_protocol():
    import ctypes as c

    api = c.CDLL(str(Path(__file__).with_name("libmonetdisplaypower.so")))
    connection = c.c_void_p
    api.visitor_type = c.CFUNCTYPE(None, c.c_uint32, c.c_char_p, c.c_char_p, c.c_int)
    signatures = {
        "open": ([], connection),
        "close": ([connection], None),
        "fd": ([connection], c.c_int),
        "dispatch": ([connection], c.c_int),
        "flush": ([connection], c.c_int),
        "outputs": ([connection, api.visitor_type], None),
        "set": ([connection, c.c_uint32, c.c_char_p, c.c_int], c.c_int),
    }
    for name, (args, result) in signatures.items():
        fn = getattr(api, "monet_power_" + name)
        fn.argtypes, fn.restype = args, result
    return api


class DisplayPower(QAbstractListModel):
    first_role = int(Qt.ItemDataRole.UserRole) + 1
    names = (b"outputId", b"connector", b"displayLabel", b"powered")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api = None
        self.connection = None
        self.readable = self.writable = None
        self.rows = []

    def roleNames(self):
        return dict(enumerate(self.names, self.first_role))

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role):
        field = role - self.first_role
        if index.isValid() and 0 <= index.row() < len(self.rows) and 0 <= field < len(self.names):
            return self.rows[index.row()][field]

    @Slot(bool)
    def observe(self, active):
        if not active:
            self.close()
            return
        if self.connection or not QGuiApplication.platformName().startswith("wayland"):
            return
        try:
            self.api = self.api or load_protocol()
        except OSError:
            return
        self.connection = self.api.monet_power_open()
        if self.connection:
            fd = self.api.monet_power_fd(self.connection)
            self.readable = QSocketNotifier(fd, QSocketNotifier.Type.Read, self)
            self.writable = QSocketNotifier(fd, QSocketNotifier.Type.Write, self)
            self.readable.activated.connect(self.dispatch)
            self.writable.activated.connect(self.flush)
            self.flush()

    def flush(self):
        if self.connection:
            result = self.api.monet_power_flush(self.connection)
            if result < 0:
                self.close()
            else:
                self.writable.setEnabled(result == 0)

    def dispatch(self):
        if not self.connection:
            return
        if self.api.monet_power_dispatch(self.connection) < 0:
            self.close()
            return
        rows = []

        @self.api.visitor_type
        def visit(identifier, name, description, on):
            rows.append((identifier, name.decode(), description.decode(errors="replace"), bool(on)))

        self.api.monet_power_outputs(self.connection, visit)
        rows.sort(key=lambda row: row[1])
        if [row[0] for row in rows] != [row[0] for row in self.rows]:
            self.beginResetModel()
            self.rows = rows
            self.endResetModel()
        else:
            for i, row in enumerate(rows):
                if self.rows[i] != row:
                    self.rows[i] = row
                    self.dataChanged.emit(self.index(i, 0), self.index(i, 0), [])
        self.flush()

    @Slot("uint", str, bool, result=bool)
    def setPower(self, identifier, connector, on):
        if not self.connection:
            return False
        accepted = self.api.monet_power_set(self.connection, identifier, connector.encode(), on)
        self.flush()
        return bool(accepted and self.connection)

    @Slot()
    def close(self):
        if self.connection:
            for notifier in (self.readable, self.writable):
                notifier.setEnabled(False)
                notifier.activated.disconnect()
                notifier.deleteLater()
            self.api.monet_power_close(self.connection)
            self.connection = self.readable = self.writable = None
        if self.rows:
            self.beginResetModel()
            self.rows = []
            self.endResetModel()
