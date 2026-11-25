"""Run explicitly selected scripts and optional search previews outside the D-Bus loop."""
from collections import OrderedDict
from dataclasses import dataclass
import os
from pathlib import Path
import selectors
import signal
import subprocess
import threading
import time

from gi.repository import GLib

from actions import preferences, tr
from command_search import copy_text, notify, result
from saved_scripts import choices, library

OUTPUT_LIMIT = 65536
PREVIEW_TIMEOUT = 15


@dataclass(frozen=True)
class Answer:
    text: str = ""
    error: str = ""


def execute(script, argument, cancel, preview=False):
    if cancel.is_set():
        return Answer()
    try:
        process = subprocess.Popen([script.path, argument], cwd=Path(script.path).parent, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    except OSError as error:
        return Answer(error=tr("Could not start the script.") + " " + str(error))
    stdout, stderr = bytearray(), bytearray()
    deadline = time.monotonic() + PREVIEW_TIMEOUT if preview else None
    complete = oversized = False
    try:
        with selectors.DefaultSelector() as watch:
            watch.register(process.stdout, selectors.EVENT_READ, stdout)
            watch.register(process.stderr, selectors.EVENT_READ, stderr)
            while watch.get_map() or process.poll() is None:
                if cancel.is_set():
                    return Answer()
                if preview and time.monotonic() >= deadline:
                    return Answer(error=tr("The script timed out."))
                if not preview and not watch.get_map():
                    process.wait()
                    break
                ready = watch.select(.1 if preview else .5)
                if not ready and not preview and process.poll() is not None:
                    # The command may have launched a separate GUI app which inherited its pipes.
                    break
                for key, _ in ready:
                    chunk = os.read(key.fd, 8192)
                    if not chunk:
                        watch.unregister(key.fd)
                        continue
                    room = OUTPUT_LIMIT - len(stdout) - len(stderr)
                    key.data.extend(chunk[:room])
                    if len(chunk) > room:
                        oversized = True
                        if preview:
                            return Answer(error=tr("The script produced too much output."))
        complete = True
        if process.returncode:
            detail = stderr.decode(errors="replace").replace("\0", "�").strip()[-360:]
            return Answer(error=tr("The script exited with code %1.").replace("%1", str(process.returncode))
                          + (" " + detail if detail else ""))
        if oversized:
            return Answer(error=tr("The script finished. Its output was too large to copy."))
        if b"\0" in stdout:
            return Answer(error=tr("The script returned binary output."))
        return Answer(stdout.decode(errors="replace").rstrip("\r\n"))
    finally:
        if not complete:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.stdout.close()
        process.stderr.close()
        process.wait()


def background(script, argument, cancel, done, preview=False):
    def work():
        try:
            answer = execute(script, argument, cancel, preview)
        except (OSError, ValueError) as error:
            answer = Answer(error=str(error))
        GLib.idle_add(done, answer)
    threading.Thread(target=work, name="Monet saved script", daemon=True).start()


def remember(cache, key, value):
    cache[key] = value
    cache.move_to_end(key)
    if len(cache) > 32:
        cache.popitem(last=False)


@dataclass
class Choice:
    script: object
    argument: str
    answer: Answer = None

    def row(self, score):
        script = self.script
        if self.answer and self.answer.error:
            hint = self.answer.error
        elif self.answer and self.answer.text:
            hint = " ".join(self.answer.text.split())[:240]
        elif self.answer:
            hint = tr("Finished with no output")
        elif script.needs_text and not self.argument:
            hint = tr("Add text after the script name")
        else:
            hint = tr("Run script and copy its output")
        return result(script.key(self.argument), script.name, "text-x-script", tr("Saved scripts"), hint, score)


class ScriptSearch:
    """One search surface. Keep returned rows briefly so a late Run can use its exact answer."""
    def __init__(self, bus, settings):
        self.bus = bus
        self.settings = settings
        self.rows = OrderedDict()
        self.answers = OrderedDict()
        self.timer = 0
        self.pending = None
        self.cancel = None
        self.running = set()

    def cancel_preview(self):
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = 0
        if self.cancel:
            self.cancel.set()
            self.cancel = None
        if self.pending:
            _, callbacks = self.pending
            self.pending = None
            for reply in callbacks:
                reply([])

    def leave(self):
        self.cancel_preview()
        self.answers.clear()

    def available(self, script):
        self.settings.sync()
        return "scripts" not in preferences(self.settings)[1] and script in library(self.settings)

    def search(self, query, reply):
        scripts = library(self.settings)
        found = choices(scripts, query)
        if found:
            script, argument, exact = found[0]
            key = script.key(argument)
            if exact and self.pending and self.pending[0] == key:
                self.pending[1].append(reply)
                return
        self.cancel_preview()
        if found and exact and script.preview and (argument or not script.needs_text):
            choice = Choice(script, argument, self.answers.get(key))
            if choice.answer is None:
                self.pending = (key, [reply])
                self.cancel = threading.Event()
                self.timer = GLib.timeout_add(300, self.preview, key, choice, self.cancel)
                return
            remember(self.rows, key, choice)
            reply([choice.row(1.0)])
            return
        rows = []
        if not scripts and not query:
            rows.append(result("scripts", tr("Add script…"), "list-add", tr("Saved scripts"), tr("Choose a script")))
        for script, argument, _ in found:
            choice = Choice(script, argument)
            remember(self.rows, script.key(argument), choice)
            rows.append(choice.row(1 - .01 * len(rows)))
        reply(rows)

    def preview(self, key, choice, cancel):
        self.timer = 0
        def finished(answer):
            if cancel.is_set() or not self.pending or self.pending[0] != key:
                return False
            _, callbacks = self.pending
            self.pending = self.cancel = None
            rows = []
            if self.available(choice.script):
                choice.answer = answer
                remember(self.answers, key, answer)
                remember(self.rows, key, choice)
                rows = [choice.row(1.0)]
            for reply in callbacks:
                reply(rows)
            return False
        if self.available(choice.script):
            background(choice.script, choice.argument, cancel, finished, preview=True)
        else:
            self.cancel_preview()
        return False

    def run(self, key):
        choice = self.rows.get(key)
        if not choice or not self.available(choice.script):
            notify(self.bus, tr("This search result is no longer available."), "text-x-script")
            return
        if choice.script.needs_text and not choice.argument:
            import dbus
            try:
                app = self.bus.get_object("org.kde.krunner", "/App", introspect=False)
                app.query(tr("script") + ": " + choice.script.name + " ", dbus_interface="org.kde.krunner.App", signature="s")
            except dbus.DBusException:
                notify(self.bus, tr("Add text after the script name"), "text-x-script")
            return

        progress_timer = 0
        def finish(answer):
            if progress_timer:
                GLib.source_remove(progress_timer)
            self.running.discard(key)
            if answer.error:
                message = answer.error
            elif answer.text:
                message = tr("Script output copied.") if copy_text(self.bus, answer.text) else tr("Could not copy the script output.")
            else:
                message = tr("Finished with no output")
            notify(self.bus, choice.script.name, "text-x-script", GLib.markup_escape_text(message))
            return False

        if choice.answer is not None:
            finish(choice.answer)
        elif key not in self.running:
            self.running.add(key)
            def progress():
                nonlocal progress_timer
                progress_timer = 0
                if key in self.running:
                    notify(self.bus, choice.script.name, "text-x-script", tr("Running script…"))
                return False
            progress_timer = GLib.timeout_add(1500, progress)
            background(choice.script, choice.argument, threading.Event(), finish)
