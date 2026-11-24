"""Identify local listening sockets and their processes. Only the UI sends signals."""
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys

PROC = Path("/proc")


@dataclass(frozen=True)
class Process:
    pid: int
    start: int
    parent: int
    uid: int
    name: str


def process(pid):
    try:
        with (PROC / str(pid) / "stat").open("rb") as stream:
            record = stream.read()
            uid = os.fstat(stream.fileno()).st_uid
        # The kernel encloses comm in parentheses. The name can itself contain
        # spaces, parentheses, or newlines. Field 22 is the start time in ticks.
        head, _, tail = record.rpartition(b") ")
        number, name = head.split(b" (", 1)
        fields = tail.split()
        if int(number) != pid or fields[0] in (b"Z", b"X"):
            return None
        name = "".join(ch if ch.isprintable() else "�" for ch in os.fsdecode(name))
        return Process(pid, int(fields[19]), int(fields[1]), uid, name)
    except (OSError, IndexError, ValueError):
        return None


def holds_socket(pid, fd, inode):
    try:
        return os.readlink(PROC / str(pid) / "fd" / str(fd)) == f"socket:[{inode}]"
    except OSError:
        return False


@dataclass(frozen=True)
class Listener:
    protocol: str
    address: str
    port: int
    inode: int
    fd: int = -1
    owner: Process | None = None

    @classmethod
    def from_json(cls, row):
        owner = row["owner"]
        return cls(**dict(row, owner=Process(**owner) if owner else None))

    def current(self):
        other = process(self.owner.pid) if self.owner else None
        return (other is not None and other.start == self.owner.start
                and other.uid == self.owner.uid and holds_socket(other.pid, self.fd, self.inode))


def parse_listeners(output):
    rows = []
    cache = {}
    for line in output.splitlines():
        columns = line.split(None, 6)
        if len(columns) < 6 or columns[0] not in ("tcp", "udp"):
            continue
        address, sep, port = columns[4].rpartition(":")
        if not sep or not port.isdecimal():
            continue
        details = columns[6] if len(columns) > 6 else ""
        matches = re.findall(r"(?:^|\s)ino:(\d+)\s+sk:", details)
        inode = int(matches[-1]) if matches else 0
        base = (columns[0].upper(), address.removeprefix("[").removesuffix("]"), int(port), inode)
        seen = set()
        for pid_text, fd_text in re.findall(r",pid=(\d+),fd=(\d+)\)", details):
            pid, fd = int(pid_text), int(fd_text)
            if pid in seen or not inode or not holds_socket(pid, fd, inode):
                continue
            if pid not in cache:
                cache[pid] = process(pid)
            if cache[pid] is not None:
                rows.append(Listener(*base, fd, cache[pid]))
                seen.add(pid)
        if not seen:
            rows.append(Listener(*base))
    return sorted(rows, key=lambda x: (x.port, x.protocol, x.address, x.owner.pid if x.owner else 0))


def listeners(port=None):
    # Numeric local TCP listeners and bound, unconnected UDP sockets. Only
    # look up process owners when displaying the full list.
    command = ["ss", "-Hlntupe"] if port is None else ["ss", "-Hlntue", "sport", "=", f":{port}"]
    result = subprocess.run(command, capture_output=True, timeout=12, check=True, env=dict(os.environ, LC_ALL="C"))
    return parse_listeners(result.stdout.decode(errors="replace"))


def listening(entry):
    # A UDP socket can connect and stop listening without changing its inode.
    return any(row.inode == entry.inode and row.protocol == entry.protocol and row.address == entry.address
               for row in listeners(entry.port))


def processes():
    rows = []
    for folder in PROC.iterdir():
        if folder.name.isdecimal():
            member = process(int(folder.name))
            if member:
                rows.append(member)
    return rows


def process_tree(root):
    by_parent = {}
    for member in processes():
        by_parent.setdefault(member.parent, []).append(member)
    live = process(root.pid)
    if live is None or live.start != root.start or live.uid != root.uid:
        raise ProcessLookupError(root.pid)
    out, seen, pending = [], set(), [live]
    while pending:
        member = pending.pop()
        if member.pid in seen:
            continue
        seen.add(member.pid)
        out.append(member)
        pending.extend(sorted(by_parent.get(member.pid, ()), key=lambda p: p.pid, reverse=True))
    return out


def selected_branch(members, selected, children):
    branch = []
    included = set()
    for member in members:
        if member == selected or (children and member.parent in included):
            branch.append(member)
            included.add(member.pid)
    return branch


