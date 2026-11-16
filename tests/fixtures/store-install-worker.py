#!/usr/bin/python3
"""A pretend Flatpak for the Store's installs, and a download-only process that uses it.

fake_flatpak() gives the gi, Flatpak, GLib and Gio that flatpak_transaction() uses.
Run as a script (MONET_STORE SCENARIO LOG), this is monet-store --install-worker with
its transactions scripted, logging [pid, phase, "start" or "end"] lines of JSON:

    complete         both phases work (and a trigger prints a line while installing)
    stall            a little progress, then none; ignores SIGTERM, as a blocked pull can
    steady           slow but steady progress, longer than the idle limit in all
    slow-fetch       a download that goes on until it is stopped
    wait-for-cancel  the install waits until the log says Cancel was pressed
    crash            the process ends without a word
    PHASE:MESSAGE    the real flatpak_transaction(), whose PHASE (fetch or deploy)
                     fails with MESSAGE
"""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import time
import types

REF = "app/org.example.Paint/x86_64/stable"


def fake_flatpak(failures=None, installed=False):
    """(sys.modules entries, what was asked of it). Each transaction has one operation, whose
    meter ticks in place as well as forward; the phase named in `failures` ("fetch",
    "deploy", or "" for a removal) fails with that message."""
    failures = failures or {}
    seen = {"runs": [], "installed": installed}

    class Error(Exception):
        def __init__(self, message, domain="flatpak", code="aborted"):
            super().__init__(message)
            self.message, self.domain, self.code = message, domain, code

        def matches(self, domain, code):
            return (self.domain, self.code) == (domain, code)

    class Cancellable:
        cancelled = False

        def cancel(self):
            self.cancelled = True

        def is_cancelled(self):
            return self.cancelled

    class Installation:
        @staticmethod
        def new_system(cancel):
            return Installation()

        new_user = new_system

        def get_installed_ref(self, kind, name, arch, branch, cancel):
            if not seen["installed"]:
                raise Error(name + " not installed", code="not-installed")

    class Progress:
        def __init__(self, transferred, percent):
            self.transferred, self.percent = transferred, percent

        def get_bytes_transferred(self):
            return self.transferred

        def get_progress(self):
            return self.percent

    class Meter:
        def set_update_frequency(self, milliseconds):
            pass

        def connect(self, name, handler):
            self.changed = handler

    class Transaction:
        @staticmethod
        def new_for_installation(installation, cancel):
            return Transaction()

        def __init__(self):
            self.handlers, self.flags, self.work = {}, set(), None

        def set_no_interaction(self, value):
            pass

        def set_no_deploy(self, value):
            self.flags.add("no-deploy")

        def set_no_pull(self, value):
            self.flags.add("no-pull")

        def connect(self, name, handler):
            self.handlers[name] = handler

        def add_install(self, remote, ref, subpaths):
            self.work = ("install", remote, ref)

        def add_uninstall(self, ref):
            self.work = ("uninstall", ref)

        def get_operations(self):
            return ["app"]

        def run(self, cancel):
            phase = "fetch" if "no-deploy" in self.flags else "deploy" if "no-pull" in self.flags else ""
            seen["runs"].append((phase, self.work))
            if not self.handlers["ready"](self):
                raise Error("Operation was cancelled", "gio", "cancelled")
            if "new-operation" in self.handlers:
                meter = Meter()
                self.handlers["new-operation"](self, "app", meter)
                for values in ((0, 0), (0, 0), (4096, 40), (4096, 40), (8192, 100)):
                    meter.changed(Progress(*values))
            if phase in failures:
                # Without a handler, Flatpak stops at the first failure too.
                stop = self.handlers.get("operation-error", lambda *details: False)
                if not stop(self, "app", Error(failures[phase], code="failed"), 0):
                    # All Flatpak itself says once a handler has stopped it.
                    raise Error("Aborted due to failure")
            if phase != "fetch":
                seen["installed"] = self.work[0] == "install"
            return True

    gi = types.ModuleType("gi")
    gi.require_version = lambda namespace, version: None
    repository = gi.repository = types.ModuleType("gi.repository")
    repository.Flatpak = types.SimpleNamespace(
        Installation=Installation, Transaction=Transaction, RefKind=types.SimpleNamespace(APP="app"),
        Error=types.SimpleNamespace(NOT_INSTALLED="not-installed"), error_quark=lambda: "flatpak")
    repository.GLib = types.SimpleNamespace(Error=Error)
    repository.Gio = types.SimpleNamespace(Cancellable=Cancellable, io_error_quark=lambda: "gio",
                                           IOErrorEnum=types.SimpleNamespace(CANCELLED="cancelled"))
    return {"gi": gi, "gi.repository": repository}, seen


def main(store_path, scenario, log):
    loader = importlib.machinery.SourceFileLoader("store_install_worker", store_path)
    store = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(store)
    log = Path(log)

    def record(*event):
        with log.open("a") as stream:
            stream.write(json.dumps([os.getpid(), *event]) + "\n")

    def logged(step):
        return any(json.loads(line)[1:] == step for line in log.read_text().splitlines())

    def scripted(action, ref, scope, progress, cancelled, phase=""):
        record(phase, "start")
        if phase == "fetch":
            if scenario == "stall":
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                progress(0.1)
                time.sleep(60)
            elif scenario == "steady":
                for step in range(1, 11):
                    progress(step / 10)
                    time.sleep(0.05)
            elif scenario == "slow-fetch":
                for step in range(1, 1000):
                    progress(step / 1000)
                    time.sleep(0.01)
            elif scenario == "crash":
                os._exit(3)
            else:
                progress(0.5)
                progress(1)
        elif scenario == "wait-for-cancel":
            deadline = time.monotonic() + 10
            while not logged(["cancel", "pressed"]) and time.monotonic() < deadline:
                time.sleep(0.01)
            time.sleep(0.6)  # Still installing well after Cancel.
        else:
            print("Updating icon cache", flush=True)  # Not the Store's own words.
        record(phase, "end")
        return {"ok": True}

    if ":" in scenario:
        failing, message = scenario.split(":", 1)
        modules, _ = fake_flatpak({failing: message})
        sys.modules.update(modules)
        real = store.flatpak_transaction

        def transaction(*args, phase=""):
            record(phase, "start")
            result = real(*args, phase=phase)
            if result.get("ok"):
                record(phase, "end")
            return result
    else:
        transaction = scripted
    store.flatpak_transaction = transaction
    return store.install_worker(REF, "system")


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
