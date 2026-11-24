"""Paste plain text into the focused editor without taking clipboard ownership."""
from collections import deque
import select
import subprocess
import sys
from time import monotonic

import gi
gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, GLib

from actions import tr


class PasteUnavailable(Exception):
    pass


def read_clipboard(*args):
    try:
        result = subprocess.run(["/usr/bin/wl-paste", *args], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=2, check=True)
    except (OSError, subprocess.SubprocessError):
        raise PasteUnavailable(tr("Could not read the clipboard.")) from None
    return result.stdout


def clipboard_formats():
    return read_clipboard("--list-types").decode("ascii", errors="replace").splitlines()


def text_format(formats):
    # Some file managers include a printable path alongside their file transfer.
    if any(t in formats for t in ("x-special/gnome-copied-files", "application/x-kde-cutselection", "application/x-kde-ark-dndextract-service")):
        raise PasteUnavailable(tr("Copy some text first."))
    preferred = ("text/plain;charset=utf-8", "text/plain; charset=utf-8", "utf8_string", "text/plain", "text/html")
    mime = next((t for kind in preferred for t in formats if t.lower() == kind), None)
    if not mime:
        raise PasteUnavailable(tr("Copy some text first."))
    return mime


def clipboard_text(mime, formats):
    if "text/uri-list" in formats:
        uris = read_clipboard("--no-newline", "--type", "text/uri-list")
        if any(line.strip().lower().startswith(b"file:") for line in uris.splitlines()):
            raise PasteUnavailable(tr("Copy some text first."))
    data = read_clipboard("--no-newline", "--type", mime)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise PasteUnavailable(tr("Could not read the clipboard.")) from None
    if mime.lower() == "text/html":
        from PySide6.QtGui import QTextDocumentFragment
        text = QTextDocumentFragment.fromHtml(text).toPlainText()
    if not text or "\x00" in text:
        raise PasteUnavailable(tr("Copy some text first."))
    return text.replace("\r\n", "\n")


def states(node):
    node.clear_cache_single()
    return node.get_state_set()


def editable(node):
    flags = states(node)
    return (flags.contains(Atspi.StateType.FOCUSED) and flags.contains(Atspi.StateType.EDITABLE)
            and (flags.contains(Atspi.StateType.SENSITIVE) or flags.contains(Atspi.StateType.ENABLED))
            and not flags.contains(Atspi.StateType.READ_ONLY) and node.get_editable_text_iface() is not None
            and node.get_text_iface() is not None)


def focused_editor(pid):
    desktop = Atspi.get_desktop(0)
    active = []
    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        if app is None:
            continue
        try:
            if app.get_process_id() != pid:
                continue
            for j in range(app.get_child_count()):
                window = app.get_child_at_index(j)
                if window is not None and states(window).contains(Atspi.StateType.ACTIVE):
                    active.append(window)
        except GLib.Error:
            continue  # An app can exit while its root is being enumerated.
    targets = []
    for window in active:
        item = focused_child(window)
        if item is not None:
            targets.append((window, item))
    return targets[0] if len(targets) == 1 else None


def focused_child(window):
    if editable(window):
        return window
    queue = deque([window])
    # Toolkits with Collection can find the focused object inside large documents.
    collection = window.get_collection_iface()
    if collection:
        flag = Atspi.StateSet.new([Atspi.StateType.FOCUSED])
        match = Atspi.CollectionMatchType
        rule = Atspi.MatchRule.new(flag, match.ALL, {}, match.EMPTY, [], match.EMPTY, [], match.EMPTY, False)
        try:
            for node in collection.get_matches(rule, Atspi.CollectionSortOrder.CANONICAL, 2, True):
                if editable(node):
                    return node
        except GLib.Error:
            pass
    deadline = monotonic() + 1
    while queue and monotonic() < deadline:
        node = queue.popleft()
        if editable(node):
            return node
        if node != window and not node.get_state_set().contains(Atspi.StateType.SHOWING):
            continue
        for i in range(node.get_child_count()):
            child = node.get_child_at_index(i)
            if child is not None:
                queue.append(child)
            if monotonic() >= deadline:
                break
    return None


