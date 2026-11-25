// SPDX-License-Identifier: GPL-2.0-or-later
import QtQuick
import org.kde.kitemmodels as Models
import org.kde.kwin as KWin

Models.KSortFilterProxyModel {
    id: proxy

    property string query: ""
    property var words: []
    property var appNames: ({})
    // KWin's ClientModel::WIdRole identifies the same window as Window::internalId.
    readonly property int windowIdRole: Qt.UserRole + 5

    function sourceRow(row) {
        return row < 0 ? -1 : mapToSource(index(row, 0)).row;
    }
    function resultRow(row) {
        return row < 0 || !sourceModel ? -1 : mapFromSource(sourceModel.index(row, 0)).row;
    }
    function readAppNames() {
        const names = {};
        for (const win of (KWin.Workspace?.stackingOrder || []))
            names[String(win.internalId)] = [win.desktopFileName, win.resourceClass].join(" ").toLocaleLowerCase();
        return names;
    }
    function refreshApps() {
        if (!words.length) return;
        appNames = readAppNames();
        invalidateFilter();
    }
    function updateWords(text) {
        query = text;
        const wordsNow = text.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
        if (wordsNow.length && !words.length) appNames = readAppNames();
        const wasSearching = words.length > 0;
        words = wordsNow;
        if (wasSearching !== (words.length > 0))
            filterRowCallback = words.length ? accepts : undefined;
        if (!words.length) appNames = {};
        invalidateFilter();
    }
    Component.onDestruction: filterRowCallback = undefined

    function accepts(row, parentIndex) {
        if (!sourceModel) return false;
        const idx = sourceModel.index(row, 0, parentIndex);
        const caption = String(sourceModel.data(idx, Qt.DisplayRole) || "").toLocaleLowerCase();
        const name = appNames[String(sourceModel.data(idx, windowIdRole))] || "";
        return words.every(word => caption.includes(word) || name.includes(word));
    }
}
