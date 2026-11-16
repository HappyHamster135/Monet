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

        def slow_relay(config, method, route, body=None, **options):
            if route == "/v1/files/inbox":
                return 404, b""
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
        self.assertFalse(link.view(self.path, self.operator)["fileRelay"])
        self.assertIsNone(link.view(self.path, self.operator)["problem"])

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

        def request(config, method, resource, body=None, **options):
            if resource == "/v1/files/inbox":
                return 404, b""
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

    def test_file_upload_resumes_from_relay_cursor_without_original(self):
        self.state["fileRelay"] = True
        link.save(self.path, self.state)
        content = b"x" * link.FILE_CHUNK + b"end"
        source = self.path.parent / "drawing.bin"
        source.write_bytes(content)
        link.queue_file(self.path, source, self.config["pair"])
        source.unlink()
        (identifier, file), = self.read()[link.FILE_OUTBOX].items()
        route = "/v1/files/outbox/" + identifier
        frame = link.decode(file["manifest"])
        self.assertEqual(json.loads(link.seal(self.config, "pc", identifier, "file-manifest", frame[8:]))["sha256"],
                         hashlib.sha256(content).hexdigest())
        transfers = []

        def relay(config, method, resource, body=None, **options):
            if resource == "/v1/files/inbox":
                return 200, b"[]"
            if resource == route:
                return 200, link.pack({"state": "uploading", "bytes": len(content), "chunks": 2, "next": 1})
            if resource == route + "/1":
                self.assertEqual(method, "PUT")
                transfers.append(link.seal(config, "pc", identifier + ":1", "file-chunk", body))
                return 201, b""
            self.assertEqual(resource, route + "/receipt")
            return 200, link.encrypt(config, "phone", identifier, "file-receipt", hashlib.sha256(frame).digest())

        with patch.object(link, "request", relay):
            self.assertFalse(link.FileSync(self.path, self.read(), None).run())
        self.assertEqual(transfers, [b"end"])
        self.assertEqual(self.read()[link.FILE_OUTBOX][identifier]["status"], "Received")
        self.assertFalse(link.file_payload(self.path, self.config["pair"], False, identifier).exists())

    def test_file_download_recovers_a_torn_chunk_and_preserves_existing_file(self):
        link.save(self.path, self.state)
        identifier = "b" * 32
        route = "/v1/files/inbox/" + identifier
        name = "Photo från mobilen.bin"
        original = b"a" * link.FILE_CHUNK + b"last"
        manifest = {"filename": name, "bytes": len(original), "mime": "application/octet-stream",
                    "sha256": hashlib.sha256(original).hexdigest(), "expires": int(time.time()) + 3600}
        frame = len(original).to_bytes(8, "big") + link.encrypt(self.config, "phone", identifier, "file-manifest", link.pack(manifest))
        received, receipts, notices = [], [], []
        available = False

        def relay(config, method, resource, body=None, **options):
            if resource == "/v1/files/inbox":
                return 200, link.pack([identifier])
            if resource == route:
                return 200, frame
            if resource == route + "/receipt":
                receipts.append(body)
                return (503 if len(receipts) == 1 else 200), b""
            index = int(resource.rsplit("/", 1)[-1])
            if index == 1 and not available:
                return 503, b""
            received.append(index)
            part = original[index * link.FILE_CHUNK:(index + 1) * link.FILE_CHUNK]
            return 200, link.encrypt(config, "phone", f"{identifier}:{index}", "file-chunk", part)

        with patch.object(link, "request", relay):
            with self.assertRaises(link.RelayRejected):
                link.FileSync(self.path, self.read(), notices.append).run()
            self.assertEqual(self.read()[link.FILE_INBOX][identifier]["status"], "Downloading")
            partial = link.file_payload(self.path, self.config["pair"], True, identifier)
            with partial.open("ab") as handle:
                handle.write(b"interrupted write")
            available = True
            with self.assertRaises(link.RelayRejected):
                link.FileSync(self.path, self.read(), notices.append).run()
            link.FileSync(self.path, self.read(), notices.append).run()
        self.assertEqual(received, [0, 1])
        self.assertEqual(notices, [self.config["pair"]])
        self.assertEqual(len(receipts), 2)
        self.assertEqual(receipts[0], receipts[1])
        self.assertEqual(link.seal(self.config, "pc", identifier, "file-receipt", receipts[0]), hashlib.sha256(frame).digest())
        folder = self.path.parent / "downloads"
        folder.mkdir()
        (folder / name).write_bytes(b"An existing file")
        action = {"id": identifier, "incoming": True, "folder": str(folder), "pair": self.config["pair"]}
        saved = link.copy_to_folder(self.path, json.dumps(action))
        self.assertEqual(saved, "Photo från mobilen (1).bin")
        self.assertEqual((folder / name).read_bytes(), b"An existing file")
        self.assertEqual((folder / saved).read_bytes(), original)
        with patch.object(link, "input_text", return_value=json.dumps(action)):
            link.change(self.path, self.operator, "remove-file")
        self.assertFalse(partial.exists())
        self.assertEqual(link.view(self.path, self.operator)["files"], [])
        self.assertEqual((folder / saved).read_bytes(), original)

    def test_unverified_receipt_keeps_a_recoverable_copy(self):
        self.state["fileRelay"] = True
        link.save(self.path, self.state)
        source = self.path.parent / "keep.bin"
        content = b"The local file"
        source.write_bytes(content)
        link.queue_file(self.path, source, self.config["pair"])
        source.unlink()
        identifier, = self.read()[link.FILE_OUTBOX]

        def relay(config, method, resource, body=None, **options):
            if resource == "/v1/files/inbox":
                return 200, b"[]"
            if resource.endswith("/receipt"):
                return 200, link.encrypt(config, "phone", identifier, "file-receipt", b"\x00" * 32)
            return 200, link.pack({"bytes": len(content), "chunks": 1, "next": 1, "state": "received"})

        with patch.object(link, "request", relay):
            link.FileSync(self.path, self.read(), None).run()
        row, = link.view(self.path, self.operator)["files"]
        self.assertEqual(row["status"], "Could not verify receipt")
        self.assertTrue(row["canSave"])
        action = {"id": identifier, "incoming": False, "pair": self.config["pair"], "folder": str(self.path.parent)}
        self.assertEqual(link.copy_to_folder(self.path, json.dumps(action)), source.name)
        self.assertEqual(source.read_bytes(), content)

    def test_file_import_rejects_stale_pair_and_unsafe_names(self):
        self.state["fileRelay"] = True
        link.save(self.path, self.state)
        source = self.path.parent / "selected.bin"
        source.write_bytes(b"selected only for the old peer")
        with self.assertRaisesRegex(ValueError, "pairing changed"):
            link.queue_file(self.path, source, "e" * 32)
        self.assertFalse(self.read().get(link.FILE_OUTBOX))
        for name in ("../../notes", "C:\\notes", "bad\u202e.bin", ".."):
            with self.subTest(name=name):
                self.assertFalse(link.safe_filename(name))

    def test_forget_during_file_fetch_does_not_restore_the_payload(self):
        identifier = "b" * 32
        original = b"data"
        manifest = {"filename": "data.bin", "mime": "application/octet-stream", "bytes": len(original),
                    "sha256": hashlib.sha256(original).hexdigest(), "expires": int(time.time()) + 3600}
        frame = len(original).to_bytes(8, "big") + link.encrypt(self.config, "phone", identifier, "file-manifest", link.pack(manifest))
        link.save(self.path, self.state)
        held, released = Event(), Event()

        def relay(config, method, resource, body=None, **options):
            if resource == "/v1/files/inbox":
                return 200, link.pack([identifier])
            if resource == "/v1/files/inbox/" + identifier:
                return 200, frame
            held.set()
            self.assertTrue(released.wait(5))
            return 200, link.encrypt(config, "phone", identifier + ":0", "file-chunk", original)

        with patch.object(link, "request", relay), ThreadPoolExecutor(max_workers=2) as pool:
            sync = pool.submit(link.FileSync(self.path, self.read(), None).run)
            try:
                self.assertTrue(held.wait(2))
                pool.submit(link.change, self.path, self.operator, "forget").result(timeout=2)
            finally:
                released.set()
            with self.assertRaises(link.PairingChanged):
                sync.result(timeout=2)
        self.assertFalse(self.read().get(link.FILE_INBOX))
        self.assertFalse(link.file_directory(self.path, self.config["pair"]).exists())
