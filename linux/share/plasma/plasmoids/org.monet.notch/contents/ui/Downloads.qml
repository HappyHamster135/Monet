import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.notificationmanager as NM
import org.kde.plasma.workspace.dbus as DBus

ColumnLayout {
    id: page
    spacing: 8
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
        Layout.fillWidth: true; spacing: 6
        IslandGlyph { source: "download"; color: "#8ddbb5"; Layout.preferredWidth: 18; Layout.preferredHeight: 18 }
        Text {
            Layout.fillWidth: true; Layout.minimumWidth: 0; textFormat: Text.PlainText; elide: Text.ElideMiddle
            text: page.localPath || i18n("Choose a downloads folder"); color: "#b9bac4"; font.pixelSize: 12

        }
        IslandButton {
            plain: true; icon.name: "view-refresh"; text: i18n("Refresh downloads")
            enabled: !page.checking; onClicked: page.refreshRequested()
        }
        IslandButton {
            plain: true; icon.name: "folder-open"; text: i18n("Open downloads folder")
            enabled: !!page.directory && !page.opener.busy
            onClicked: page.opener.open(page.directory, true, this)
        }
        IslandButton {
            plain: true; icon.name: "configure"; text: i18n("Manage watched folder")
            onClicked: page.manageRequested()
        }
    }
    C.Label {
        Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText
        visible: text.length > 0; text: page.opener.error || page.shelfMessage
        maximumLineCount: 2; elide: Text.ElideMiddle
    }
    C.ScrollView {
        id: scroll
        implicitWidth: 240; implicitHeight: 180
        Layout.fillWidth: true; Layout.fillHeight: true; clip: true
        contentWidth: availableWidth
        Layout.minimumHeight: 0
        ColumnLayout {
            width: scroll.availableWidth
            spacing: 6
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
            IslandEmpty {
                Layout.fillWidth: true; Layout.preferredHeight: Math.max(90, scroll.availableHeight)
                visible: !(page.feed?.recent.length)
                symbol: "folder-download"; tint: "#8ddbb5"
                title: page.checking || (page.feed && !page.feed.ready && !page.feed.unavailable) ? i18n("Checking downloads…")
                    : page.feed && !page.feed.unavailable ? i18n("No recent files") : i18n("Folder unavailable")
                detail: page.feed && !page.feed.unavailable ? i18n("New downloads will appear here.") : i18n("Choose a folder to watch from the folder settings.")
            }
            Repeater {
                model: page.feed?.recent ?? []
                delegate: Rectangle {
                    id: file
                    required property var modelData
                    Layout.fillWidth: true; implicitHeight: 58
                    color: "#19191e"; radius: 12
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 9; spacing: 10
                        Rectangle {
                            Layout.preferredWidth: 34; Layout.preferredHeight: 34; radius: 10; color: "#24332e"
                            Kirigami.Icon { anchors.centerIn: parent; width: 19; height: width; isMask: true; color: "#8ddbb5"
                                source: file.modelData.partial ? "go-down-symbolic" : "text-x-generic" }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 3
                            Text {
                                Layout.fillWidth: true; textFormat: Text.PlainText; elide: Text.ElideMiddle
                                text: file.modelData.name; color: "#ededf2"; font.pixelSize: 12; font.weight: Font.Medium

                            }
                            Text {
                                Layout.fillWidth: true; color: file.modelData.partial ? "#8ddbb5" : "#9696a2"
                                text: file.modelData.partial ? i18n("Downloading · %1", file.modelData.size) : file.modelData.size
                                textFormat: Text.PlainText; elide: Text.ElideRight; font.pixelSize: 11
                            }
                        }
                        IslandButton {
                            visible: !file.modelData.partial; enabled: !page.opener.busy; plain: true
                            icon.name: "folder-open"; text: i18n("Show %1 in Files", file.modelData.name)
                            onClicked: page.opener.open(file.modelData.url, false, this)
                        }
                        IslandButton {
                            visible: page.offerShelf && !file.modelData.partial; enabled: !page.shelfReply; plain: true
                            icon.name: "folder-add"; text: i18n("Add %1 to file shelf", file.modelData.name)
                            onClicked: page.addToShelf(file.modelData)
                        }
                    }
                }
            }
        }
    }
}
