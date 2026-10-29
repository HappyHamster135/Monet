// SPDX-License-Identifier: LGPL-2.0-or-later
void KateFoldingTest::testPersistentFoldingRoundTrip()
{
    DocumentPrivate doc;
    const QString text = QStringLiteral("A line of text.\n").repeated(20);
    doc.setText(text);
    const std::unique_ptr<ViewPrivate> view{static_cast<ViewPrivate *>(doc.createView(nullptr))};
    auto &folding = view->textFolding();
    using F = Kate::TextFolding;
    const Range outer(1, 0, 8, 1), inner(2, 0, 5, 1), other(10, 0, 14, 1);
    folding.newFoldingRange(outer, F::Persistent | F::Folded);
    folding.newFoldingRange(inner, F::Persistent | F::Folded);
    folding.newFoldingRange(other, F::Folded);
    const auto saved = folding.exportFoldingRanges();
    for (int cycle = 0; cycle < 2; ++cycle) {
        folding.importFoldingRanges(saved);
        QCOMPARE(folding.exportFoldingRanges(), saved);
        const auto parents = folding.foldingRangesForParentRange();
        QCOMPARE(parents.size(), 2);
        const auto parent = parents[0].id;
        const auto child = folding.foldingRangesForParentRange(parent)[0].id;
        QVERIFY(!folding.isLineVisible(3));
        QVERIFY(folding.unfoldRange(parent));
        QCOMPARE(folding.foldingRange(parent), outer);
        QVERIFY(folding.isLineVisible(2));
        QVERIFY(!folding.isLineVisible(3));
        QVERIFY(folding.unfoldRange(child));
        QCOMPARE(folding.foldingRange(child), inner);
        QVERIFY(folding.isLineVisible(3));
        QVERIFY(folding.foldRange(child));
        QVERIFY(folding.foldRange(parent));
        QCOMPARE(folding.exportFoldingRanges(), saved);
        QCOMPARE(doc.text(), text);
    }
}
