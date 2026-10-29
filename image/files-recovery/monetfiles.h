// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <QDir>
#include <QJsonArray>
#include <QJsonObject>
#include <QUrl>

inline QString monetLocalPath(const QUrl &url)
{
    if (!url.isLocalFile() || !url.authority().isEmpty() || url.hasQuery() || url.hasFragment()) return {};
    const auto path = QDir::cleanPath(url.toLocalFile());
    if (!path.startsWith(QLatin1Char('/')) || path.size() > 8192) return {};
    for (const auto c : path) if (c.unicode() < 32) return {};
    return path;
}

inline bool monetWithin(const QString &path, const QString &folder)
{
    return !path.isEmpty() && path != folder && path.startsWith(folder == QStringLiteral("/") ? folder : folder + QLatin1Char('/'));
}
