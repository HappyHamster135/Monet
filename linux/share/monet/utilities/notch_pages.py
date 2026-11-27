"""Small, inline versions of everyday tools. Desktop editors remain independent."""
from datetime import datetime
import json
from pathlib import Path
import sys
from uuid import uuid4

from PySide6.QtCore import QProcess, QRectF, QSettings, QSize, QStandardPaths, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QListView, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton,
    QSizePolicy, QStackedWidget, QStyle, QStyledItemDelegate, QToolButton, QVBoxLayout, QWidget)

from actions import stored, tr
from clipboard_text import copy_text


def label(text, muted=False):
    item = QLabel(text)
    item.setTextFormat(Qt.PlainText)
    item.setWordWrap(True)
    item.setProperty("muted", muted)
    item.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    return item


def button(text, callback, primary=False):
    item = QPushButton(text)
    item.setProperty("primary", primary)
    item.clicked.connect(callback)
    return item


def row(layout, *widgets):
    line = QHBoxLayout()
    line.setSpacing(6)
    for item in widgets:
        line.addWidget(item)
    layout.addLayout(line)
    return line


class Page(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host, self.settings = host, host.settings
        self.layout_box = QVBoxLayout(self)
        self.layout_box.setContentsMargins(4, 4, 8, 4)
        self.layout_box.setSpacing(10)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)

    def paintEvent(self, event):
        # These pages are repeatedly reparented into the same Wayland surface.
        # Paint the canvas ourselves: QWidget subclasses otherwise leave old
        # backing-buffer pixels beneath transparent labels and empty space.
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor("#101011") if self.property("notchInline") else self.palette().window())

    def notify(self, message):
        self.host.issue(message)

    def copy(self, text, message=None, done=None):
        def finished(ok):
            self.notify((message or tr("Copied.")) if ok else tr("Couldn’t copy. Try again."))
            if done:
                done(ok)
        copy_text(self.host, text, finished)


class ClipboardPage(Page):
    def __init__(self, host, key):
        super().__init__(host)
        self.key, self.generation, self.reader = key, 0, None
        self.layout_box.addWidget(label(tr("Remove formatting from copied text.") if key == "plain" else
                                         tr("Remove tracking parameters from a copied link."), True))
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText(tr("Paste or type text here…") if key == "plain" else tr("Paste a web link here…"))
        self.edit.setAccessibleName(tr("Text to copy") if key == "plain" else tr("Link to clean"))
        self.edit.setMinimumSize(0, 110)
        self.edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.layout_box.addWidget(self.edit, 1)
        self.detail = label("", True)
        self.layout_box.addWidget(self.detail)
        self.load = button(tr("Use clipboard"), self.refresh)
        self.apply = button(tr("Copy plain text") if key == "plain" else tr("Clean & copy"), self.transform, True)
        row(self.layout_box, self.load, self.apply)
        self.edit.textChanged.connect(self.changed)
        self.changed()

    def changed(self):
        self.apply.setEnabled(bool(self.edit.toPlainText().strip()))

    def refresh(self):
        # Merely returning to this page must not modify the clipboard. Copy is
        # explicit, with the transformed result and delivery status shown here.
        self.generation += 1
        generation = self.generation
        if self.reader:
            self.reader.kill()
        clipboard = QApplication.clipboard()
        if clipboard.ownsClipboard() or not QApplication.platformName().startswith("wayland"):
            self.loaded(clipboard.text())
            return
        self.load.setEnabled(False)
        self.detail.setText(tr("Reading clipboard…"))
        formats = iter(("text/plain;charset=utf-8", "text/plain", "UTF8_STRING"))

        def attempt():
            if generation != self.generation:
                return
            mime = next(formats, None)
            if mime is None:
                self.load.setEnabled(True)
                self.detail.setText(tr("Copy some text first, or paste it above."))
                return
            job = self.reader = QProcess(self)
            data = bytearray()
            timer = QTimer(job)
            timer.setSingleShot(True)
            timer.timeout.connect(job.kill)
            def read():
                data.extend(bytes(job.readAllStandardOutput()))
                if len(data) > 1024 * 1024:
                    job.kill()
            job.readyReadStandardOutput.connect(read)
            completed = False
            def finish(ok):
                nonlocal completed
                if completed:
                    return
                completed = True
                timer.stop()
                read()
                job.deleteLater()
                if self.reader is job:
                    self.reader = None
                if generation != self.generation:
                    return
                if ok and data and len(data) <= 1024 * 1024:
                    self.load.setEnabled(True)
                    self.loaded(data.decode("utf-8", errors="replace"))
                else:
                    attempt()
            job.finished.connect(lambda code, status: finish(code == 0 and status == QProcess.NormalExit))
            job.errorOccurred.connect(lambda error: finish(False) if error == QProcess.FailedToStart else None)
            job.start("wl-paste", ["--no-newline", "--type", mime])
            timer.start(1000)
        attempt()

    def loaded(self, text):
        self.edit.setPlainText(text[:1024 * 1024])
        self.detail.setText(tr("Ready to copy without formatting.") if text and self.key == "plain" else
                            tr("Ready to clean.") if text else tr("Copy some text first, or paste it above."))

    def transform(self):
        text = self.edit.toPlainText()
        if not text:
            return
        message = tr("Plain text copied.")
        if self.key == "clean":
            from links import RulesError, clean_link
            try:
                text, removed = clean_link(text)
            except (ValueError, RulesError) as error:
                self.notify(tr("Couldn’t read the saved link rules.") if isinstance(error, RulesError) else tr("Enter one http or https link."))
                return
            message = tr("Clean link copied.") if removed else tr("Link already clean. Copied.")
            self.detail.setText(tr("Removed: ") + ", ".join(removed) if removed else tr("No tracking parameters found."))
            self.edit.setPlainText(text)
        self.copy(text, message)