def selection(node):
    count = node.get_character_count()
    start = end = node.get_caret_offset()
    selections = node.get_n_selections()
    if selections == 1:
        selected = Atspi.Text.get_selection(node, 0)
        start, end = sorted((selected.start_offset, selected.end_offset))
    if selections > 1 or not 0 <= start <= end <= count:
        raise PasteUnavailable(tr("This field could not accept the paste."))
    return count, start, end


def paste(pid, mode):
    Atspi.set_timeout(450, 650)
    target = focused_editor(pid)
    if not target:
        raise PasteUnavailable(tr("Focus an editable text field and try again."))
    window, node = target

    def current():
        # KWin closes stdin if this request loses its keyboard destination.
        return (not select.select([sys.stdin], [], [], 0)[0]
                and states(window).contains(Atspi.StateType.ACTIVE) and editable(node))

    original = selection(node)
    formats = clipboard_formats()
    mime = text_format(formats)
    plain_types = {"text/plain", "text/plain;charset=utf-8", "text/plain; charset=utf-8",
                   "utf8_string", "text", "string", "targets", "timestamp", "multiple"}
    plain_field = node.get_role() == Atspi.Role.PASSWORD_TEXT or (
        node.get_role() == Atspi.Role.ENTRY and node.get_state_set().contains(Atspi.StateType.SINGLE_LINE))
    if (all(t.lower() in plain_types for t in formats) or
            (plain_field and "text/uri-list" not in formats and mime.lower() != "text/html")):
        if current() and selection(node) == original:
            return 23  # Ask KWin to deliver the editor's normal paste shortcut.
        raise PasteUnavailable(tr("The focused field changed. Try pasting again."))

    text = clipboard_text(mime, formats)
    if not current() or selection(node) != original:
        raise PasteUnavailable(tr("The focused field changed. Try pasting again."))
    data = text.encode("utf-8")
    if mode == "commit" and len(data) <= 3500:
        # A Wayland text-input message, including its header, must fit in 4 KiB.
        sys.stdout.buffer.write(data)
        return 24

    # XWayland and editors without a Wayland text-input connection expose
    # toolkit editing operations. The selection is retained until the whole
    # insertion has succeeded, including when a field enforces a length limit.
    before, start, end = original
    toolkit = (node.get_application().get_toolkit_name() or "").lower()
    if not (toolkit.startswith("qt") or toolkit == "gtk"):
        raise PasteUnavailable(tr("This field could not accept the paste."))
    qt = toolkit.startswith("qt")
    units = len(text.encode("utf-16-le")) // 2 if qt else len(text)
    length = units if qt else len(data)
    previous = Atspi.Text.get_text(node, start, end) if start != end else None
    if not current() or selection(node) != original:
        raise PasteUnavailable(tr("The focused field changed. Try pasting again."))
    if not Atspi.EditableText.insert_text(node, end, text, length):
        raise PasteUnavailable(tr("This field could not accept the paste."))
    if node.get_character_count() != before + units or not current():
        raise PasteUnavailable(tr("The field changed during paste. Check its contents."))
    if start != end:
        if (Atspi.Text.get_text(node, start, end) != previous or
                Atspi.Text.get_text(node, end, end + units) != text):
            raise PasteUnavailable(tr("The field changed during paste. Check its contents."))
        if not Atspi.EditableText.delete_text(node, start, end):
            raise PasteUnavailable(tr("The field changed during paste. Check its contents."))
    if node.get_n_selections() == 1:
        Atspi.Text.remove_selection(node, 0)
    Atspi.Text.set_caret_offset(node, start + units)
    return 0


def main(pid, mode):
    try:
        return paste(pid, mode)
    except PasteUnavailable as error:
        message = str(error)
    except GLib.Error:
        message = tr("This field could not accept the paste.")
    subprocess.run(["notify-send", "--app-name", tr("Monet Utilities"), "--icon", "edit-paste",
                    tr("Paste as plain text"), message], check=False)
    return 1
