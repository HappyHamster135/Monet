"""Exact distribution sources remain available after repository metadata rotates."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("source_rpm", ROOT / "image/download-source-rpm.py")
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)
NAME = "plasma-systemmonitor-6.8.2-1.fc45.src.rpm"
KEY = "655a4b02f577861e"
SIGNATURE = "RSA/SHA256, date, Key ID " + KEY


class SourceRpm(unittest.TestCase):
    def test_archive_url_is_pinned_to_installed_source_and_signer(self):
        with patch.object(source, "query", return_value=f"{NAME}\nFedora Project\n{SIGNATURE}"):
            name, key, url = source.source_info("plasma-systemmonitor")
        self.assertEqual((name, key), (NAME, KEY))
        self.assertEqual(url, "https://kojipkgs.fedoraproject.org/packages/plasma-systemmonitor/6.8.2/1.fc45/data/signed/f577861e/src/" + NAME)

    def test_invalid_package_source_vendor_or_signature_is_rejected(self):
        with self.assertRaises(ValueError):
            source.source_info("--querytags")
        for value in (f"../../evil.src.rpm\nFedora Project\n{SIGNATURE}",
                      f"{NAME}\nOther Vendor\n{SIGNATURE}",
                      f"{NAME}\nFedora Project\n(none)"):
            with self.subTest(value=value), patch.object(source, "query", return_value=value), self.assertRaises(ValueError):
                source.source_info("plasma-systemmonitor")

    def test_verified_signature_still_requires_exact_source_and_signer(self):
        for identity in (f"other-1-1.fc45.src.rpm\n1\n{SIGNATURE}",
                         f"{NAME}\n0\n{SIGNATURE}",
                         f"{NAME}\n1\nRSA/SHA256, date, Key ID 1234567812345678"):
            with self.subTest(identity=identity), patch.object(source.subprocess, "run"), \
                    patch.object(source, "query", return_value=identity), self.assertRaises(ValueError):
                source.verify(Path("archive"), NAME, KEY)

    def test_signature_failure_stops_before_reading_package_metadata(self):
        with patch.object(source.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "rpmkeys")) as run, \
                patch.object(source, "query") as query, self.assertRaises(subprocess.CalledProcessError):
            source.verify(Path("archive"), NAME, KEY)
        query.assert_not_called()
        self.assertIn("_pkgverify_level all", run.call_args.args[0])

    def test_failed_verification_leaves_no_downloaded_source(self):
        import io
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(source, "source_info", return_value=(NAME, KEY, "https://example.test/source")), \
                patch.object(source.urllib.request, "urlopen", return_value=io.BytesIO(b"bad archive")), \
                patch.object(source, "verify", side_effect=ValueError("bad signature")):
            with self.assertRaises(ValueError):
                source.download("plasma-systemmonitor", temporary)
            self.assertEqual(list(Path(temporary).iterdir()), [])
