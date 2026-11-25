"""Regression checks for linked wallpaper sources, previews and Plasma routing."""
import json
from importlib.util import find_spec
from pathlib import Path
import sys
import tempfile
from threading import Event
import unittest
from unittest.mock import MagicMock, patch

from tests.test_settings_feedback import QT
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "linux/share/monet/utilities"))
if QT:
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QColor, QImage
    from wallpapers import Collection, Wallpaper, apply, catalog, thumbnail


@unittest.skipUnless(QT, "requires Qt image readers")
class Gallery(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.settings = QSettings(str(self.root / "utilities.ini"), QSettings.IniFormat)
        self.c = Collection(self.settings)
        self.stop = Event()

    def picture(self, name):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        image = QImage(640, 360, QImage.Format_RGB32)
        image.fill(QColor("#24b963"))
        self.assertTrue(image.save(str(path)))
        return path

    def scan(self, *roots):
        return catalog(roots, self.c.files, self.c.folders, self.c.hidden, self.stop)

    def test_overlapping_roots_exclusions_and_unmounted_sources(self):
        image = self.picture("photos/nested/landscape.png")
        self.picture("photos/.hidden/private.png")
        self.picture("photos/nested/.hidden.png")
        self.picture("external/photo.png")
        folder = self.root / "photos"
        (folder / "link").symlink_to(self.root / "external", target_is_directory=True)
        (folder / "loop").symlink_to(folder, target_is_directory=True)
        self.c.add([folder, image.parent, self.root / "offline"], folder=True)
        self.c.add([image])
        self.assertEqual([p.target for p in self.scan()], [image])
        self.c.forget(image)
        self.c = Collection(self.settings)
        self.assertEqual(self.scan(), [])
        self.assertIn(self.root / "offline", self.c.folders)
        self.c.forget(folder, folder=True)
        self.assertIn(image, self.c.hidden)
        self.c.add([image])
        self.c.forget(image.parent, folder=True)
        self.assertEqual([p.target for p in self.scan()], [image])
        self.c.forget(image)
        self.assertTrue(image.exists())
        self.assertFalse(Collection(self.settings).hidden)

    def test_package_aliases_resolution_variants_and_cancel(self):
        data = self.root / "wallpapers"
        wide = self.picture("wallpapers/Lake/contents/images/640x360.png")
        self.picture("wallpapers/Lake/contents/images/1080x1920.png")
        package = data / "Lake"
        metadata = {"KPlugin": {"Id": "Lake", "Name": "Quiet lake"}}
        (package / "metadata.json").write_text(json.dumps(metadata))
        (data / "Default").symlink_to(package)
        loose = self.picture("wallpapers/Blue sky.png")
        entries = self.scan(data)
        self.assertEqual([(p.name, p.target, p.preview) for p in entries],
                         [("Blue sky", loose, loose), ("Quiet lake", package, wide)])
        self.assertTrue(all(not p.personal for p in entries))
        self.assertLessEqual(thumbnail(wide).width(), 256)
        self.stop.set()
        self.assertEqual(self.scan(data), [])

    def test_missing_or_corrupt_image_rejected_before_contacting_the_desktop(self):
        path = self.root / "broken.png"
        for present in (False, True):
            if present:
                path.write_bytes(b"damaged")
            with self.assertRaises(ValueError):
                apply(Wallpaper("Missing", path, path))

    @unittest.skipUnless(find_spec("dbus"), "requires the Plasma session bus")
    def test_disconnected_screen_cannot_fall_back_to_all_desktops(self):
        path = self.picture("someone's portrait #1 50%.png")
        service = MagicMock()
        service.evaluateScript.return_value = "false"
        with patch("dbus.SessionBus") as bus, patch("dbus.Interface", return_value=service):
            with self.assertRaises(ValueError):
                apply(Wallpaper("Portrait", path, path), 'DP-1')
        script = service.evaluateScript.call_args.args[0]
        self.assertIn(json.dumps(path.as_uri()), script)
        self.assertIn('screenId >= 0', script)
        self.assertIn(json.dumps("DP-1"), script)
        bus.return_value.close.assert_called_once()
