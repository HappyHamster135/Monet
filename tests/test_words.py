"""Monet's words in other languages: the catalogs in po/, what
tools/make-translations.py builds from them, and how Monet finds them.

    python3 -m unittest discover -s tests
"""

import gettext
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALE = ROOT / "linux/share/locale"
LANGUAGES = sorted(p.stem for p in (ROOT / "po").glob("*.po"))


class Catalogs(unittest.TestCase):
    def test_catalog_is_current_and_keeps_every_placeholder(self):
        out = subprocess.run([sys.executable, str(ROOT / "tools/make-translations.py"), "--check"],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def test_every_language_is_built(self):
        self.assertGreaterEqual(len(LANGUAGES), 20)
        for language in LANGUAGES:
            self.assertTrue((LOCALE / language / "LC_MESSAGES/monet.mo").is_file(), language)
            self.assertTrue((ROOT / "setup/locale" / language / "LC_MESSAGES/monet-setup.mo").is_file(), language)

    def test_gettext_reads_them_plurals_and_all(self):
        words = gettext.translation("monet", localedir=str(LOCALE), languages=["ru"])
        self.assertNotEqual(words.gettext("Finish setting up Windows"), "Finish setting up Windows")
        # Russian counts 1, 3 and 5 games three ways.
        self.assertEqual(len({words.ngettext("%1 game", "%1 games", n) for n in (1, 3, 5)}), 3)


class Finding(unittest.TestCase):
    def test_widgets_and_the_painting_find_monets_words(self):
        # Plasma looks for a widget's words under plasma_applet_<its id>.
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('plasma_applet_${applet##*/}.mo', install)
        self.assertIn("plasma_wallpaper_org.monet.hours.mo", install)
        self.assertIn('"$DATADIR/monet/names.tsv"', install)
        uninstall = (ROOT / "linux/uninstall.sh").read_text()
        self.assertIn("plasma_applet_org.monet.*.mo", uninstall)
        self.assertIn('"$REPO/setup/locale"', (ROOT / "image/setup/build.sh").read_text())

    def test_kdes_own_screens_ask_for_monets_words_by_name(self):
        # The lock and shut-down screens, the widget explorer, edit mode and the
        # password dialog run in KDE's programs, whose words are KDE's.
        share = ROOT / "linux/share/monet"
        for qml in (share / "lockscreen/MonetLockScreen.qml", share / "logout/Logout.qml",
                    share / "explorer/MonetWidgetExplorer.qml", share / "editmode/MonetDesktopEditMode.qml",
                    ROOT / "image/password/QuickAuthDialog.qml"):
            text = qml.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\bi18n[cp]{0,2}\(", text), qml.name)
            self.assertIn('i18nd("monet"', text.replace("i18ndc(", "i18nd(").replace("i18ndp(", "i18nd("), qml.name)

    def test_menu_entries_and_widgets_carry_their_names(self):
        desktop = (ROOT / "linux/share/applications/monet-settings.desktop").read_text(encoding="utf-8")
        self.assertIn("Name[de]=", desktop)
        meta = json.loads((ROOT / "linux/share/plasma/plasmoids/org.monet.quick/metadata.json").read_text(encoding="utf-8"))
        self.assertIn("Name[ja]", meta["KPlugin"])

    def test_scripts_say_monets_words(self):
        # monet-quick say: the text in the session's language with its %1 filled in, English without one.
        source = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            quick = Path(tmp) / "monet-quick"
            quick.write_text(source.replace("@DATADIR@", (ROOT / "linux/share").as_posix()), encoding="utf-8")
            env = {k: v for k, v in os.environ.items() if k not in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")}

            def say(language, *words):
                return subprocess.run([sys.executable, str(quick), "say", *words], capture_output=True, text=True,
                                      encoding="utf-8", env={**env, "LANGUAGE": language}).stdout

            self.assertEqual(say("C", "Monet %1 is here", "0.9"), "Monet 0.9 is here\n")
            german = say("de", "Monet %1 is here", "0.9")
            self.assertIn("0.9", german)
            self.assertNotEqual(german, "Monet 0.9 is here\n")


if __name__ == "__main__":
    unittest.main()
