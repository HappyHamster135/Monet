"""Local port ownership, shared sockets and confirmed process identities."""
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

MODULE = Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"
sys.path.insert(0, str(MODULE))
import local_ports as ports


class LocalPorts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        listening = patch.object(ports, "listening", return_value=True)
        self.listening = listening.start()
        self.addCleanup(listening.stop)
        proc = patch.object(ports, "PROC", self.root)
        proc.start()
        self.addCleanup(proc.stop)
        self.parent = self.add(2020, 100, name="fixture) tcp")
        self.child = self.add(2021, 2020)
        self.grandchild = self.add(2022, 2021)
        self.other = self.add(2023, 400)
        for member in (self.parent, self.child):
            (self.root / str(member.pid) / 'fd' / '7').symlink_to('socket:[4413]')
        self.entry = ports.Listener("TCP", "127.0.0.1", 1234, 4413, 7, self.parent)

    def add(self, pid, parent, start=7000, name="fixture"):
        folder = self.root / str(pid)
        (folder / "fd").mkdir(parents=True, exist_ok=True)
        # fields 3..22, with the start tick in field 22.
        (folder / "stat").write_text(f"{pid} ({name}) S {parent} " + "0 " * 17 + str(start))
        return ports.process(pid)

    def test_parse_ipv4_ipv6_shared_and_unknown_owners(self):
        rows = ports.parse_listeners('tcp LISTEN 0 128 127.0.0.1:1234 0.0.0.0:* '
                                     'users:(("fixture) tcp",pid=2020,fd=7),("child",pid=2021,fd=7)) ino:4413 sk:2\n'
                                     'udp UNCONN 0 0 [fe80::1%eth0]:5353 [::]:* uid:77 ino:1231 sk:d5\n'
                                     'tcp LISTEN 0 128 *:443 *:* users:(("gone",pid=2020,fd=8)) ino:879 sk:278\n')
        self.assertEqual([(r.port, r.owner.pid if r.owner else None) for r in rows],
                         [(443, None), (1234, 2020), (1234, 2021), (5353, None)])
        self.assertEqual(rows[-1].address, "fe80::1%eth0")
        self.assertEqual(rows[1].owner.name, "fixture) tcp")

    def test_tree_omits_unrelated_and_after_confirmation_children(self):
        members = ports.process_tree(self.parent)
        self.assertEqual(members, [self.parent, self.child, self.grandchild])
        self.add(2234, self.parent.pid)
        self.assertEqual(ports.selected_branch(members, self.child, True), [self.child, self.grandchild])
        self.assertEqual(ports.selected_branch(members, self.child, False), [self.child])

    def end(self, members, selected, *, children=True):
        return ports.end_processes(self.entry, selected, members, children, signal.SIGTERM, os.getpid())

    def test_pins_and_signals_only_confirmed_descendants_children_first(self):
        members = ports.process_tree(self.parent)
        with patch.object(os, "pidfd_open", side_effect=lambda pid: pid+5) as pin, \
             patch.object(signal, "pidfd_send_signal") as send, patch.object(os, "close") as close:
            self.assertEqual(self.end(members, self.child), (2, 0))
            self.assertEqual([c.args[0] for c in pin.call_args_list], [2021, 2022])
            self.assertEqual([c.args[0] for c in send.call_args_list], [2027, 2026])
            self.assertEqual(close.call_count, 2)

    def test_stale_port_pid_and_reparented_children_are_skipped(self):
        members = ports.process_tree(self.parent)
        self.add(self.grandchild.pid, self.other.pid)
        with patch.object(os, "pidfd_open", side_effect=lambda pid: pid) as pin, \
             patch.object(signal, "pidfd_send_signal") as send, patch.object(os, "close"):
            self.assertEqual(self.end(members, self.child), (1, 1))
            self.assertEqual(send.call_count, 1)
            self.add(self.child.pid, self.parent.pid, start=9999)
            with self.assertRaises(ProcessLookupError):
                self.end(members, self.child)
            (self.root / str(self.parent.pid) / "fd/7").unlink()
            pin.reset_mock()
            with self.assertRaises(ProcessLookupError):
                self.end(members, self.parent)
            pin.assert_not_called()
            self.assertEqual(send.call_count, 1)

    def test_process_only_action_refuses_a_reused_pid_or_protected_member(self):
        members = ports.process_tree(self.parent)
        with patch.object(signal, "pidfd_send_signal") as send:
            with self.assertRaises(PermissionError):
                ports.end_processes(None, self.parent, members, True, signal.SIGTERM, self.grandchild.pid)
            self.add(self.parent.pid, self.parent.parent, start=9000)
            with patch.object(os, "pidfd_open", return_value=80), patch.object(os, "close"):
                with self.assertRaises(ProcessLookupError):
                    ports.end_processes(None, self.parent, members, False, signal.SIGTERM, -1)
            send.assert_not_called()

    def test_restart_does_not_launch_when_the_app_is_still_alive(self):
        try:
            import gi
        except ImportError:
            self.skipTest("Requires the desktop launcher bindings")
        entry = Mock()
        entry.get_is_hidden.return_value = False
        with patch.object(ports, "window_apps", return_value={self.parent.pid: "fixture.desktop"}), \
             patch.object(ports, "desktop_entry", return_value=entry), \
             patch.object(os, "pidfd_open", return_value=91), patch.object(os, "close") as close, \
             patch.object(signal, "pidfd_send_signal") as send, patch.object(ports.select, "poll") as poll:
            poll.return_value.poll.return_value = []
            result = ports.restart_app(None, self.parent, [self.parent], -1, self.root, "fixture.desktop")
            self.assertEqual(result, "still-running")
            send.assert_called_once_with(91, signal.SIGTERM)
            close.assert_called_once_with(91)
            entry.launch.assert_not_called()
            with self.assertRaises(ProcessLookupError):
                ports.restart_app(None, self.parent, [self.parent], -1, self.root, "wrong.desktop")
            self.assertEqual(send.call_count, 1)
