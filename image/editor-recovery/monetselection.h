// SPDX-License-Identifier: LGPL-2.0-or-later
#pragma once
#include <QJsonArray>
#include <QJsonObject>
#include <QList>
#include <QStringList>

inline bool monetValidSelection(const QJsonValue &value)
{
    if (value.isNull()) return true;
    auto coordinates = [](const QJsonValue &value, int count) {
        if (!value.isArray() || value.toArray().size() != count) return false;
        for (const auto &n : value.toArray())
            if (!n.isDouble() || n.toInt(-1) < 0 || n.toDouble() != n.toInt(-1)) return false;
        return true;
    };
    auto point = [&](const QJsonObject &item) {
        if (!coordinates(item.value(QStringLiteral("cursor")), 2)) return false;
        const auto range = item.value(QStringLiteral("range"));
        if (range.isNull()) return true;
        if (!coordinates(range, 4)) return false;
        const auto r = range.toArray();
        return r[0].toInt() < r[2].toInt() || (r[0] == r[2] && r[1].toInt() <= r[3].toInt());
    };
    const auto item = value.toObject();
    auto keys = item.keys();
    const bool multi = item.contains(QStringLiteral("secondary"));
    if (multi) { keys.removeAll(QStringLiteral("anchor")); keys.removeAll(QStringLiteral("secondary")); }
    if (!value.isObject() || keys != QStringList{QStringLiteral("block"), QStringLiteral("cursor"), QStringLiteral("range")}
        || !item.value(QStringLiteral("block")).isBool() || !point(item)) return false;
    if (!multi) return true;
    const auto anchor = item.value(QStringLiteral("anchor"));
    const auto secondary = item.value(QStringLiteral("secondary"));
    if (item.value(QStringLiteral("block")).toBool() || (!anchor.isNull() && !coordinates(anchor, 2))
        || !secondary.isArray() || secondary.toArray().isEmpty() || secondary.toArray().size() > 1023) return false;
    QList<QJsonArray> cursors{item.value(QStringLiteral("cursor")).toArray()};
    for (const auto &value : secondary.toArray()) {
        const auto entry = value.toObject();
        const auto anchor = entry.value(QStringLiteral("anchor"));
        if (!value.isObject() || entry.keys() != QStringList{QStringLiteral("anchor"), QStringLiteral("cursor"), QStringLiteral("range")}
            || !point(entry) || (!anchor.isNull() && !coordinates(anchor, 2))
            || (!entry.value(QStringLiteral("range")).isNull() && anchor.isNull())) return false;
        const auto cursor = entry.value(QStringLiteral("cursor")).toArray();
        if (cursors.contains(cursor)) return false;
        cursors.append(cursor);
    }
    return true;
}
