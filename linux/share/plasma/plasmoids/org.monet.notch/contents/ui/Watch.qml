import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as C
import org.kde.kirigami as Kirigami
import org.kde.plasma.workspace.dbus as DBus

ColumnLayout {
    id: page
    required property string service
    required property string path
    signal backRequested()
    signal editing()
    readonly property string iface: "org.monet.WindowWatch"
    property DBus.DBusPendingReply request
    property bool dirty: false
    property string imageUrl: ""
    property bool failed: false

    function call(member) {
        return DBus.SessionBus.asyncCall({service: service, path: path, iface: iface, member: member})
    }
    function refresh() {
        if (request) {
            dirty = true
            return
        }
        dirty = false
        request = call("Frame")
        if (request.isFinished) settle()
    }
    function settle() {
        if (!request || !request.isFinished) return
        failed = !request.isValid
        imageUrl = failed ? "" : String(request.value || "")
        request = null
        if (dirty) Qt.callLater(refresh)
    }
    Connections {
        target: page.request
        function onFinished() { page.settle() }
    }
    DBus.SignalWatcher {
        busType: DBus.BusType.Session
        service: page.service; path: page.path; iface: page.iface
        function dbusChanged() { page.refresh() }
    }
    Component.onCompleted: refresh()

    RowLayout {
        Layout.fillWidth: true
        C.ToolButton {
            icon.name: "go-previous"; Accessible.name: i18n("Back to activity")
            onClicked: page.backRequested()
        }
        C.Label { Layout.fillWidth: true; text: i18n("Watched region"); font.bold: true }
        C.ToolButton { text: i18n("Stop watching"); onClicked: page.call("Stop") }
    }
    Item {
        Layout.fillWidth: true; Layout.fillHeight: true
        Image {
            id: picture; objectName: "notchWatchImage"
            anchors.fill: parent; fillMode: Image.PreserveAspectFit
            source: page.imageUrl; cache: false
            Accessible.role: Accessible.Graphic; Accessible.name: i18n("Live window preview")
        }
        C.Label {
            anchors.centerIn: parent; visible: !page.imageUrl || picture.status === Image.Error
            text: page.failed || picture.status === Image.Error ? i18n("Preview unavailable") : i18n("Waiting for the window…")
        }
    }
    C.Button {
        Layout.alignment: Qt.AlignHCenter; text: i18n("Edit region and alerts")
        onClicked: { page.call("Edit"); page.editing() }
    }
}
