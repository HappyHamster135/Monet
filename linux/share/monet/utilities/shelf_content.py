"""Values kept on the shared shelf and the native formats used for a drag."""
from dataclasses import dataclass
from hashlib import sha256
from functools import cached_property
import os
from pathlib import Path

from PySide6.QtCore import QMimeData, QUrl


@dataclass(frozen=True)
class ShelfEntry:
    kind: str
    value: str

    @classmethod
    def file(cls, path):
        if isinstance(path, str) and "\0" not in path and os.path.isabs(path):
            return cls("file", os.path.normpath(path))
        return None

    @classmethod
    def from_url(cls, url):
        if url.isValid() and url.isLocalFile() and not url.host():
            return cls.file(url.toLocalFile())
        if url.isValid() and url.scheme() in ("https", "http") and url.host():
            return cls("link", url.toString(QUrl.FullyEncoded))
        return None

    @classmethod
    def from_text(cls, text):
        if not isinstance(text, str) or not text.strip() or "\0" in text:
            return None
        if text[:8].lower().startswith(("https://", "http://")) and not any(c.isspace() for c in text):
            url = QUrl(text, QUrl.StrictMode)
            if url.isValid() and url.host():
                return cls("link", text)
        return cls("text", text)

    @classmethod
    def restore(cls, record):
        # Original installations saved a list of absolute paths.
        if isinstance(record, str):
            return cls.file(record)
        if isinstance(record, dict):
            if isinstance(record.get("link"), str):
                url = QUrl(record["link"], QUrl.StrictMode)
                if url.isValid() and url.scheme() in ("https", "http") and url.host():
                    return cls("link", record["link"])
            if isinstance(record.get("text"), str):
                return cls.from_text(record["text"])
        return None

    def record(self):
        return self.value if self.kind == "file" else {self.kind: self.value}

    def uri(self):
        if self.kind == "file":
            return QUrl.fromLocalFile(self.value).toString(QUrl.FullyEncoded)
        return self.value if self.kind == "link" else ""

    @cached_property
    def key(self):
        if self.kind == "text":
            return "text:" + sha256(self.value.encode("utf-8")).hexdigest()
        return self.uri()

    def name(self):
        if self.kind == "file":
            return Path(self.value).name or self.value
        if self.kind == "link":
            url = QUrl(self.value)
            return url.host() + url.path()
        # Keep even a long single-line selection cheap to lay out.
        preview = " ".join(self.value.lstrip()[:160].split())
        return preview + ("…" if len(self.value.strip()) > 160 else "")


def from_mime(mime):
    if mime.hasUrls():
        entries = [ShelfEntry.from_url(url) for url in mime.urls()]
        return entries if all(entries) else []
    entry = ShelfEntry.from_text(mime.text()) if mime.hasText() else None
    return [entry] if entry else []


def to_mime(entries):
    mime = QMimeData()
    if entries:
        if all(entry.kind != "text" for entry in entries):
            mime.setUrls([QUrl(entry.uri()) for entry in entries])
        mime.setText("\n".join(entry.value for entry in entries))
    return mime
