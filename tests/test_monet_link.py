from concurrent.futures import ThreadPoolExecutor
import hashlib
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Event
import time
import unittest
from unittest.mock import patch


if sys.platform == "linux":
    SCRIPT = Path(__file__).resolve().parents[1] / "linux/libexec/monet-link"
    LOADER = SourceFileLoader("monet_link", str(SCRIPT))
    SPEC = spec_from_loader(LOADER.name, LOADER)
    link = module_from_spec(SPEC)
    LOADER.exec_module(link)


@unittest.skipUnless(sys.platform == "linux", "requires the Linux Monet Link service")
class MonetLinkSync(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.json"
        self.operator = self.path.with_name("relay.json")
        self.config = {"pair": "a" * 32, "secret": link.encode(bytes(range(32))),
                       "expires": int(time.time()) + 60}
        self.state = link.new_state(self.config)
        self.state["paired"] = True

    def note(self, text):
        return {"type": "note", "text": text, "expires": int(time.time()) + 3600}

    def read(self):
        return json.loads(self.path.read_text())

    def test_queued_note_survives_receipt_arriving_during_send(self):
        first = link.queue(self.state, self.note("Earlier note"))
        original = link.decode(self.state["outbox"][first]["envelope"])
        receipt = link.encrypt(self.config, "phone", first, "receipt", hashlib.sha256(original).digest())
        link.save(self.path, self.state)
        waiting, respond = Event(), Event()

        def slow_relay(config, method, route):
            if (method, route) == ("GET", "/v1/outbox/" + first):
                waiting.set()
                self.assertTrue(respond.wait(5))
                return 200, receipt
            self.assertEqual((method, route), ("GET", "/v1/inbox"))
            return 200, b"[]"

        with patch.object(link, "request", slow_relay), patch.object(link, "input_text", return_value="New note"), \
                ThreadPoolExecutor(max_workers=2) as workers:
            sync = workers.submit(link.watch_once, self.path, self.operator)
            try:
                self.assertTrue(waiting.wait(2))
                workers.submit(link.change, self.path, self.operator, "send").result(timeout=2)
                self.assertEqual([item["status"] for item in self.read()["outbox"].values()], ["Queued", "Queued"])
            finally:
                respond.set()
            self.assertTrue(sync.result(timeout=2))
        sent = self.read()["outbox"]
        self.assertEqual(sent.pop(first)["status"], "Received")
        (_, item), = sent.items()
        self.assertEqual(item["status"], "Queued")

    def test_forget_keeps_a_late_inbound_note_from_restoring_local_state(self):
        identifier = "b" * 32
        route = "/v1/inbox/" + identifier
        note = link.encrypt(self.config, "phone", identifier, "message", link.pack(self.note("In flight")))
        link.save(self.path, self.state)
        waiting, respond = Event(), Event()

        def slow_relay(config, method, resource):
            if (method, resource) == ("GET", "/v1/inbox"):
                return 200, link.pack([identifier])
            self.assertEqual((method, resource), ("GET", route))
            waiting.set()
            self.assertTrue(respond.wait(5))
            return 200, note

        with patch.object(link, "request", slow_relay), ThreadPoolExecutor(max_workers=2) as workers:
            sync = workers.submit(link.watch_once, self.path, self.operator)
            try:
                self.assertTrue(waiting.wait(2))
                workers.submit(link.change, self.path, self.operator, "forget").result(timeout=2)
                self.assertEqual(link.view(self.path, self.operator)["phase"], "removing")
            finally:
                respond.set()
            self.assertTrue(sync.result(timeout=2))
        self.assertFalse(self.read()["inbox"])
        with patch.object(link, "request", return_value=(204, b"")) as relay:
            self.assertFalse(link.watch_once(self.path, self.operator))
        relay.assert_called_once_with(self.config, "DELETE", "/v1/pair/" + self.config["pair"])
        self.assertFalse(self.path.exists())

    def test_incoming_note_notifies_once_even_if_its_receipt_is_retried(self):
        identifier = "b" * 32
        route = "/v1/inbox/" + identifier
        note = self.note("Private handoff content")
        envelope = link.encrypt(self.config, "phone", identifier, "message", link.pack(note))
        link.save(self.path, self.state)
        receipts = []
        notices = []

        def request(config, method, resource, body=None):
            if (method, resource) == ("GET", "/v1/inbox"):
                return 200, link.pack([identifier])
            if (method, resource) == ("GET", route):
                return 200, envelope
            self.assertEqual((method, resource), ("PUT", route + "/receipt"))
            receipts.append(body)
            return (503 if len(receipts) == 1 else 200), b""

        def notify(pair):
            self.assertEqual(self.read()["inbox"][identifier]["message"], note)
            notices.append(pair)

        with patch.object(link, "request", request):
            self.assertTrue(link.watch_once(self.path, self.operator, notify))
            self.assertTrue(link.watch_once(self.path, self.operator, notify))
        self.assertEqual(notices, [self.config["pair"]])
        self.assertEqual(len(receipts), 2)
        self.assertEqual(receipts[0], receipts[1])

    def test_notice_uses_local_action_and_honors_activation_and_revocation(self):
        private_text = "Text never shown in a notification"
        self.state["inbox"]["b" * 32] = {"message": self.note(private_text)}
        link.save(self.path, self.state)

        def notify(command, **kwargs):
            if "--help" in command:
                return subprocess.CompletedProcess(command, 0, "--activation-token-fd", "")
            self.assertIn("--action=default=Open Phone settings", command)
            self.assertNotIn(private_text, " ".join(command))
            descriptor, = kwargs["pass_fds"]
            os.write(descriptor, b"test-activation-token")
            return subprocess.CompletedProcess(command, 0, "default\n", "")

        with patch.object(link.shutil, "which", return_value="/usr/bin/notify-send"), \
                patch.object(link.subprocess, "run", side_effect=notify), patch.object(link.subprocess, "Popen") as launch:
            link.show_handoff_notice(self.path, self.config["pair"])
            command, = launch.call_args.args
            self.assertEqual(command, [SCRIPT.with_name("monet-settings"), "phone"])
            self.assertEqual(launch.call_args.kwargs["env"]["XDG_ACTIVATION_TOKEN"], "test-activation-token")
            self.state["revoking"] = True
            link.save(self.path, self.state)
            link.show_handoff_notice(self.path, self.config["pair"])
            self.assertEqual(launch.call_count, 1)