@contextmanager
def pinned_selection(listener, selected, members, children, ui_pid):
    """Pin the confirmed subtree's process identities before delivering signals."""
    if not members or (listener and not listener.current()):
        raise ProcessLookupError()
    tree = {member.pid: member for member in members}
    root = members[0]
    if tree.get(selected.pid) != selected or (listener and
            (root.pid, root.start, root.uid) != (listener.owner.pid, listener.owner.start, listener.owner.uid)):
        raise ProcessLookupError()

    def still_related(member):
        live = process(member.pid)
        return (live is not None and live.start == member.start and live.uid == member.uid
                and (member.pid == root.pid or live.parent == member.parent))

    ancestor = selected
    visited = set()
    while ancestor.pid != root.pid:
        if ancestor.pid in visited or not still_related(ancestor) or ancestor.parent not in tree:
            raise ProcessLookupError()
        visited.add(ancestor.pid)
        ancestor = tree[ancestor.parent]

    targets = selected_branch(members, selected, children)
    if any(m.uid != os.getuid() or m.pid in (1, ui_pid, os.getpid()) for m in targets):
        raise PermissionError()
    handles = {}
    try:
        for member in targets:
            if member != selected and member.parent not in handles:
                continue
            try:
                fd = os.pidfd_open(member.pid)
            except ProcessLookupError:
                if member == selected:
                    raise
                continue
            if still_related(member):
                handles[member.pid] = fd
            else:
                os.close(fd)
                if member == selected:
                    raise ProcessLookupError()
        if not still_related(root) or (listener and not (listening(listener) and listener.current())):
            raise ProcessLookupError()
        yield handles, len(targets)
    finally:
        for fd in handles.values():
            os.close(fd)


def end_processes(listener, selected, members, children, sig, ui_pid):
    if sig not in (signal.SIGTERM, signal.SIGKILL):
        raise ValueError("Invalid process action")
    with pinned_selection(listener, selected, members, children, ui_pid) as (handles, count):
        sent = 0
        for fd in reversed(handles.values()):
            try:
                signal.pidfd_send_signal(fd, sig)
                sent += 1
            except (ProcessLookupError, PermissionError):
                pass
        return sent, count - sent


def window_apps(helpers, pids):
    """Use the desktop IDs of windows belonging to these exact host PIDs."""
    from importlib.machinery import SourceFileLoader
    from importlib.util import module_from_spec, spec_from_loader
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtDBus import QDBusConnection
    app = QCoreApplication.instance() or QCoreApplication([])
    registered = QDBusConnection.sessionBus().interface().isServiceRegistered("org.kde.KWin")
    if not registered.isValid() or not registered.value():
        return {}
    loader = SourceFileLoader("monet_resume", str(helpers / "monet-resume"))
    resume = module_from_spec(spec_from_loader(loader.name, loader))
    loader.exec_module(resume)
    pairs = resume.kwin_script("const wanted=new Set(" + json.dumps(list(pids)) + ");"
                               "reply(windows().filter(w=>wanted.has(w.pid)).map(w=>[w.pid,appId(w)]))")
    matches = {}
    for pid, app_id in pairs:
        if pid in pids and resume.APP_ID.fullmatch(app_id):
            matches.setdefault(pid, set()).add(app_id)
    return {pid: next(iter(ids)) for pid, ids in matches.items() if len(ids) == 1}


def desktop_entry(app_id):
    try:
        from gi.repository.GioUnix import DesktopAppInfo
    except ImportError:
        from gi.repository.Gio import DesktopAppInfo
    try:
        return DesktopAppInfo.new(app_id)
    except TypeError:
        # PyGObject reports a NULL constructor when the desktop file vanished.
        return None


def restart_app(listener, selected, members, ui_pid, helpers, expected):
    from gi.repository import GLib
    if window_apps(helpers, {selected.pid}).get(selected.pid) != expected:
        raise ProcessLookupError()
    entry = desktop_entry(expected)
    if not entry or entry.get_is_hidden():
        return "unavailable"
    with pinned_selection(listener, selected, members, False, ui_pid) as (handles, _):
        fd = handles[selected.pid]
        exited = select.poll()
        exited.register(fd, select.POLLIN)
        signal.pidfd_send_signal(fd, signal.SIGTERM)
        if not exited.poll(12000):
            return "still-running"
    try:
        return "launched" if entry.launch([], None) else "launch-failed"
    except GLib.Error:
        return "launch-failed"


def main(args):
    if args in (["list"], ["processes"]):
        rows = listeners() if args == ["list"] else processes()
        return [asdict(row) for row in rows]
    if len(args) == 3 and args[0] == "tree":
        target = process(int(args[1]))
        if not target or target.start != int(args[2]):
            raise ProcessLookupError()
        return [asdict(member) for member in process_tree(target)]
    if len(args) == 2 and args[0] == "apps":
        matches = window_apps(Path(args[1]), set(json.load(sys.stdin)))
        return {pid: app_id for pid, app_id in matches.items() if (entry := desktop_entry(app_id)) and not entry.get_is_hidden()}
    if args == ["end"] or (len(args) == 2 and args[0] == "restart"):
        request = json.load(sys.stdin)
        listener = Listener.from_json(request["listener"]) if request["listener"] else None
        members = [Process(**member) for member in request["members"]]
        selected = Process(**request["selected"])
        if args[0] == "restart":
            return restart_app(listener, selected, members, os.getppid(), Path(args[1]), request["app"])
        sig = signal.SIGKILL if request["force"] else signal.SIGTERM
        return end_processes(listener, selected, members, request["children"], sig, os.getppid())
    raise ValueError("Unknown operation")


if __name__ == "__main__":
    try:
        print(json.dumps(main(sys.argv[1:])))
    except ProcessLookupError:
        sys.exit("Process exited.")
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        sys.exit(str(exc) or type(exc).__name__)
