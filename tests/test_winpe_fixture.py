"""The VM harness only creates image files and preserves existing evidence."""
import importlib.util
import errno
import random
import tempfile
import unittest
from unittest import mock
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "winpe_fixture", Path(__file__).resolve().parents[1] / "tools/test-winpe.py")
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


class SparseFixtureTests(unittest.TestCase):
    def test_large_partition_offset_and_discontiguous_extents(self):
        # Buffered reads combined with descriptor-level SEEK_DATA/HOLE used to
        # skip bytes here, corrupting the extracted NTFS metadata in the full VM.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / "source", root / "destination"
            offset = 257 * fixture.MIB
            fixture.sparse(source, offset + 8 * fixture.MIB)
            data = random.Random(11).randbytes(5 * fixture.MIB)
            with source.open("r+b") as stream:
                stream.seek(offset)
                stream.write(data[:12288])
                stream.seek(offset + 16384)
                stream.write(data)
            fixture.copy_region(source, destination, offset, 8 * fixture.MIB)
            with source.open("rb") as stream:
                stream.seek(offset)
                expected = stream.read(8 * fixture.MIB)
            self.assertEqual(destination.read_bytes(), expected)
            fallback = root / "fallback"
            with mock.patch.object(fixture.os, "copy_file_range", side_effect=OSError(errno.EXDEV, "different filesystems")):
                fixture.copy_region(source, fallback, offset, 8 * fixture.MIB)
            self.assertEqual(fallback.read_bytes(), expected)

    def test_region_offsets_holes_and_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / "source", root / "destination"
            fixture.sparse(source, 8 * fixture.MIB)
            with source.open("r+b") as stream:
                for offset, data in [(123, b"excluded"), (2 * fixture.MIB + 17, b"included"),
                                     (6 * fixture.MIB - 2, b"boundary")]:
                    stream.seek(offset)
                    stream.write(data)
            fixture.copy_region(source, destination, fixture.MIB, 5 * fixture.MIB)
            self.assertEqual(destination.read_bytes(), source.read_bytes()[fixture.MIB:6 * fixture.MIB])
            # The copy must remain sparse on a filesystem that supports holes.
            if source.stat().st_blocks * 512 < source.stat().st_size / 2:
                self.assertLess(destination.stat().st_blocks * 512, destination.stat().st_size / 2)

    def test_existing_evidence_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / "source", root / "destination"
            source.write_bytes(b"new")
            destination.write_bytes(b"existing evidence")
            with self.assertRaises(FileExistsError):
                fixture.copy_region(source, destination, 0, 3)
            self.assertEqual(destination.read_bytes(), b"existing evidence")

    def test_out_of_range_region_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / "source", root / "destination"
            source.write_bytes(b"small")
            fixture.sparse(destination, 20)
            for offset, length in [(-1, 3), (2, -1), (4, 2)]:
                with self.subTest(offset=offset, length=length), self.assertRaises(ValueError):
                    fixture.copy_sparse(source, destination, source_offset=offset, length=length)


if __name__ == "__main__":
    unittest.main()
