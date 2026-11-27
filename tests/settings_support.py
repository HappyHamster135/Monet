"""Settings source audits and waits for pages compiled on demand."""
from pathlib import Path
import json
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


def visual_item(window, name):
    """Find a visual child without wrapping unrelated private KDE types in Python."""
    from PySide6.QtQml import QQmlEngine, QQmlExpression
    expression = QQmlExpression(QQmlEngine.contextForObject(window), window, """
        (function() {
            const pending = [contentItem];
            while (pending.length) {
                const item = pending.pop();
                if (item.objectName === %s) return item;
                for (const child of item.children) pending.push(child);
            }
            return null;
        })()
    """ % json.dumps(name))
    result, _ = expression.evaluate()
    if expression.hasError():
        raise AssertionError(expression.error().toString())
    return result


def select_settings_page(window, page):
    from PySide6.QtTest import QTest
    window.setProperty("page", page)
    deadline = time.monotonic() + 5
    while not window.property("pageReady") and time.monotonic() < deadline:
        QTest.qWait(10)
    if not window.property("pageReady"):
        raise AssertionError("Settings page did not load: " + page)
