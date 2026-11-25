import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.notificationmanager as NM
import org.kde.plasma.workspace.dbus as DBus

ColumnLayout {
    id: page
    required property var feed
    property bool offerShelf: true
    required property bool checking
    required property string localPath
    required property url directory
    required property var opener
    signal backRequested()
    signal manageRequested()
    signal refreshRequested()
    property DBus.DBusPendingReply shelfReply
    property string shelfName: ""
    property string shelfMessage: ""
    function addToShelf(row) {
        shelfName = row.name
        shelfMessage = ""
        shelfReply = DBus.SessionBus.asyncCall({service: "org.monet.Utilities", path: "/Utilities",
            iface: "org.monet.Utilities", member: "AddToShelf", signature: "(s)", arguments: [row.url]})
        if (shelfReply.isFinished) finishShelf()
    }
    function finishShelf() {
        if (!shelfReply || !shelfReply.isFinished) return
        shelfMessage = shelfReply.isValid && shelfReply.value === true ? i18n("Added %1 to the file shelf.", shelfName)
            : i18n("Could not add %1 to the file shelf.", shelfName)
        shelfReply = null
    }
    Connections { target: page.shelfReply; function onFinished() { page.finishShelf() } }

    RowLayout {
        Layout.fillWidth: true
        C.ToolButton { text: i18n("Activity"); icon.name: "go-previous"; onClicked: page.backRequested() }
        Item { Layout.fillWidth: true }
        C.ToolButton {
            icon.name: "view-refresh"; Accessible.name: i18n("Refresh downloads")
            C.ToolTip.text: Accessible.name; C.ToolTip.visible: hovered
            enabled: !page.checking; onClicked: page.refreshRequested()
        }
        C.ToolButton {
            text: i18n("Folder…"); icon.name: "folder-download"
            Accessible.name: i18n("Manage watched folder"); onClicked: page.manageRequested()
        }
    }
    C.Label {
        Layout.fillWidth: true; textFormat: Text.PlainText; elide: Text.ElideMiddle
        text: page.localPath; Accessible.name: text
        C.ToolTip.text: text; C.ToolTip.visible: truncated && pathHover.hovered
        HoverHandler { id: pathHover }
    }
    C.Label {
        Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText
        visible: text.length > 0; text: page.opener.error || page.shelfMessage
        maximumLineCount: 2; elide: Text.ElideMiddle
    }
    C.ScrollView {
        id: scroll
        Layout.fillWidth: true; Layout.fillHeight: true; clip: true
        contentWidth: availableWidth
        ColumnLayout {
            width: scroll.availableWidth
            Repeater {
                model: NM.Notifications {
                    groupMode: NM.Notifications.GroupDisabled
                    showNotifications: false; showJobs: true; showExpired: false; showDismissed: false
                }
                delegate: ColumnLayout {
                    required property var model
                    readonly property var job: model.jobDetails
                    readonly property string dest: String(job?.effectiveDestUrl || "") || String(job?.destUrl || "")
                    readonly property string base: String(page.directory)
                    readonly property string prefix: base.endsWith("/") ? base : base + "/"
                    visible: !!page.feed && !!job && job.state !== NM.Notifications.JobStateStopped && !!base &&
                             (dest === base || dest.slice(0, dest.lastIndexOf("/") + 1) === prefix)
                    Layout.fillWidth: true
                    C.Label {
                        Layout.fillWidth: true; elide: Text.ElideMiddle; textFormat: Text.PlainText
                        text: job?.summary ?? ""
                    }
                    C.ProgressBar {
                        Layout.fillWidth: true; from: 0; to: 100; value: job?.percentage ?? 0
                        visible: value > 0 || (job?.totalBytes ?? 0) > 0
                        Accessible.name: parent.job?.summary ?? ""
                    }
                }
            }
            C.Label {
                Layout.fillWidth: true; wrapMode: Text.Wrap
                visible: !(page.feed?.recent.length)
                text: page.checking || (page.feed && !page.feed.ready && !page.feed.unavailable) ? i18n("Checking downloads…")
                    : page.feed && !page.feed.unavailable ? i18n("No recent files in this folder.") : i18n("The watched folder is unavailable.")
            }
            Repeater {
                model: page.feed?.recent ?? []
                delegate: RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    Kirigami.Icon {
                        Layout.preferredWidth: 20; Layout.preferredHeight: 20
                        source: modelData.partial ? "folder-download" : "text-x-generic"
                    }
                    ColumnLayout {
                        Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 0
                        C.Label {
                            Layout.fillWidth: true; textFormat: Text.PlainText; elide: Text.ElideMiddle
                            text: modelData.name
                            C.ToolTip.text: text; C.ToolTip.visible: truncated && fileHover.hovered
                            HoverHandler { id: fileHover }
                        }
                        C.Label {
                            Layout.fillWidth: true; color: Kirigami.Theme.disabledTextColor
                            text: modelData.partial ? i18n("Partial download") : modelData.size
                        }
                    }
                    C.ToolButton {
                        visible: !modelData.partial; enabled: !page.opener.busy
                        icon.name: "folder-open"; Accessible.name: i18n("Show %1 in Files", modelData.name)
                        C.ToolTip.text: i18n("Show in Files"); C.ToolTip.visible: hovered
                        onClicked: page.opener.open(modelData.url, false, this)
                    }
                    C.ToolButton {
                        visible: page.offerShelf && !modelData.partial; enabled: !page.shelfReply; icon.name: "folder-add"
                        Accessible.name: i18n("Add %1 to file shelf", modelData.name)
                        C.ToolTip.text: i18n("Add to file shelf"); C.ToolTip.visible: hovered
                        onClicked: page.addToShelf(modelData)
                    }
                }
            }
        }
    }
}
