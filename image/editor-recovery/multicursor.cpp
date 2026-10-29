// SPDX-License-Identifier: LGPL-2.0-or-later
#include "monetselection.h"

QJsonObject KTextEditor::ViewPrivate::monetSelectionState(const QJsonObject &state)
{
    if (!state.isEmpty()) {
        if (!monetValidSelection(state) || !state.contains(QStringLiteral("secondary")) || isMulticursorNotAllowed()) return {};
        auto cursor = [this](const QJsonArray &value, int index = 0) {
            const int line = value[index].toInt();
            if (line >= doc()->lines()) return doc()->documentEnd();
            return KTextEditor::Cursor(line, qMin(value[index + 1].toInt(), qMax(0, doc()->lineLength(line))));
        };
        auto range = [&](const QJsonValue &value) {
            return value.isNull() ? KTextEditor::Range::invalid() : KTextEditor::Range(cursor(value.toArray()), cursor(value.toArray(), 2));
        };
        QPointer<ViewPrivate> alive(this);
        clearSecondaryCursors();
        setCursorPosition(cursor(state.value(QStringLiteral("cursor")).toArray()));
        if (!alive) return {};
        setSelection(range(state.value(QStringLiteral("range"))));
        if (!alive) return {};
        m_viewInternal->m_selectAnchor = state.value(QStringLiteral("anchor")).isNull()
            ? KTextEditor::Cursor::invalid() : cursor(state.value(QStringLiteral("anchor")).toArray());
        QList<KTextEditor::Cursor> positions{cursorPosition()};
        for (const auto &value : state.value(QStringLiteral("secondary")).toArray()) {
            const auto entry = value.toObject();
            const auto position = cursor(entry.value(QStringLiteral("cursor")).toArray());
            if (positions.contains(position)) continue; // Shortened files can collapse several cursors onto one point.
            positions.append(position);
            SecondaryCursor secondary;
            secondary.pos.reset(static_cast<Kate::TextCursor *>(doc()->newMovingCursor(position)));
            const auto selection = range(entry.value(QStringLiteral("range")));
            if (selection.isValid()) secondary.range.reset(newSecondarySelectionRange(selection));
            secondary.anchor = entry.value(QStringLiteral("anchor")).isNull()
                ? KTextEditor::Cursor::invalid() : cursor(entry.value(QStringLiteral("anchor")).toArray());
            m_secondaryCursors.push_back(std::move(secondary));
            tagLine(position);
        }
        sortCursors();
        paintCursors();
    }
    if (m_secondaryCursors.empty() || m_secondaryCursors.size() > 1023) return {};
    auto cursor = [](KTextEditor::Cursor value) -> QJsonValue {
        return value.isValid() ? QJsonValue(QJsonArray{value.line(), value.column()}) : QJsonValue(QJsonValue::Null);
    };
    auto point = [&](KTextEditor::Cursor position, KTextEditor::Range range, KTextEditor::Cursor anchor) {
        return QJsonObject{{QStringLiteral("cursor"), cursor(position)}, {QStringLiteral("anchor"), cursor(anchor)},
            {QStringLiteral("range"), range.isValid() ? QJsonValue(QJsonArray{range.start().line(), range.start().column(),
                range.end().line(), range.end().column()}) : QJsonValue(QJsonValue::Null)}};
    };
    auto result = point(cursorPosition(), selectionRange(), m_viewInternal->m_selectAnchor);
    result.insert(QStringLiteral("block"), false);
    QJsonArray secondary;
    for (const auto &item : m_secondaryCursors) secondary.append(point(item.cursor(), item.selectionRange(), item.anchor));
    result.insert(QStringLiteral("secondary"), secondary);
    return monetValidSelection(result) ? result : QJsonObject{};
}
