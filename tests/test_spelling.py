"""Verify real Hunspell ranking against disposable copies of image dictionaries."""
import ctypes
import ctypes.util
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("monet_spelling", ROOT / "image/spelling/patch.py")
spelling = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(spelling)
DICTIONARIES = Path("/usr/share/hunspell")
LIBRARY = ctypes.util.find_library("hunspell-1.7")


class DictionaryPatch(unittest.TestCase):
    def test_idempotent_and_preserves_existing_rules_and_non_ascii(self):
        for encoding in ("UTF-8", "ISO8859-1"):
            original = f"SET {encoding}\nTRY esiaé\nREP 1\nREP f ph\nSFX A Y 0\n"
            result = spelling.patched(original, ["REP ^im$ I'm", "REP f ph"])
            self.assertIn("REP 2\n", result)
            self.assertIn("REP f ph\nSFX A Y 0\n", result)
            self.assertIn("TRY esiaé\n", result)
            self.assertEqual(spelling.patched(result, ["REP ^im$ I'm"]), result)

    def test_changed_upstream_tables_stop_before_any_dictionary_is_written(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            original = "SET UTF-8\nREP 1\nREP f ph\n"
            for language in spelling.LANGUAGES:
                (directory / f"{language}.aff").write_text(original)
            (directory / "en_AU.aff").write_text("SET UTF-8\nREP 3\nREP f ph\n")
            with self.assertRaises(ValueError): spelling.main(directory)
            self.assertEqual((directory / "en_US.aff").read_text(), original)


@unittest.skipUnless(LIBRARY and all((DICTIONARIES / f"{lang}.dic").exists()
                                  for lang in spelling.LANGUAGES), "English Hunspell dictionaries and runtime")
class NativeSuggestions(unittest.TestCase):
    def test_common_typos_rank_first_without_changing_valid_words(self):
        lib = ctypes.CDLL(LIBRARY)
        char_list = ctypes.POINTER(ctypes.c_char_p)
        lib.Hunspell_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        lib.Hunspell_create.restype = ctypes.c_void_p
        lib.Hunspell_destroy.argtypes = [ctypes.c_void_p]
        lib.Hunspell_spell.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.Hunspell_suggest.argtypes = [ctypes.c_void_p, ctypes.POINTER(char_list), ctypes.c_char_p]
        lib.Hunspell_free_list.argtypes = [ctypes.c_void_p, ctypes.POINTER(char_list), ctypes.c_int]
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            originals = {}
            for language in spelling.LANGUAGES:
                for suffix in ("aff", "dic"):
                    source = DICTIONARIES / f"{language}.{suffix}"
                    shutil.copyfile(source, directory / source.name)
                originals[language] = (directory / f"{language}.dic").read_bytes()
            spelling.main(directory)
            for language in spelling.LANGUAGES:
                with self.subTest(language=language):
                    self.assertEqual((directory / f"{language}.dic").read_bytes(), originals[language])
                    handle = lib.Hunspell_create(str(directory / f"{language}.aff").encode(),
                                                str(directory / f"{language}.dic").encode())
                    self.assertTrue(handle)
                    try:
                        for word, wanted in [("im", "I'm"), ("Im", "I'm"), ("ive", "I've"),
                                             ("preformace", "performance"), ("Preformace", "Performance"),
                                             ("PREFORMACE", "PERFORMANCE"), ("dont", "don't"),
                                             ("youre", "you're"), ("definately", "definitely"),
                                             ("recieve", "receive"), ("instalation", "installation"),
                                             ("teh", "the"), ("seperate", "separate")]:
                            with self.subTest(word=word):
                                suggestions = char_list()
                                count = lib.Hunspell_suggest(handle, ctypes.byref(suggestions), word.encode())
                                try:
                                    self.assertGreater(count, 0)
                                    self.assertEqual(suggestions[0].decode("ascii"), wanted)
                                finally:
                                    lib.Hunspell_free_list(handle, ctypes.byref(suggestions), count)
                        # Never force context-sensitive contractions onto valid
                        # English words, code fragments or a substring of a word.
                        for word in ("image", "import", "simple", "ill", "well", "were", "its", "lets", "wont"):
                            self.assertTrue(lib.Hunspell_spell(handle, word.encode()), (language, word))
                    finally:
                        lib.Hunspell_destroy(handle)


if __name__ == "__main__":
    unittest.main()
