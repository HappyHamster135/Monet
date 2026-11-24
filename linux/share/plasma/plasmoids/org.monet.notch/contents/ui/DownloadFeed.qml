import QtQuick
import org.kde.coreaddons as KCore
import org.kde.private.desktopcontainment.folder as Folder
import org.kde.kitemmodels as Models

// The caller creates this only for a verified directory while Activity is open.
// Use the desktop directory lister so special characters in local paths survive.
Folder.FolderModel {
    id: feed
    required property url directory
    property var recent: []
    readonly property string latestFinished: recent.find(row => !row.partial)?.name ?? ""
    readonly property bool ready: status === Folder.FolderModel.Ready
    readonly property bool unavailable: !!errorString || status === Folder.FolderModel.Canceled
    readonly property int urlRole: feed.Models.KRoleNames.role("url")
    readonly property int sizeRole: feed.Models.KRoleNames.role("size")
    readonly property int dirRole: feed.Models.KRoleNames.role("isDir")
    url: String(directory)
    sortMode: 2 // KDirModel::ModifiedTime
    sortDesc: true
    sortDirsFirst: false
    parseDesktopFiles: false
    previews: false

    function collect() {
        if (unavailable) { recent = []; return }
        if (!ready) return
        const baseUrl = String(directory)
        const prefix = baseUrl.endsWith("/") ? baseUrl : baseUrl + "/"
        const rows = [], partialNames = new Set()
        // Read metadata only for recent files. No delegate is created for older entries.
        const count = rowCount()
        for (let i = 0; i < count && rows.length < 64; ++i) {
            const idx = index(i, 0)
            if (data(idx, dirRole)) continue
            const url = String(data(idx, urlRole)), end = url.lastIndexOf("/") + 1
            if (url.slice(0, end) !== prefix) continue
            let name
            try { name = decodeURIComponent(url.slice(end)) } catch (_) { continue }
            const suffix = /\.(?:part|crdownload|opdownload|download)$/i.exec(name)
            const base = suffix ? name.slice(0, -suffix[0].length) : name
            if (suffix) {
                partialNames.add(base)
                // Firefox may create name.ext, then write name.<nonce>.ext.part.
                const moz = /^(.+)\.[\w-]{8}(\.[^.]+)$/.exec(base)
                if (moz) partialNames.add(moz[1] + moz[2])
                const trailing = /^(.+)\.[\w-]{8}$/.exec(base)
                if (trailing) partialNames.add(trailing[1])
            }
            rows.push({name: name, url: url, partial: !!suffix,
                       size: data(idx, sizeRole)})
        }
        const emptySize = KCore.Format.formatByteSize(0)
        recent = rows.filter(row => row.partial || row.size !== emptySize || !partialNames.has(row.name)).slice(0, 12)
    }
    function queueUpdate() { Qt.callLater(collect) }
    onDirectoryChanged: recent = []
    onStatusChanged: queueUpdate()
    onRowsInserted: queueUpdate()
    onRowsRemoved: queueUpdate()
    onErrorStringChanged: queueUpdate()
    onDataChanged: queueUpdate()
    onModelReset: queueUpdate()
    onLayoutChanged: queueUpdate()
    Component.onCompleted: queueUpdate()
}
