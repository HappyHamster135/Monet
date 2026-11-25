"""Keep the native result model and dispatch, delaying focus return for Monet app menus."""
from pathlib import Path
import sys


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Unexpected Milou source around {old!r}")
    return text.replace(old, new)


def install(module):
    original = module / "ResultsView.qml"
    output = module / "MonetResultsView.qml"
    text = original.read_text()
    fragment = Path(__file__).with_name("menu-result.qml.inc").read_text()
    text = replace_once(text, "import QtQuick\n", "import QtQuick\nimport org.kde.plasma.workspace.dbus as DBus\n")
    text = replace_once(text, "    function runCurrentIndex(event) {", fragment + "\n    function runCurrentIndex(event) {")
    text = replace_once(text, "onQueryStringChanged: () => {", "onQueryStringChanged: () => {\n            listView.menuRequest = null")
    text = replace_once(text, "resultModel.run(resultModel.index(0, 0));\n                    listView.activated();",
                        "listView.runResult(0, true)")
    text = replace_once(text, "if (resultModel.run(resultModel.index(currentIndex, 0))) {\n                activated()\n            }",
                        "runResult(currentIndex, false)")
    descriptor = module / "qmldir"
    mapping = "ResultsView 254.0 "
    target = mapping + output.name
    manifest = descriptor.read_text()
    # The plugin embeds a second qmldir. Its "prefer" would override the
    # on-disk ResultsView entry as soon as Qt loads the C++ ResultsModel.
    if target not in manifest:
        manifest = replace_once(manifest, "prefer :/qt/qml/org/kde/milou/\n", "")
        manifest = replace_once(manifest, mapping + original.name, target)
    output.write_text(text)
    descriptor.write_text(manifest)


if __name__ == "__main__":
    install(Path(sys.argv[1]).resolve())
