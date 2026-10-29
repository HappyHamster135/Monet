// SPDX-License-Identifier: LGPL-2.0-or-later
#include <QJsonArray>
void MulticursorTest::testMonetMultiCursorState()
{
    const auto text = QStringLiteral("abcdefghij\nabcdefghij\nabcdefghij");
    auto original = createDocAndView(text, 0, 6);
    original.view->setSecondaryCursors({Cursor(1, 6), Cursor(2, 6)});
    original.view->shiftCursorLeft();
    original.view->shiftCursorLeft();
    const auto saved = original.view->monetSelectionState({});
    QVERIFY(!saved.isEmpty());
    auto restored = createDocAndView(text, 0, 0);
    for (int cycle = 0; cycle < 2; ++cycle) {
        QCOMPARE(restored.view->monetSelectionState(saved), saved);
        QCOMPARE(restored.doc->text(), text);
        restored.view->shiftCursorRight();
        QCOMPARE(restored.view->cursorPosition(), Cursor(0, 5));
        QCOMPARE(restored.view->selectionRange(), Range(0, 5, 0, 6));
        QCOMPARE(restored.view->secondaryCursors().size(), 2);
        for (int i = 0; i < 2; ++i) {
            const auto &cursor = restored.view->secondaryCursors()[i];
            QCOMPARE(cursor.cursor(), Cursor(i + 1, 5));
            QCOMPARE(cursor.anchor, Cursor(i + 1, 6));
            QCOMPARE(cursor.selectionRange(), Range(i + 1, 5, i + 1, 6));
        }
    }
    restored.view->keyDelete();
    QCOMPARE(restored.doc->text(), QStringLiteral("abcdeghij\nabcdeghij\nabcdeghij"));
    QCOMPARE(original.doc->text(), text);

    original.view->setCursors({Cursor(0, 2), Cursor(1, 3), Cursor(2, 4)});
    const auto carets = original.view->monetSelectionState({});
    QVERIFY(!carets.isEmpty());
    QCOMPARE(restored.view->monetSelectionState(carets), carets);
    original.view->shiftCursorRight();
    restored.view->shiftCursorRight();
    QCOMPARE(restored.view->monetSelectionState({}), original.view->monetSelectionState({}));
}

void MulticursorTest::testMonetMultiCursorValidation()
{
    const auto text = QStringLiteral("abcdefghij\nabcdefghij\nabcdefghij");
    auto original = createDocAndView(text, 0, 6);
    original.view->setSecondaryCursors({Cursor(1, 6), Cursor(2, 6)});
    original.view->shiftCursorLeft();
    const auto saved = original.view->monetSelectionState({});
    for (const auto &change : {QJsonObject{{QStringLiteral("block"), true}}, QJsonObject{{QStringLiteral("anchor"), QJsonArray{true, 1}}},
                              QJsonObject{{QStringLiteral("secondary"), QJsonArray{}}}, QJsonObject{{QStringLiteral("text"), QStringLiteral("not allowed")}}}) {
        auto bad = saved;
        for (auto it = change.begin(); it != change.end(); ++it) bad.insert(it.key(), it.value());
        QVERIFY(original.view->monetSelectionState(bad).isEmpty());
        QCOMPARE(original.view->monetSelectionState({}), saved);
    }
    auto bad = saved;
    auto secondary = saved.value(QStringLiteral("secondary")).toArray();
    auto first = secondary[0].toObject();
    first.insert(QStringLiteral("anchor"), QJsonValue::Null);
    secondary[0] = first;
    bad.insert(QStringLiteral("secondary"), secondary);
    QVERIFY(original.view->monetSelectionState(bad).isEmpty());
    QCOMPARE(original.view->monetSelectionState({}), saved);
    auto shortFile = createDocAndView(QStringLiteral("a"), 0, 0);
    shortFile.view->monetSelectionState(saved);
    QCOMPARE(shortFile.view->cursorPosition(), Cursor(0, 1));
    QVERIFY(shortFile.view->secondaryCursors().empty());
    QCOMPARE(shortFile.doc->text(), QStringLiteral("a"));
    QCOMPARE(original.doc->text(), text);
    original.view->setCursors({Cursor(2, 0), Cursor(1, 0)});
    shortFile.view->monetSelectionState(original.view->monetSelectionState({}));
    QCOMPARE(shortFile.view->cursorPosition(), Cursor(0, 1));
    QVERIFY(shortFile.view->secondaryCursors().empty());
}