class SnippetsPage(Page):
    def __init__(self, host):
        super().__init__(host)
        self.current = None
        self.entries, self.shortcuts, self.variables = {}, {}, {}
        self.stack = QStackedWidget()
        self.layout_box.addWidget(self.stack, 1)
        listing = QWidget()
        layout = QVBoxLayout(listing)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("Search snippets…"))
        self.search.setAccessibleName(tr("Search snippets"))
        row(layout, self.search, button(tr("New"), self.add, True))
        self.names = QListWidget()
        self.names.setAccessibleName(tr("Saved snippets"))
        self.names.setMinimumWidth(0)
        self.names.setTextElideMode(Qt.ElideRight)
        self.names.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self.names, 1)
        self.empty = label(tr("Save text you use often. Choose New to write your first snippet."), True)
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setContentsMargins(24, 16, 24, 16)
        self.empty.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        layout.addWidget(self.empty, 1)
        self.stack.addWidget(listing)
        editor = QWidget()
        layout = QVBoxLayout(editor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.name = QLineEdit()
        self.name.setPlaceholderText(tr("Snippet name"))
        self.name.setAccessibleName(tr("Snippet name"))
        self.name.setMaxLength(120)
        row(layout, button(tr("‹ All"), self.listing), self.name)
        self.edit = QPlainTextEdit()
        self.edit.setInputMethodHints(Qt.ImhSensitiveData)
        self.edit.setPlaceholderText(tr("Write a snippet…"))
        self.edit.setAccessibleName(tr("Snippet text"))
        self.edit.setMinimumSize(0, 100)
        self.edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        layout.addWidget(self.edit, 1)
        self.options = QWidget()
        extras = QVBoxLayout(self.options)
        extras.setContentsMargins(0, 0, 0, 0)
        extras.setSpacing(6)
        self.shortcut = QLineEdit()
        self.shortcut.setPlaceholderText(tr("Typing shortcut, e.g. hello → ;hello;"))
        self.shortcut.setAccessibleName(tr("Typing shortcut"))
        self.shortcut.setMaxLength(40)
        extras.addWidget(self.shortcut)
        self.expand = QCheckBox(tr("Expand variables"))
        extras.addWidget(self.expand)
        for_row = []
        for title, value in ((tr("Date"), "{{date}}"), (tr("Time"), "{{time}}"), (tr("Clipboard"), "{{clipboard}}")):
            for_row.append(button(title, lambda checked=False, value=value: self.insert_variable(value)))
        row(extras, *for_row)
        extras.addWidget(label(tr("Typing shortcuts use the Monet Text Snippets IBus input method."), True))
        self.options.hide()
        layout.addWidget(self.options)
        self.more = button(tr("Options"), lambda: self.options.setVisible(not self.options.isVisible()))
        self.remove_button = button(tr("Delete"), self.remove)
        row(layout, self.more, self.remove_button, button(tr("Save"), self.save), button(tr("Copy"), self.copy_snippet, True))
        self.stack.addWidget(editor)
        self.search.textChanged.connect(self.filter)
        self.names.itemClicked.connect(lambda item: self.select(item.data(Qt.UserRole)))
        self.names.itemActivated.connect(lambda item: self.select(item.data(Qt.UserRole)))
        self.refresh()

    def refresh(self):
        if self.stack.currentIndex() == 1:
            return  # Keep a draft when the notch closes or changes tabs.
        self.settings.sync()
        self.entries = stored(self.settings, "snippets", {})
        self.shortcuts = stored(self.settings, "snippetShortcuts", {})
        self.variables = stored(self.settings, "snippetVariables", {})
        self.filter()

    def filter(self):
        self.names.clear()
        needle = self.search.text().casefold()
        for name, text in self.entries.items():
            if not isinstance(text, str) or needle not in (name + " " + text).casefold():
                continue
            preview = " ".join(text.split())[:100]
            item = QListWidgetItem(name + ("\n" + preview if preview else ""))
            item.setData(Qt.UserRole, name)
            item.setSizeHint(QSize(0, 54))
            self.names.addItem(item)
        self.empty.setVisible(self.names.count() == 0)
        self.names.setVisible(self.names.count() != 0)
        self.empty.setText(tr("No matching snippets.") if self.entries else tr("Save text you use often. Choose New to write your first snippet."))

    def select(self, name):
        self.current = name
        self.name.setText(name or "")
        self.edit.setPlainText(self.entries.get(name, ""))
        self.shortcut.setText(self.shortcuts.get(name, ""))
        self.expand.setChecked(self.variables.get(name) is True)
        self.remove_button.setEnabled(bool(name))
        self.remove_button.setText(tr("Delete"))
        self.options.hide()
        self.stack.setCurrentIndex(1)

    def add(self):
        self.select(None)
        self.name.setFocus()

    def insert_variable(self, value):
        self.expand.setChecked(True)
        self.edit.insertPlainText(value)
        self.edit.setFocus()

    def save(self):
        from snippet_rules import valid_shortcut
        name, shortcut = self.name.text().strip(), self.shortcut.text().strip()
        if not name:
            self.notify(tr("Give this snippet a name first."))
            self.name.setFocus()
            return False
        # Merge with settings at save time; another window may have edited a different snippet.
        self.settings.sync()
        entries = stored(self.settings, "snippets", {})
        shortcuts = stored(self.settings, "snippetShortcuts", {})
        variables = stored(self.settings, "snippetVariables", {})
        if name != self.current and name in entries:
            self.notify(tr("A snippet already has this name."))
            return False
        if shortcut and (not valid_shortcut(shortcut) or any(k != self.current and v == shortcut for k, v in shortcuts.items())):
            self.notify(tr("Use a unique shortcut with letters, numbers, underscores or hyphens."))
            return False
        if self.current and self.current != name:
            for values in (entries, shortcuts, variables):
                values.pop(self.current, None)
        entries[name] = self.edit.toPlainText()
        shortcuts.pop(name, None)
        variables.pop(name, None)
        if shortcut:
            shortcuts[name] = shortcut
        if self.expand.isChecked():
            variables[name] = True
        for key, values in (("snippets", entries), ("snippetShortcuts", shortcuts), ("snippetVariables", variables)):
            self.settings.setValue(key, json.dumps(values))
        self.settings.sync()
        self.entries, self.shortcuts, self.variables, self.current = entries, shortcuts, variables, name
        self.remove_button.setEnabled(True)
        self.notify(tr("Snippet saved."))
        return True

    def listing(self):
        if (self.name.text().strip() or self.edit.toPlainText()) and not self.save():
            return
        self.stack.setCurrentIndex(0)
        self.refresh()

    def copy_snippet(self):
        if not self.save():
            return
        text = self.edit.toPlainText()
        if self.expand.isChecked():
            from snippet_variables import ClipboardUnavailable, current_text, expand
            clipboard = QApplication.clipboard()
            try:
                local = clipboard.ownsClipboard() or not QApplication.platformName().startswith("wayland")
                text = expand(text, clipboard.text if local else current_text)
            except (ClipboardUnavailable, OSError):
                self.notify(tr("Copy some text first to use the clipboard variable."))
                return
        self.copy(text, tr("Snippet copied."))

    def remove(self):
        if not self.current:
            return
        if self.remove_button.text() != tr("Confirm"):
            self.remove_button.setText(tr("Confirm"))
            self.notify(tr("Press Confirm to delete this snippet."))
            return
        self.settings.sync()
        for key in ("snippets", "snippetShortcuts", "snippetVariables"):
            values = stored(self.settings, key, {})
            values.pop(self.current, None)
            self.settings.setValue(key, json.dumps(values))
        self.settings.sync()
        self.current = None
        self.stack.setCurrentIndex(0)
        self.refresh()
        self.notify(tr("Snippet deleted."))


class EmojiDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        if option.state & (QStyle.State_Selected | QStyle.State_MouseOver | QStyle.State_HasFocus):
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#303038"))
            painter.drawRoundedRect(QRectF(option.rect.adjusted(2, 2, -2, -2)), 10, 10)
        font = QFont("Noto Color Emoji")
        font.setPixelSize(28)
        painter.setFont(font)
        painter.setPen(QColor("#f5f5f7"))
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.drawText(option.rect, Qt.AlignCenter, index.data(Qt.UserRole))
        painter.restore()


class EmojiCategories(QWidget):
    """Every category remains visible, including in a narrow notch or popup."""
    currentChanged = Signal(int)
    def __init__(self):
        super().__init__();self.buttons=[];self.values=[];self.index=0
        self.setAccessibleName(tr('Emoji categories'))
        self.grid=QGridLayout(self);self.grid.setContentsMargins(0,0,0,0);self.grid.setSpacing(3)

    def add_category(self,title,value,glyph):
        index=len(self.buttons);self.values.append(value)
        button=QToolButton();button.setText(glyph);button.setAccessibleName(title)
        button.setCheckable(True);button.setChecked(index==self.index)
        button.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed);button.setMinimumWidth(0)
        button.setFixedHeight(31)
        button.setStyleSheet("QToolButton {font:19px 'Noto Color Emoji';border:1px solid transparent;border-radius:8px;background:transparent;padding:0;} QToolButton:checked {background:#36594f;border-color:#73b8a3;} QToolButton:hover {background:#303b3c;} QToolButton:focus {border-color:#73b8a3;}")
        button.clicked.connect(lambda checked=False,index=index:self.setCurrentIndex(index))
        self.buttons.append(button);self.grid.addWidget(button,index//6,index%6)

    def count(self):return len(self.values)
    def tabData(self,index):return self.values[index]
    def currentIndex(self):return self.index
    def setCurrentIndex(self,index):
        if not 0<=index<len(self.buttons):return
        self.index=index
        for i,button in enumerate(self.buttons):button.setChecked(i==index)
        self.currentChanged.emit(index)


class EmojiPage(Page):
    def __init__(self, host):
        super().__init__(host)
        from command_search import emoji_dictionary, emoji_index
        self.index = emoji_index()
        try:
            self.categories = {glyph: group for glyph, _, _, group in emoji_dictionary(
                Path("/usr/share/plasma/emoji/en.dict"), with_categories=True)}
        except (OSError, ValueError):
            self.categories = {}
        self.recent = stored(self.settings, "notchRecentEmoji", [])
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("Search emoji…"))
        self.search.setAccessibleName(tr("Search emoji"))
        self.category = EmojiCategories()
        for title, value, glyph in ((tr("Popular"), "popular", "⭐"), (tr("Recent"), "recent", "🕘"),
                                    (tr("All"), "all", "🌐"), (tr("Faces"), 1, "😀"), (tr("People"), 2, "👋"),
                                    (tr("Nature"), 4, "🐻"), (tr("Food"), 5, "🍎"), (tr("Travel"), 6, "🚀"),
                                    (tr("Activities"), 7, "⚽"), (tr("Objects"), 8, "💡"),
                                    (tr("Symbols"), 9, "❤️"), (tr("Flags"), 10, "🏳️")):
            self.category.add_category(title,value,glyph)
        self.layout_box.addWidget(self.search)
        self.layout_box.addWidget(self.category)
        self.group_title=label('');self.group_title.setProperty('sectionTitle',True)
        self.layout_box.addWidget(self.group_title)
        self.grid = QListWidget()
        self.grid.setObjectName("emojiGrid")
        self.grid.setAccessibleName(tr("Emoji, activate to copy"))
        self.grid.setViewMode(QListView.IconMode)
        self.grid.setResizeMode(QListView.Adjust)
        self.grid.setMovement(QListView.Static)
        self.grid.setGridSize(QSize(46, 46))
        self.grid.setUniformItemSizes(True)
        self.grid.setLayoutMode(QListView.Batched)
        self.grid.setBatchSize(96)
        self.grid.setMouseTracking(True)
        self.grid.setVerticalScrollMode(QListView.ScrollPerPixel)
        self.grid.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.grid.setMinimumSize(0, 92)
        self.grid.setItemDelegate(EmojiDelegate(self.grid))
        self.layout_box.addWidget(self.grid, 1)
        self.caption = label(tr("Choose an emoji to copy it."), True)
        self.layout_box.addWidget(self.caption)
        self.grid.itemClicked.connect(self.choose)
        self.grid.itemActivated.connect(self.choose)
        self.grid.currentItemChanged.connect(lambda item, _: self.caption.setText(item.text() if item else tr("No matching emoji.")))
        self.grid.itemEntered.connect(lambda item:self.caption.setText(item.text()))
        self.delay = QTimer(self)
        self.delay.setSingleShot(True)
        self.delay.setInterval(90)
        self.delay.timeout.connect(self.fill)
        self.search.textChanged.connect(self.search_changed)
        self.category.currentChanged.connect(self.fill)
        self.fill()

    def search_changed(self):
        self.grid.setEnabled(False)
        self.caption.setText(tr('Searching…'))
        self.delay.start()

    def fill(self):
        self.delay.stop()
        needle = self.search.text().casefold().split()
        category = self.category.tabData(self.category.currentIndex())
        popular = "😀 😃 😄 😁 😆 😅 😂 🙂 🙃 😉 😊 🥰 😍 🤩 😘 😎 🤔 🫡 😴 😭 😤 🤯 🥳 🫶 👍 👎 👏 🙌 🙏 👋 💪 ❤️ 🧡 💛 💚 💙 💜 🔥 ✨ ⭐ 🎉 🎊 ✅ 🚀 💯 👀 ☕ 🌸 🐱 🌈 🎵 📌 💻".split()
        keys = list(self.index) if needle or category not in ("popular", "recent") else (self.recent if category == "recent" else popular)
        if needle:
            phrase = " ".join(needle)
            keys.sort(key=lambda key: 0 if phrase in (self.index[key][2], self.index[key][4]) or phrase == key else
                      1 if self.index[key][2].startswith(phrase) or self.index[key][4].startswith(phrase) else 2)
        self.grid.clear()
        for glyph in keys:
            entry = self.index.get(glyph)
            if not entry or (needle and not all(term in " ".join(entry).casefold() for term in needle)):
                continue
            if not needle and category not in ("all", "recent", "popular") and self.categories.get(glyph) != category:
                continue
            item = QListWidgetItem(entry[1])
            item.setData(Qt.UserRole, glyph)
            item.setData(Qt.AccessibleTextRole, entry[1])
            item.setSizeHint(QSize(46, 46))
            self.grid.addItem(item)
        self.caption.setText(tr("Choose an emoji to copy it.") if self.grid.count() else tr("No emoji here yet.") if category == "recent" and not needle else tr("No matching emoji."))
        title=tr('Search results') if needle else self.category.buttons[self.category.currentIndex()].accessibleName()
        self.group_title.setText(title+' · '+str(self.grid.count()))
        self.grid.scrollToTop()
        self.grid.setEnabled(True)

    def choose(self, item):
        if self.delay.isActive():return
        glyph = item.data(Qt.UserRole)
        def remember(ok):
            if ok:
                self.recent = [glyph] + [x for x in self.recent if x != glyph][:39]
                self.settings.setValue("notchRecentEmoji", json.dumps(self.recent))
                self.settings.sync()
                self.caption.setText(tr('{emoji} copied · paste with Ctrl+V').format(emoji=glyph))
            else:self.caption.setText(tr('Could not copy. Try again.'))
        self.copy(glyph, tr("Emoji copied."), remember)


