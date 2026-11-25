"""Optional IBus input method. Compose inside the focused editor, without reading its text."""
import os
import sys
import time

import gi
gi.require_version("IBus", "1.0")
from gi.repository import Gio, GLib, IBus
from PySide6.QtCore import QSettings

from snippet_rules import expansion_table


class SnippetInput(IBus.EngineSimple):
    __gtype_name__ = "MonetSnippetInput"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.settings = QSettings("Monet", "Utilities")
        self.revision = None
        self.rules, self.prefixes = {}, set()
        self.prefix = ""
        self.releases = set()
        self.pending = None

    def refresh(self):
        try:
            stat = os.stat(self.settings.fileName())
            revision = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
        except OSError:
            revision = ()
        if self.revision != revision:
            self.settings.sync()
            self.rules, self.prefixes = expansion_table(self.settings)
            self.revision = revision

    def preedit(self, text):
        self.prefix = text
        self.update_preedit_text_with_mode(IBus.Text.new_from_string(text), len(text),
                                           bool(text), IBus.PreeditFocusMode.COMMIT)

    def finish(self, text):
        self.preedit("")
        self.commit_text(IBus.Text.new_from_string(text))

    def do_reset(self):
        self.pending = None
        self.prefix = ""
        IBus.EngineSimple.do_reset(self)

    def do_focus_out(self):
        # The client owns focus-out commitment of the displayed composition.
        self.pending = None
        self.prefix = ""
        self.releases.clear()
        IBus.EngineSimple.do_focus_out(self)

    def do_disable(self):
        self.pending = None
        self.prefix = ""
        self.releases.clear()
        IBus.EngineSimple.do_disable(self)

    def accepts_shortcut(self):
        purpose, hints = self.get_content_type()
        return (purpose in (IBus.InputPurpose.FREE_FORM, IBus.InputPurpose.ALPHA)
                and not hints & (IBus.InputHints.HIDDEN_TEXT | IBus.InputHints.PRIVATE)
                and self.client_capabilities & IBus.Capabilite.PREEDIT_TEXT)

    def expand_clipboard(self, candidate, text):
        # Returning to IBus lets the editor that owns the clipboard answer
        # the transfer and lets focus-out cancel an outstanding composition.
        from threading import Thread
        from snippet_variables import ClipboardUnavailable, expand
        request = object()
        self.pending = request
        self.preedit(candidate)

        def deliver(result):
            if self.pending is request:
                self.pending = None
                suffix = self.prefix[len(candidate):]
                self.finish(result)
                for index, char in enumerate(suffix):
                    if self.pending is not None:
                        self.preedit(self.prefix + suffix[index:])
                        break
                    if not self.type_character(char):
                        self.commit_text(IBus.Text.new_from_string(char))
            return False

        def read():
            try:
                result = expand(text)
            except ClipboardUnavailable:
                result = candidate
            GLib.idle_add(deliver, result)

        Thread(target=read, daemon=True).start()

    def type_character(self, character):
        if character == ";":
            self.refresh()
        candidate = self.prefix + character
        if candidate in self.rules:
            text, variables = self.rules[candidate]
            if variables:
                if "{{clipboard}}" in text:
                    self.expand_clipboard(candidate, text)
                    return True
                from snippet_variables import expand
                text = expand(text)
            self.finish(text)
            return True
        if candidate in self.prefixes:
            self.preedit(candidate)
            return True
        if self.prefix:
            if character == ";" and ";" in self.prefixes:
                self.finish(self.prefix)
                self.preedit(";")
            else:
                # The mismatch belongs to this composition. Deliver both pieces
                # in one edit so a forwarded key cannot overtake the prefix.
                self.finish(self.prefix + character)
            return True
        return False

    def do_process_key_event(self, keyval, keycode, state):
        base = IBus.EngineSimple.do_process_key_event
        if state & IBus.ModifierType.RELEASE_MASK:
            if keycode in self.releases:
                self.releases.remove(keycode)
                return True
            return base(self, keyval, keycode, state)
        starting = not self.prefix
        if starting:
            # Let normal dead-key and Compose sequences consume the key first.
            if base(self, keyval, keycode, state):
                return True
            if keyval != IBus.KEY_semicolon:
                return False
        if not self.accepts_shortcut():
            self.pending = None
            if self.prefix:
                self.preedit("")
            return False
        if keyval in (IBus.KEY_Shift_L, IBus.KEY_Shift_R):
            return False
        modified = state & (IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.MOD1_MASK |
                            IBus.ModifierType.SUPER_MASK | IBus.ModifierType.MOD4_MASK |
                            IBus.ModifierType.META_MASK | IBus.ModifierType.HYPER_MASK)
        if self.pending is not None:
            character = IBus.keyval_to_unicode(keyval)
            if not modified and character and character.isprintable() and len(self.prefix) < 256:
                self.preedit(self.prefix + character)
                self.releases.add(keycode)
                return True
            # Navigation and edits apply to the literal preedit if the
            # clipboard owner has not answered yet.
            self.pending = None
            self.finish(self.prefix)
            return base(self, keyval, keycode, state)
        if not modified and self.prefix and keyval in (IBus.KEY_BackSpace, IBus.KEY_Escape):
            self.preedit(self.prefix[:-1] if keyval == IBus.KEY_BackSpace else "")
        else:
            char = IBus.keyval_to_unicode(keyval)
            if modified or not char or not char.isprintable():
                if self.prefix:
                    self.finish(self.prefix)
                return False if starting else base(self, keyval, keycode, state)
            if not self.type_character(char):
                return False
        self.releases.add(keycode)
        return True


def activate(bus):
    engine = "monet-snippets"
    if not bus.get_engines_by_names([engine]):
        return 2
    settings = Gio.Settings.new("org.freedesktop.ibus.general")
    configured = list(settings.get_strv("preload-engines"))
    previous = bus.get_global_engine()
    methods = list(configured)
    if engine not in configured:
        if not settings.is_writable("preload-engines"):
            return 3
        if previous and previous.get_name() not in methods:
            methods.append(previous.get_name())
        if engine not in methods:
            methods.append(engine)
        if not settings.set_strv("preload-engines", methods):
            return 3
        Gio.Settings.sync()
    # The IBus panel can also switch engines while reloading its list.
    for delay in (0, .15, .4):
        if delay:
            time.sleep(delay)
        current = bus.get_global_engine()
        if current and current.get_name() == engine:
            return 0
        if bus.set_global_engine(engine):
            return 0
    if methods != configured and list(settings.get_strv("preload-engines")) == methods:
        settings.set_strv("preload-engines", configured)
        Gio.Settings.sync()
    return 4


def main():
    IBus.init()
    bus = IBus.Bus()
    if not bus.is_connected():
        return 1
    if sys.argv[1:] == ["--activate"]:
        return activate(bus)
    loop = GLib.MainLoop()
    bus.connect("disconnected", lambda *_: loop.quit())
    factory = IBus.Factory.new(bus.get_connection())
    factory.add_engine("monet-snippets", SnippetInput)
    bus.request_name("org.freedesktop.IBus.MonetSnippets", 0)
    loop.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
