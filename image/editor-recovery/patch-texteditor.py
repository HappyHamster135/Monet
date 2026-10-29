#!/usr/bin/python3
"""Retain both native folding flags and add a regression to the upstream suite."""
from pathlib import Path
import shutil
import sys


def patch(root):
    path = root / "src/buffer/katetextfolding.cpp"
    source = path.read_text(encoding="utf-8")
    before = "if (rawFlags & Folded) {\n            flags = Folded;\n        }"
    if source.count(before) != 1:
        raise ValueError("Upstream text folding import changed")
    path.write_text(source.replace(before, before.replace("flags =", "flags |=")), encoding="utf-8")
    header = root / "autotests/src/katefoldingtest.h"
    source = header.read_text(encoding="utf-8")
    before = "    void testUnfoldingInImportFoldingRanges();"
    if source.count(before) != 1:
        raise ValueError("Upstream folding test declaration changed")
    header.write_text(source.replace(before, before + "\n    void testPersistentFoldingRoundTrip();"), encoding="utf-8")
    test = root / "autotests/src/katefoldingtest.cpp"
    source = test.read_text(encoding="utf-8")
    before = '#include "moc_katefoldingtest.cpp"'
    if source.count(before) != 1:
        raise ValueError("Upstream folding test changed")
    addition = Path(__file__).with_name("textfolding-test.cpp").read_text(encoding="utf-8")
    test.write_text(source.replace(before, addition + "\n" + before), encoding="utf-8")
    header = root / "src/view/kateview.h"
    source = header.read_text(encoding="utf-8")
    before = "    QList<PlainSecondaryCursor> plainSecondaryCursors() const;"
    if source.count(before) != 1:
        raise ValueError("Upstream secondary cursor API changed")
    source = source.replace(before, before + "\n    Q_INVOKABLE QJsonObject monetSelectionState(const QJsonObject &state);")
    before = "#include <QJsonDocument>"
    if source.count(before) != 1:
        raise ValueError("Upstream view includes changed")
    header.write_text(source.replace(before, before + "\n#include <QJsonObject>"), encoding="utf-8")
    view = root / "src/view/kateview.cpp"
    source = view.read_text(encoding="utf-8")
    before = '#include "moc_kateview.cpp"'
    if source.count(before) != 1:
        raise ValueError("Upstream view implementation changed")
    addition = Path(__file__).with_name("multicursor.cpp").read_text(encoding="utf-8")
    view.write_text(source.replace(before, addition + "\n" + before), encoding="utf-8")
    shutil.copyfile(Path(__file__).with_name("monetselection.h"), root / "src/view/monetselection.h")
    header = root / "autotests/src/multicursortest.h"
    source = header.read_text(encoding="utf-8")
    before = "    static void testSetGetSelections();"
    if source.count(before) != 1:
        raise ValueError("Upstream multicursor test declaration changed")
    header.write_text(source.replace(before, before + "\n    static void testMonetMultiCursorState();\n    static void testMonetMultiCursorValidation();"), encoding="utf-8")
    test = root / "autotests/src/multicursortest.cpp"
    source = test.read_text(encoding="utf-8")
    before = '#include "moc_multicursortest.cpp"'
    if source.count(before) != 1:
        raise ValueError("Upstream multicursor test changed")
    addition = Path(__file__).with_name("multicursor-test.cpp").read_text(encoding="utf-8")
    test.write_text(source.replace(before, addition + "\n" + before), encoding="utf-8")


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
