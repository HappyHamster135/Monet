import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.notificationmanager as NM

ColumnLayout {
    id: inbox
    property int requestedNotice: 0
    property var liveSource: null
    signal previewFinished()
    signal activated()
    readonly property bool inDetail: !!selection
    property var selection: null
    property var detail: ({})
    property var toRemove: []
    property bool canClear: false
    spacing: Kirigami.Units.smallSpacing
    NM.Settings { id: preferences }
    NM.Notifications {
        id: history
        showNotifications: true
        showJobs: preferences.jobsInNotifications
        showExpired: true
        showDismissed: false
        ignoreBlacklistDuringInhibition: true
        blacklistedDesktopEntries: preferences.historyBlacklistedApplications
        blacklistedNotifyRcNames: preferences.historyBlacklistedServices
        urgencies: NM.Notifications.CriticalUrgency | NM.Notifications.NormalUrgency
                   | (preferences.lowPriorityHistory ? NM.Notifications.LowUrgency : 0)
        groupMode: NM.Notifications.GroupDisabled
        sortMode: NM.Notifications.SortByDate
        sortOrder: Qt.DescendingOrder
        limit: 50
        onDataChanged: (first, last, roles) => {
            if (!roles.length || roles.includes(NM.Notifications.ClosableRole)) clearAvailability.restart()
            inbox.scheduleUpdate()
        }
        onRowsRemoved: { clearAvailability.restart(); inbox.scheduleUpdate() }
        onRowsInserted: { clearAvailability.restart(); inbox.scheduleUpdate() }
        onModelReset: { clearAvailability.restart(); inbox.scheduleUpdate() }
    }
    Connections {
        target: inbox.liveSource
        function onDataChanged() { inbox.scheduleUpdate() }
        function onRowsRemoved() { inbox.scheduleUpdate() }
        function onModelReset() { inbox.scheduleUpdate() }
    }
    onLiveSourceChanged: if (inDetail) refresh.restart()
    function scheduleUpdate() {
        if (inDetail) refresh.restart()
    }
    function findEntry(item) {
        const source = item?.live ? liveSource : history
        if (item && source) {
            for (let i = 0; i < source.count; ++i) {
                const entry = source.index(i, 0)
                if (source.data(entry, NM.Notifications.IdRole) === item.id
                    && source.data(entry, NM.Notifications.TypeRole) === item.kind) return entry
            }
        }
        return null
    }
    function show(item) {
        replyField.clear()
        selection = item
        refreshDetail()
        if (inDetail) backButton.forceActiveFocus(Qt.OtherFocusReason)
    }
    function cancelClear() {
        toRemove = []
        clearButton.forceActiveFocus(Qt.BacktabFocusReason)
    }
    function back() {
        const previous = selection
        selection = null
        detail = {}
        replyField.clear()
        if (previous?.live) previewFinished()
        const entry = previous?.live ? null : findEntry(previous)
        if (entry) list.currentIndex = entry.row
        list.forceActiveFocus(Qt.OtherFocusReason)
    }
    Timer { id: refresh; interval: 0; onTriggered: inbox.refreshDetail() }
    function refreshDetail() {
        if (!selection) return
        const entry = findEntry(selection)
        if (!entry) { back(); return }
        const source = selection.live ? liveSource : history
        const read = role => source.data(entry, role)
        detail = {
            app: read(NM.Notifications.ApplicationNameRole) || "", summary: read(NM.Notifications.SummaryRole) || "",
            body: read(NM.Notifications.BodyRole) || "",
            defaultLabel: read(NM.Notifications.HasDefaultActionRole) ? read(NM.Notifications.DefaultActionLabelRole) || i18n("Open") : "",
            names: read(NM.Notifications.ActionNamesRole) || [], labels: read(NM.Notifications.ActionLabelsRole) || [],
            canReply: !!read(NM.Notifications.HasReplyActionRole), replyHint: read(NM.Notifications.ReplyPlaceholderTextRole) || i18n("Reply…"),
            closable: !!read(NM.Notifications.ClosableRole), progress: read(NM.Notifications.PercentageRole) || 0
        }
    }
    function openRequested() {
        if (requestedNotice) show({id: requestedNotice, kind: NM.Notifications.NotificationType, live: true})
    }
    Timer { id: openRequest; interval: 0; onTriggered: inbox.openRequested() }
    onRequestedNoticeChanged: if (requestedNotice) openRequest.restart()
    Component.onCompleted: {
        clearAvailability.restart()
        if (requestedNotice) openRequest.restart()
    }
    function action(kind, value) {
        // Find the sender's current item again. Other apps may have inserted,
        // replaced or withdrawn notifications since this button was painted.
        const entry = findEntry(selection)
        if (!entry) { back(); return }
        const source = selection.live ? liveSource : history
        const read = role => source.data(entry, role)
        source.window = inbox.Window.window
        const behavior = read(NM.Notifications.ResidentRole) ? NM.Notifications.None : NM.Notifications.Close
        if (kind === "default" && read(NM.Notifications.HasDefaultActionRole)) {
            source.invokeDefaultAction(entry, behavior)
            activated()
        } else if (kind === "action" && (read(NM.Notifications.ActionNamesRole) || []).includes(value)) {
            source.invokeAction(entry, value, behavior)
        } else if (kind === "reply" && read(NM.Notifications.HasReplyActionRole) && value.trim()) {
            source.reply(entry, value, behavior)
            replyField.clear()
        } else if (kind === "dismiss" && read(NM.Notifications.ClosableRole)) source.close(entry)
    }
    function removable(entry) {
        return history.data(entry, NM.Notifications.TypeRole) === NM.Notifications.NotificationType
                && history.data(entry, NM.Notifications.ClosableRole)
    }
    function deliveryTime(entry) {
        return Math.max(Number(history.data(entry, NM.Notifications.CreatedRole)) || 0,
                        Number(history.data(entry, NM.Notifications.UpdatedRole)) || 0)
    }
    Timer {
        id: clearAvailability
        interval: 0
        onTriggered: {
            for (let i = 0; i < history.count; ++i) {
                if (inbox.removable(history.index(i, 0))) { inbox.canClear = true; return }
            }
            inbox.canClear = false
        }
    }
    function askClear() {
        const pending = []
        for (let i = 0; i < history.count; ++i) {
            const entry = history.index(i, 0)
            if (removable(entry))
                pending.push({id: history.data(entry, NM.Notifications.IdRole), stamp: deliveryTime(entry)})
        }
        toRemove = pending
        if (pending.length) cancelButton.forceActiveFocus(Qt.OtherFocusReason)
    }
    function clearListed() {
        for (const item of toRemove) {
            const entry = findEntry({id: item.id, kind: NM.Notifications.NotificationType})
            if (entry && removable(entry) && deliveryTime(entry) === item.stamp) history.close(entry)
        }
        toRemove = []
    }
    RowLayout {
        Layout.fillWidth: true
        C.ToolButton {
            id: backButton
            visible: inbox.inDetail
            text: i18n("Back to notifications"); display: C.AbstractButton.IconOnly
            icon.name: "go-previous"; onClicked: inbox.back()
            C.ToolTip.visible: hovered; C.ToolTip.text: text
        }
        C.Label {
            Layout.fillWidth: true; font.bold: true
            text: inbox.inDetail ? inbox.detail.app || i18n("Notification") : i18n("Notifications")
            textFormat: Text.PlainText; elide: Text.ElideRight
        }
        C.ToolButton {
            id: clearButton
            visible: !inbox.toRemove.length && (inbox.inDetail ? !!inbox.detail.closable : inbox.canClear)
            text: inbox.inDetail ? i18n("Dismiss notification") : i18n("Clear notifications…")
            display: C.AbstractButton.IconOnly
            icon.name: inbox.inDetail ? "window-close" : "edit-clear-history"
            C.ToolTip.visible: hovered; C.ToolTip.text: text
            onClicked: if (inbox.inDetail) inbox.action("dismiss"); else inbox.askClear()
        }
    }
    ColumnLayout {
        Layout.fillWidth: true; Layout.fillHeight: true
        visible: inbox.toRemove.length > 0
        C.Label { Layout.fillWidth: true; text: i18n("Remove these notifications from desktop history?"); wrapMode: Text.Wrap }
        Keys.onEscapePressed: inbox.cancelClear()
        RowLayout {
            C.Button { id: cancelButton; text: i18n("Cancel"); onClicked: inbox.cancelClear() }
            C.Button { text: i18n("Clear"); onClicked: inbox.clearListed() }
        }
    }
    ListView {
        id: list
        visible: !inbox.inDetail && !inbox.toRemove.length
        Layout.fillWidth: true; Layout.fillHeight: true
        model: history; clip: true; boundsBehavior: Flickable.StopAtBounds
        C.ScrollBar.vertical: C.ScrollBar {}
        function selectCurrent() { if (currentItem) currentItem.clicked() }
        Keys.onReturnPressed: selectCurrent()
        Keys.onEnterPressed: selectCurrent()
        delegate: C.ItemDelegate {
            required property int index
            required property var model
            width: list.width
            highlighted: list.activeFocus && ListView.isCurrentItem
            Accessible.name: [model.applicationName, model.summary].filter(Boolean).join(". ")
            onClicked: { list.currentIndex = index; inbox.show({id: model.notificationId, kind: model.type}) }
            contentItem: RowLayout {
                Kirigami.Icon { source: model.applicationIconName || "notifications"; Layout.preferredWidth: 20; Layout.preferredHeight: 20 }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 0
                    C.Label { Layout.fillWidth: true; textFormat: Text.PlainText; elide: Text.ElideRight; text: model.summary || model.applicationName }
                    C.Label { Layout.fillWidth: true; textFormat: Text.PlainText; elide: Text.ElideRight; opacity: 0.72; font: Kirigami.Theme.smallFont; text: model.applicationName || "" }
                }
                C.Label {
                    readonly property var timestamp: Number(model.updated) ? model.updated : model.created
                    text: !timestamp ? "" : timestamp.toDateString() === new Date().toDateString()
                          ? Qt.formatTime(timestamp, Qt.locale().timeFormat(Locale.ShortFormat))
                          : Qt.formatDate(timestamp, Qt.locale().dateFormat(Locale.ShortFormat))
                    font: Kirigami.Theme.smallFont
                }
            }
        }
        C.Label { anchors.centerIn: parent; visible: !list.count; text: i18n("No recent notifications") }
    }
    C.ScrollView {
        id: details
        visible: inbox.inDetail
        Layout.fillWidth: true; Layout.fillHeight: true; clip: true
        contentWidth: availableWidth
        ColumnLayout {
            width: details.availableWidth
            C.Label {
                Layout.fillWidth: true; textFormat: Text.PlainText; wrapMode: Text.Wrap
                text: inbox.detail.summary || ""; font.bold: true
            }
            C.Label {
                Layout.fillWidth: true; visible: !!text
                // The desktop already sanitizes notification markup. Omit inline images.
                text: (inbox.detail.body || "").replace(/<img\b[^>]*>/gi, "")
                textFormat: Text.StyledText; wrapMode: Text.Wrap
                onLinkActivated: link => { if (/^https?:\/\//i.test(link)) Qt.openUrlExternally(link) }
            }
            C.ProgressBar {
                visible: inbox.selection?.kind === NM.Notifications.JobType
                Layout.fillWidth: true; to: 100; value: inbox.detail.progress || 0
            }
            component NoticeAction: C.Button {
                width: Math.min(implicitWidth, details.availableWidth)
                contentItem: C.Label {
                    text: parent.text; textFormat: Text.PlainText; elide: Text.ElideRight
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                }
                C.ToolTip.visible: hovered && contentItem.truncated
                C.ToolTip.text: text
            }
            Flow {
                Layout.fillWidth: true; spacing: Kirigami.Units.smallSpacing
                NoticeAction {
                    visible: !!text; text: inbox.detail.defaultLabel || ""
                    onClicked: inbox.action("default")
                }
                Repeater {
                    model: inbox.detail.names || []
                    NoticeAction {
                        required property string modelData
                        required property int index
                        text: inbox.detail.labels?.[index] || modelData
                        onClicked: inbox.action("action", modelData)
                    }
                }
            }
            RowLayout {
                visible: !!inbox.detail.canReply; Layout.fillWidth: true
                C.TextField {
                    id: replyField
                    Layout.fillWidth: true; Accessible.name: i18n("Reply")
                    placeholderText: inbox.detail.replyHint || ""
                    onAccepted: inbox.action("reply", text)
                }
                C.ToolButton {
                    text: i18n("Send reply"); icon.name: "mail-send"; display: C.AbstractButton.IconOnly
                    enabled: replyField.text.trim().length > 0
                    onClicked: inbox.action("reply", replyField.text)
                }
            }
        }
    }
}
