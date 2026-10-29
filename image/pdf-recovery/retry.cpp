// SPDX-License-Identifier: GPL-2.0-or-later
namespace {
struct MonetPdfAppend {
    QJsonObject request;
    QPointer<KParts::ReadWritePart> part;
    QString status;
};
QHash<Shell *, QHash<QString, MonetPdfAppend>> monetPdfAppends;
}

QString Shell::monetAppendDocument(const QString &text)
{
    const auto bytes = text.toUtf8();
    if (bytes.size() > 650000) return QStringLiteral("invalid");
    const auto parsed = QJsonDocument::fromJson(bytes);
    const auto request = parsed.object();
    const auto before = request.value(QStringLiteral("before")).toObject();
    const auto tab = request.value(QStringLiteral("tab")).toObject();
    const auto attempt = request.value(QStringLiteral("attempt")).toString();
    const auto id = request.value(QStringLiteral("window")).toString();
    static const QRegularExpression validAttempt(QStringLiteral("\\A[0-9a-f]{32}\\z"));
    if (!parsed.isObject() || request.keys() != QStringList{QStringLiteral("attempt"), QStringLiteral("before"), QStringLiteral("tab"), QStringLiteral("window")}
        || !validAttempt.match(attempt).hasMatch() || QUuid(id).isNull() || !monetValidDocumentState(before)
        || !monetValidDocumentState(QJsonObject{{QStringLiteral("active"), 0}, {QStringLiteral("tabs"), QJsonArray{tab}}})
        || tab.value(QStringLiteral("modified")).toBool()) return QStringLiteral("invalid");

    QPointer<Shell> window;
    const auto windows = monetDocumentIdentities();
    if (windows.isEmpty()) return QStringLiteral("unconfirmed");
    for (const auto &[candidate, currentId] : windows) {
        if (currentId == id) window = candidate;
    }
    if (!window) return QStringLiteral("closed");
    if (monetPdfAppends.value(window).contains(attempt)) {
        const auto previous = monetPdfAppends.value(window).value(attempt);
        if (previous.request != request) return QStringLiteral("conflict");
        if (previous.status == QStringLiteral("opened") && !previous.part) return QStringLiteral("closed");
        return previous.status;
    }
    if (QApplication::activeModalWidget()) return QStringLiteral("busy");
    const auto current = QJsonDocument::fromJson(window->monetDocumentState().toUtf8());
    if (!current.isObject() || current.object() != before) return QStringLiteral("conflict");
    if (before.value(QStringLiteral("tabs")).toArray().size() >= 32 || monetPdfAppends.value(window).size() >= 128)
        return QStringLiteral("limit");
    const auto path = tab.value(QStringLiteral("path")).toString();
    const QFileInfo file(path);
    if (!file.isFile() || !file.isReadable()) return QStringLiteral("unavailable");
    if (!monetPdfAppends.contains(window)) {
        connect(window, &QObject::destroyed, qApp, [owner = window.data()] { monetPdfAppends.remove(owner); });
    }
    // Retain the attempt before opening: a lost reply or nested dialog must not replay it.
    monetPdfAppends[window].insert(attempt, {request, nullptr, QStringLiteral("busy")});
    const int originalCount = before.value(QStringLiteral("tabs")).toArray().size();
    const QPointer<KParts::ReadWritePart> active = originalCount ? window->m_tabs[window->m_tabWidget->currentIndex()].part : nullptr;
    const auto url = QUrl::fromLocalFile(path);
    if (originalCount) window->openNewTab(url, QString(), true);
    else window->openUrl(url);
    if (!window) return QStringLiteral("closed");
    QPointer<KParts::ReadWritePart> part;
    QString status = QStringLiteral("unconfirmed");
    if (window->m_tabs.size() == originalCount + 1 && window->m_tabs[originalCount].part->url() == url) {
        part = window->m_tabs[originalCount].part;
        uint pages = 0;
        const uint page = tab.value(QStringLiteral("page")).toInt();
        if (QMetaObject::invokeMethod(part, "pages", Q_RETURN_ARG(uint, pages)) && page <= pages
            && QMetaObject::invokeMethod(part, "goToPage", Q_ARG(uint, page))) status = QStringLiteral("opened");
    }
    if (active) {
        for (int i = 0; i < window->m_tabs.size(); ++i) {
            if (window->m_tabs[i].part == active) window->setActiveTab(i);
        }
    }
    monetPdfAppends[window][attempt] = {request, part, status};
    return status;
}
