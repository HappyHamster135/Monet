// SPDX-License-Identifier: GPL-2.0-or-later
#include "monetfiles.h"

QJsonObject DolphinView::monetViewState() const
{
    const auto folder = monetLocalPath(url());
    if (folder.isEmpty() || m_loadingState != LoadingState::Completed || rootItem().url() != url()
        || selectedItemsCount() > 4096 || m_model->expandedDirectories().size() > 256) return {};
    auto paths = [&](const auto &urls, QJsonArray &result) {
        QStringList ordered;
        for (const auto &url : urls) {
            const auto path = monetLocalPath(url);
            if (!monetWithin(path, folder)) return false;
            ordered.append(path);
        }
        ordered.removeDuplicates();
        ordered.sort();
        for (const auto &path : ordered) result.append(path);
        return true;
    };
    QJsonArray selected, expanded;
    if (!paths(selectedItems().urlList(), selected) || !paths(m_model->expandedDirectories(), expanded)) return {};
    QJsonValue current(QJsonValue::Null);
    const int index = m_container->controller()->selectionManager()->currentItem();
    if (index >= 0) {
        const auto path = monetLocalPath(m_model->fileItem(index).url());
        if (!monetWithin(path, folder)) return {};
        current = path;
    }
    const auto horizontal = m_container->horizontalScrollBar();
    const auto vertical = m_container->verticalScrollBar();
    return {{QStringLiteral("current"), current}, {QStringLiteral("selected"), selected},
            {QStringLiteral("expanded"), expanded},
            {QStringLiteral("scroll"), QJsonArray{horizontal->value(), vertical->value()}},
            {QStringLiteral("maximum"), QJsonArray{horizontal->maximum(), vertical->maximum()}}};
}