class RecordingPage(Page):
    def __init__(self, host, dismiss):
        super().__init__(host)
        self.dismiss = dismiss
        self.outer = self.layout_box
        self.form = QWidget()
        self.layout_box = QVBoxLayout(self.form)
        self.layout_box.setContentsMargins(0, 0, 0, 0)
        self.outer.addWidget(self.form)
        self.clip = None
        self.recorder = None
        saved = self.settings.value("notchLastRecording", "")
        self.last_file = Path(saved) if isinstance(saved,str) and saved and Path(saved).is_file() else None
        self.layout_box.addWidget(label(tr("Record your screen")))
        self.layout_box.addWidget(label(tr("Choose what to capture. Your recording is saved automatically."), True))
        self.mode = QComboBox()
        self.mode.setAccessibleName(tr("Recording area"))
        for name, mode in ((tr("Screen region"), "r"), (tr("One window"), "w"), (tr("One screen"), "s")):
            self.mode.addItem(name, mode)
        self.layout_box.addWidget(self.mode)
        self.sound = QCheckBox(tr("System audio"))
        self.mic = QCheckBox(tr("Microphone"))
        row(self.layout_box, self.sound, self.mic)
        self.sound.clicked.connect(self.save_options)
        self.mic.clicked.connect(self.save_options)
        self.mode.activated.connect(self.save_options)
        self.layout_box.addStretch(1)
        self.message = label(tr("Finish using the recording indicator in the system tray."), True)
        self.layout_box.addWidget(self.message)
        self.start = button(tr("Start recording"), self.capture, True)
        self.layout_box.addWidget(self.start)
        self.reveal = button(tr("Show saved file"), self.show_file)
        self.editor = button(tr("Trim a recording"), self.open_editor)
        self.reveal.setVisible(self.last_file is not None)
        row(self.layout_box, self.reveal, self.editor)
        self.refresh()

    def config(self):
        return QSettings(str(Path(QStandardPaths.writableLocation(QStandardPaths.ConfigLocation)) / "spectaclerc"), QSettings.IniFormat)

    def refresh(self):
        if self.recorder:
            return
        config = self.config()
        self.sound.setChecked(config.value("GuiConfig/videoRecordSystemAudio", False, type=bool))
        self.mic.setChecked(config.value("GuiConfig/videoRecordMicrophone", False, type=bool))
        self.mode.setCurrentIndex(max(0,self.mode.findData(self.settings.value("notchRecordingArea","r"))))

    def save_options(self, *_):
        config = self.config()
        config.setValue("GuiConfig/videoRecordSystemAudio",self.sound.isChecked())
        config.setValue("GuiConfig/videoRecordMicrophone",self.mic.isChecked())
        config.sync()
        self.settings.setValue("notchRecordingArea",self.mode.currentData())
        self.settings.sync()
        if config.status() != QSettings.NoError:self.notify(tr("Could not save recording preferences."))

    def capture(self):
        if self.recorder:
            return
        # Use the same KDE writer and native capture engine as the full editor.
        # Unlike that editor, never minimize/show a separate Utilities window.
        import subprocess
        try:
            for key, enabled in (("videoRecordSystemAudio", self.sound.isChecked()), ("videoRecordMicrophone", self.mic.isChecked())):
                subprocess.run(["kwriteconfig6", "--file", "spectaclerc", "--group", "GuiConfig", "--key", key,
                                "--type", "bool", "true" if enabled else "false"], check=True, timeout=1, capture_output=True)
            config = self.config()
            location = QUrl.fromUserInput(str(config.value("VideoSave/videoSaveLocation", "")))
            folder = Path(location.toLocalFile()) if location.isLocalFile() else Path(QStandardPaths.writableLocation(QStandardPaths.MoviesLocation)) / "Screencasts"
            folder.mkdir(parents=True, exist_ok=True)
        except (OSError, subprocess.SubprocessError):
            self.notify(tr("Couldn’t prepare the recording. Check your save folder and audio settings."))
            return
        suffix = ".mp4" if str(config.value("VideoSave/preferredVideoFormat", "WebM_VP9")) in ("MP4_H264", "2") else ".webm"
        target = folder / ("Recording " + datetime.now().strftime("%Y-%m-%d %H.%M.%S ") + uuid4().hex[:12] + suffix)
        job = self.recorder = QProcess(self)
        for control in (self.mode, self.sound, self.mic, self.start, self.editor, self.reveal):
            control.setEnabled(False)
        self.start.setText(tr("Recording in progress…"))
        self.message.setText(tr("Select the area to capture. Finish using the recording indicator in the system tray."))
        def finish(success):
            if self.recorder is not job:
                return
            self.recorder = None
            job.deleteLater()
            for control in (self.mode, self.sound, self.mic, self.start, self.editor, self.reveal):
                control.setEnabled(True)
            self.start.setText(tr("Start recording"))
            try:
                saved = success and target.is_file() and target.stat().st_size > 0
            except OSError:
                saved = False
            if saved:
                self.last_file = target
                self.settings.setValue("notchLastRecording",str(target)); self.settings.sync()
                self.message.setText(tr("Saved: ") + target.name)
                self.reveal.show()
                self.editor.show()
            else:
                self.message.setText(tr("Recording cancelled.") if success else tr("Couldn’t record the screen. Try again."))
        job.finished.connect(lambda code, status: finish(code == 0 and status == QProcess.NormalExit))
        job.errorOccurred.connect(lambda error: finish(False) if error == QProcess.FailedToStart else None)
        mode = self.mode.currentData()
        self.dismiss()
        QTimer.singleShot(220, self, lambda: job.start("spectacle", ["--new-instance", "--background", "--nonotify", "--record", mode, "--output", str(target)]))

    def show_file(self):
        if self.last_file:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_file.parent)))

    def open_editor(self):
        if self.clip is None:
            from compact_capture import ClipEditor
            self.clip = ClipEditor(self.host, self.go_back)
            self.outer.addWidget(self.clip)
        self.form.hide()
        self.clip.show()
        if self.last_file and self.clip.file != self.last_file:
            self.clip.open_file(self.last_file)
        self.updateGeometry()

    def go_back(self):
        if self.clip and not self.clip.isHidden():
            self.clip.hide(); self.form.show(); self.updateGeometry()
            return True
        return False


