// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <window.h>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSet>
#include <QSettings>

class MouseExceptions
{
public:
    void reload()
    {
        QSettings settings("Monet", "MouseEnhancements");
        settings.sync();
        const auto apps = QJsonDocument::fromJson(settings.value("applications").toByteArray()).object();
        names.clear();
        for (auto it = apps.begin(); it != apps.end(); ++it) {
            if (!it.key().endsWith(".desktop") || it.key().contains('/') || !it.value().isArray()) continue;
            names.insert(name(it.key()));
            for (const auto &alias : it.value().toArray()) {
                if (alias.isString() && !alias.toString().isEmpty()) names.insert(name(alias.toString()));
            }
        }
    }

    bool matches(const KWin::Window *window) const
    {
        if (names.isEmpty()) return false;
        // An explicitly identified window takes precedence over its transient parent.
        for (int depth = 0; window && depth < 16; ++depth, window = window->transientFor()) {
            const auto desktop = window->desktopFileName();
            if (!desktop.isEmpty()) return names.contains(name(desktop));
            const auto wmClass = window->resourceClass();
            if (!wmClass.isEmpty()) return names.contains(name(wmClass));
        }
        return false;
    }

private:
    static QString name(QString id)
    {
        id = id.section('/', -1).toCaseFolded();
        if (id.endsWith(".desktop")) id.chop(8);
        return id;
    }
    QSet<QString> names;
};
