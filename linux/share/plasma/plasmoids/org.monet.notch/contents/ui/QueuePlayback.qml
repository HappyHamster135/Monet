import QtQuick
import org.kde.plasma.private.mpris as Mpris
import org.kde.plasma.workspace.dbus as DBus

// Keep an accepted click alive if the popup closes before the player changes track.
Item {
    id: action
    visible: false
    readonly property bool busy: !!owner
    property string failedOwner: ""
    property string owner: ""
    property string targetId: ""
    property string originalId: ""
    property var player: null
    property string operation: ""
    property bool metadataChangedDuringRead: false
    property DBus.DBusPendingReply reply
    readonly property string path: "/org/mpris/MediaPlayer2"
    readonly property string playerInterface: "org.mpris.MediaPlayer2.Player"

    function finish(failed) {
        deadline.stop()
        failedOwner = failed ? owner : ""
        operation = ""
        reply = null
        owner = ""
        player = null
    }
    function send(step, iface, member, signature, args) {
        operation = step
        reply = DBus.SessionBus.asyncCall({service: owner, path: path, iface: iface,
            member: member, signature: signature, arguments: args})
        checkReply()
    }
    function choose(serviceOwner, current, target, sourcePlayer) {
        if (busy || !serviceOwner || !target || !sourcePlayer?.canPlay || !sourcePlayer.canControl) return
        failedOwner = ""
        originalId = current
        targetId = target
        player = sourcePlayer
        owner = serviceOwner
        deadline.start()
        send("skip", "org.mpris.MediaPlayer2.TrackList", "GoTo", "(o)", [target])
    }
    function readTrack() {
        metadataChangedDuringRead = false
        send("read", "org.freedesktop.DBus.Properties", "Get", "(ss)", [playerInterface, "Metadata"])
    }
    function confirmed(id) {
        if (id === targetId) {
            if (!player?.canPlay) finish(true)
            else if (player.playbackStatus === Mpris.PlaybackStatus.Playing) finish(false)
            else send("play", playerInterface, "Play", "()", [])
        } else if (id && id !== originalId) {
            finish(false)
        }
    }
    function checkReply() {
        if (!reply?.isFinished) return
        if (!reply.isValid) { finish(true); return }
        if (operation === "skip") readTrack()
        else if (operation === "read") {
            if (metadataChangedDuringRead) { readTrack(); return }
            const id = String(reply.value?.["mpris:trackid"] || "")
            reply = null
            operation = "wait"
            confirmed(id)
        } else if (operation === "play") finish(false)
    }
    Connections { target: action.reply; function onFinished() { action.checkReply() } }
    DBus.SignalWatcher {
        busType: DBus.BusType.Session; service: action.owner; path: action.path
        iface: "org.freedesktop.DBus.Properties"; enabled: action.busy
        function dbusPropertiesChanged(iface, changed, invalidated) {
            if (String(iface) !== action.playerInterface || (changed.Metadata === undefined && !invalidated.includes("Metadata"))) return
            if (action.operation === "read") { action.metadataChangedDuringRead = true; return }
            if (action.operation !== "wait") return
            if (changed.Metadata !== undefined) action.confirmed(String(changed.Metadata["mpris:trackid"] || ""))
            else if (invalidated.includes("Metadata")) action.readTrack()
        }
    }
    Timer { id: deadline; interval: 4000; onTriggered: action.finish(true) }
}
