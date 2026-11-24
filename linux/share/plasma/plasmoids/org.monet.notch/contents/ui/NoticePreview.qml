// Mounted only while previews are enabled on an unlocked, active desktop.
import QtQuick
import org.kde.notificationmanager as NM

NM.Notifications {
    id: feed
    property int noticeId: 0
    property string title: ""
    property string sender: ""
    property bool watching: true
    onWatchingChanged: {
        since = Date.now()
        newest = since
        seenAtNewest = []
        resetPreview()
    }
    property double since: Date.now()
    property double newest: since
    property var seenAtNewest: []
    readonly property NM.Settings preferences: NM.Settings {}
    readonly property Timer timeout: Timer { interval: 5000; onTriggered: feed.resetPreview() }

    showNotifications: true
    showJobs: false
    showExpired: false
    showDismissed: false
    showAddedDuringInhibition: false
    blacklistedDesktopEntries: preferences.popupBlacklistedApplications
    blacklistedNotifyRcNames: preferences.popupBlacklistedServices
    urgencies: NM.Notifications.CriticalUrgency | NM.Notifications.NormalUrgency
               | (preferences.lowPriorityPopups ? NM.Notifications.LowUrgency : 0)
    groupMode: NM.Notifications.GroupDisabled
    sortMode: NM.Notifications.SortByDate
    sortOrder: Qt.DescendingOrder
    limit: 8

    function resetPreview() {
        timeout.stop()
        noticeId = 0
        sender = ""
        title = ""
    }
    function updatePreview() {
        // A model reset, wake or removal can expose an older row at the top.
        // Keep each actual delivery separate from these changes to the view.
        if (!watching) return
        let currentPresent = false
        let next = null
        let seen = seenAtNewest.slice()
        for (let row = 0; row < count; ++row) {
            const entry = index(row, 0)
            const id = data(entry, NM.Notifications.IdRole)
            if (id === noticeId) currentPresent = true
            const created = data(entry, NM.Notifications.CreatedRole)
            const updated = data(entry, NM.Notifications.UpdatedRole)
            const stamp = Math.max(Number(created) || 0, Number(updated) || 0)
            if (stamp <= since || stamp < newest || (stamp === newest && seen.includes(id)) || (next && stamp < next.stamp)) continue
            if (stamp > (next ? next.stamp : newest)) seen = []
            seen.push(id)
            if (!next || stamp > next.stamp) next = {entry, id, stamp}
        }
        if (next) {
            newest = next.stamp
            seenAtNewest = seen
            const heading = data(next.entry, NM.Notifications.SummaryRole)
            sender = data(next.entry, NM.Notifications.ApplicationNameRole) || ""
            title = heading || sender || i18n("Notification")
            noticeId = next.id
            timeout.restart()
        } else if (noticeId && !currentPresent) resetPreview()
    }
    readonly property Timer changed: Timer { interval: 0; onTriggered: feed.updatePreview() }
    onRowsInserted: changed.restart()
    onRowsRemoved: changed.restart()
    onDataChanged: changed.restart()
    onModelReset: changed.restart()
}
