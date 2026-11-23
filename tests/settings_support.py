"""Settings source audits and waits for pages compiled on demand."""
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]


def qml_source(path):
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.name == "MonetSettings.qml":
        text += "\n" + "\n".join(p.read_text(encoding="utf-8")
                                 for p in sorted(path.parent.glob("Settings*.qml")))
    return text


def settings_source():
    return qml_source(ROOT / "linux/share/monet/settings-app/MonetSettings.qml")


def select_settings_page(window, page):
    from PySide6.QtTest import QTest
    window.setProperty("page", page)
    deadline = time.monotonic() + 5
    while not window.property("pageReady") and time.monotonic() < deadline:
        QTest.qWait(10)
    if not window.property("pageReady"):
        raise AssertionError("Settings page did not load: " + page)
