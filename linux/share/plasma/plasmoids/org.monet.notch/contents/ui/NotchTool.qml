import QtQuick
import QtQuick.Controls as C
import org.kde.plasma.workspace.dbus as DBus

Item {
    id: page
    required property string tool
    required property bool active
    required property string screenName
    required property string ownerId
    signal dismissRequested()
    signal backRequested()
    property string token: ""
    property bool failed: false
    readonly property bool ownsSurface: releasing || (active && !!token && !failed)
    property DBus.DBusPendingReply pending
    property DBus.DBusPendingReply releasePending
    property bool releasing: false
    property var afterRelease: null
    function call(data) {
        return DBus.SessionBus.asyncCall({service:"org.monet.Utilities", path:"/NotchTools", iface:"org.monet.Utilities",
            member:"Tool", signature:"(s)", arguments:[JSON.stringify(data)]})
    }
    function closeSurface() {
        if (token) call({action:"close", id:token})
        token = ""; pending = null
    }
    function releaseForNavigation(callback) {
        afterRelease = callback
        if (releasing) return
        releasing = true
        pending = null
        if (!token) { releaseFinished(); return }
        const previous = token
        token = ""
        releasePending = call({action:"close", id:previous})
        if (releasePending.isFinished) releaseFinished()
    }
    function releaseFinished() {
        if (releasePending && !releasePending.isFinished) return
        const callback = afterRelease
        releasePending = null
        afterRelease = null
        releasing = false
        if (callback) callback()
    }
    Connections { target: page.releasePending; function onFinished() { page.releaseFinished() } }
    function reposition() {
        if (!active || releasing || width < 40 || height < 24) return
        const at = mapToGlobal(0, 0)
        if (!token) token = ownerId + "." + Date.now() + "." + Math.floor(Math.random()*100000)
        failed = false
        pending = call({action:"show", id:token, key:tool, screen:screenName, x:at.x, y:at.y, w:width, h:height})
        if (pending.isFinished) finished()
    }
    function finished() {
        if (!pending?.isFinished) return
        try { failed = !pending.isValid || !JSON.parse(String(pending.value)).ok } catch (_) { failed = true }
        pending = null
    }
    Connections { target: page.pending; function onFinished() { page.finished() } }
    DBus.SignalWatcher {
        enabled: page.ownsSurface; busType: DBus.BusType.Session; service:"org.monet.Utilities"
        path:"/NotchTools"; iface:"org.monet.Utilities"
        function dbusToolClosed(id, goBack) {
            if (id === page.token) {
                if (goBack) page.backRequested()
                else page.dismissRequested()
            }
        }
    }
    Timer { id: layout; interval: 0; onTriggered: page.reposition() }
    Component.onCompleted: layout.restart()
    Component.onDestruction: closeSurface()
    onToolChanged: { closeSurface(); layout.restart() }
    onScreenNameChanged: layout.restart()
    onWidthChanged: layout.restart()
    onHeightChanged: layout.restart()
    onReleasingChanged: if (!releasing && active) layout.restart()
    onActiveChanged: if (active) layout.restart(); else closeSurface()
    C.Button {
        visible: page.failed; anchors.centerIn: parent; text: i18n("Could not open tool. Retry")
        onClicked: page.reposition()
    }
    C.BusyIndicator { anchors.centerIn: parent; running: !!page.pending; visible: running }
}
