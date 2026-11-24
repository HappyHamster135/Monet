"""Regression checks for selection changes while a text offer is in flight."""
import asyncio
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"))
from clipboard_links import Clipboard, LIMIT


class CopiedLinks(unittest.TestCase):
    def setUp(self):
        self.reader = Clipboard.__new__(Clipboard)
        self.reader.loop = asyncio.new_event_loop()
        self.reader.lib = Mock()
        self.reader.input_fd = None
        self.reader.flush = Mock()
        self.addCleanup(self.reader.loop.close)
        self.addCleanup(self.reader.close_input)

    def offer(self, data):
        read_fd, write_fd = os.pipe()
        self.reader.selection(read_fd)
        try:
            os.write(write_fd, data)
        finally:
            os.close(write_fd)
        self.reader.read(read_fd)
        return read_fd

    def test_new_offer_replaces_incomplete_link_and_clear_cancels(self):
        first = self.offer(b"https://example.org/old?utm_campaign=a")
        second = self.offer(b"https://example.org/new?utm_campaign=a")
        self.reader.read(first)
        self.reader.lib.clip_replace.assert_not_called()
        self.reader.read(second)
        clean = b"https://example.org/new"
        self.reader.lib.clip_replace.assert_called_once_with(clean, len(clean))
        self.reader.lib.clip_replace.reset_mock()
        third = self.offer(b"https://example.org/cleared?gclid=z")
        self.reader.selection(-1)
        self.reader.read(third)
        self.reader.lib.clip_replace.assert_not_called()

    def test_large_slow_text_is_bounded_and_never_republished(self):
        read_fd, write_fd = os.pipe()
        self.reader.selection(read_fd)
        try:
            for chunk in (b"https://x/?utm_source=", b"x" * 4096, b"x" * 4096):
                os.write(write_fd, chunk)
                self.reader.read(read_fd)
        finally:
            os.close(write_fd)
        self.assertIsNone(self.reader.input_fd)
        self.assertIsNone(self.reader.buffer)
        self.reader.lib.clip_replace.assert_not_called()

    def test_cleaner_accepts_exact_limit_but_preserves_multiline_and_invalid_utf8(self):
        prefix = b"https://example.org/?utm_source="
        data = prefix.ljust(LIMIT, b"a")
        # Feed in chunks smaller than the minimum Linux pipe capacity.
        read_fd, write_fd = os.pipe()
        self.reader.selection(read_fd)
        for start in range(0, len(data), 2048):
            os.write(write_fd, data[start:start + 2048])
            self.reader.read(read_fd)
        os.close(write_fd)
        self.reader.read(read_fd)
        self.reader.lib.clip_replace.assert_called_once()
        self.reader.lib.clip_replace.reset_mock()
        for data in (prefix + b"x\n", prefix + b"\xff", prefix + b"\x00"):
            fd = self.offer(data)
            self.reader.read(fd)
        self.reader.lib.clip_replace.assert_not_called()