class CleaningPage(Page):
    def __init__(self, host, dismiss):
        super().__init__(host)
        self.dismiss = dismiss
        self.cleaning = QTimer(self)
        self.cleaning.setSingleShot(True)
        self.layout_box.addWidget(label(tr("Clean your screen and keyboard")))
        self.layout_box.addWidget(label(tr("Choose how long to pause input, then start when you’re ready."), True))
        self.duration = QComboBox()
        self.duration.setAccessibleName(tr("Cleaning time"))
        for seconds, title in ((30, tr("30 seconds")), (60, tr("1 minute")), (120, tr("2 minutes"))):
            self.duration.addItem(title, seconds)
        self.duration.setCurrentIndex(max(0, self.duration.findData(self.settings.value("cleaningSeconds", 60, type=int))))
        self.layout_box.addWidget(label(tr("Cleaning time"), True))
        self.layout_box.addWidget(self.duration)
        self.display = QComboBox()
        self.display.setAccessibleName(tr("During cleaning"))
        self.display.addItem(tr("Lock the session"), "lock")
        native = QApplication.platformName().startswith("wayland") and any(
            (Path(root) / "kwin/plugins/monet_cleaning.so").is_file() for root in QApplication.libraryPaths())
        if native:
            self.display.addItem(tr("Darken displays"), "dark")
            self.display.addItem(tr("Keep desktop visible"), "visible")
        self.display.setCurrentIndex(max(0, self.display.findData(self.settings.value("cleaningDisplay", "lock"))))
        self.layout_box.addWidget(label(tr("During cleaning"), True))
        self.layout_box.addWidget(self.display)
        self.detail = label("", True)
        self.layout_box.addWidget(self.detail)
        self.display.currentIndexChanged.connect(self.describe)
        self.duration.activated.connect(self.save_preferences)
        self.display.activated.connect(self.save_preferences)
        self.describe()
        self.layout_box.addStretch()
        self.start = button(tr("Start cleaning"), self.begin, True)
        self.layout_box.addWidget(self.start)

    def describe(self):
        self.detail.setText({
            "lock": tr("Your session locks while you clean. Unlock as usual when you’re finished."),
            "dark": tr("Input pauses and every display darkens until the timer ends. Press Esc five times to finish early."),
            "visible": tr("Your apps stay visible while input pauses. Press Esc five times or choose Finish cleaning to return."),
        }[self.display.currentData()])

    def save_preferences(self, *_):
        self.settings.setValue("cleaningSeconds", self.duration.currentData())
        self.settings.setValue("cleaningDisplay", self.display.currentData())
        self.settings.sync()

    def begin(self):
        seconds, mode = self.duration.currentData(), self.display.currentData()
        self.save_preferences()
        # Keep the Utilities D-Bus owner alive for the entire native input pause.
        # The compositor restores input if its owner exits.
        self.cleaning.start((seconds+3)*1000)
        self.dismiss()
        def start():
            if mode == "lock":
                import window
                self.host.worker([sys.executable, window.MODULES / "cleaning.py", str(seconds)], lambda _: None)
            else:
                self.host.start_desktop_cleaning(seconds, mode == "dark")
        QTimer.singleShot(220, self, start)


def create_page(key, host, dismiss):
    if key in ("text-tools", "color-tools"):
        from quick_text_colors import TextToolsPage, ColorToolsPage
        return (TextToolsPage if key == "text-tools" else ColorToolsPage)(host)
    if key == "lock":
        return CleaningPage(host, dismiss)
    if key in ("plain", "clean"):
        return ClipboardPage(host, key)
    if key == "snippets":
        return SnippetsPage(host)
    if key == "emoji":
        return EmojiPage(host)
    if key in ("record", "recordings"):
        return RecordingPage(host, dismiss)
    raise ValueError("Unknown inline page")
