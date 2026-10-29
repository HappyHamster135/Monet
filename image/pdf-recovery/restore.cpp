// SPDX-License-Identifier: GPL-2.0-or-later
#include <QFileInfo>

namespace {
bool monetValidDocumentState(const QJsonObject &state)
{
    if (state.keys() != QStringList{QStringLiteral("active"), QStringLiteral("tabs")}
        || !state.value(QStringLiteral("tabs")).isArray() || !state.value(QStringLiteral("active")).isDouble()) return false;
    const auto tabs = state.value(QStringLiteral("tabs")).toArray();
    const auto active = state.value(QStringLiteral("active"));
    if (tabs.size() > 32 || active.toDouble() != active.toInt(-2)
        || (tabs.isEmpty() ? active.toInt() != -1 : active.toInt() < 0 || active.toInt() >= tabs.size())) return false;
    for (const auto &value : tabs) {
        if (!value.isObject()) return false;
        const auto tab = value.toObject();
        if (tab.keys() != QStringList{QStringLiteral("modified"), QStringLiteral("page"), QStringLiteral("path")}
            || !tab.value(QStringLiteral("path")).isString() || !tab.value(QStringLiteral("modified")).isBool()
            || !tab.value(QStringLiteral("page")).isDouble()) return false;
        const auto page = tab.value(QStringLiteral("page"));
        const auto path = tab.value(QStringLiteral("path")).toString();
        if (page.toDouble() != page.toInt() || page.toInt() < 1 || page.toInt() > 1000000
            || path.size() > 4096 || !QDir::isAbsolutePath(path) || path.startsWith(QStringLiteral("//"))
            || path != QDir::cleanPath(path)) return false;
        for (const auto character : path) {
            if (character.unicode() < 32 || character.unicode() == 127) return false;
        }
    }
    return true;
}
}

bool Shell::monetRestoreDocumentState(const QString &text)
{
    const auto bytes = text.toUtf8();
    if (bytes.size() > 600000 || m_tabs.size() != 1 || !m_tabs[0].part->url().isEmpty() || m_tabs[0].part->isModified()) return false;
    const auto parsed = QJsonDocument::fromJson(bytes);
    const auto state = parsed.object();
    if (!parsed.isObject() || !monetValidDocumentState(state)) return false;
    const auto tabs = state.value(QStringLiteral("tabs")).toArray();
    for (const auto &value : tabs) {
        const QFileInfo file(value.toObject().value(QStringLiteral("path")).toString());
        if (!file.isFile() || !file.isReadable()) return false;
    }
    for (int i = 0; i < tabs.size(); ++i) {
        const auto tab = tabs[i].toObject();
        const auto url = QUrl::fromLocalFile(tab.value(QStringLiteral("path")).toString());
        // A private recovery session keeps its captured tabs without changing global preferences.
        if (i == 0) openUrl(url);
        else openNewTab(url, QString(), true);
        if (m_tabs.size() != i + 1 || m_tabs[i].part->url() != url) return false;
        uint pages = 0;
        const uint page = tab.value(QStringLiteral("page")).toInt();
        if (!QMetaObject::invokeMethod(m_tabs[i].part, "pages", Q_RETURN_ARG(uint, pages)) || page > pages
            || !QMetaObject::invokeMethod(m_tabs[i].part, "goToPage", Q_ARG(uint, page))) return false;
    }
    if (!tabs.isEmpty()) setActiveTab(state.value(QStringLiteral("active")).toInt());
    return true;
}
