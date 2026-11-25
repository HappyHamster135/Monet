pragma ComponentBehavior: Bound
import QtQuick
import org.kde.plasma.private.volume as Pulse

Item {
    id: meter
    property var player: null
    property var sources: null
    property var playerRows: []
    property var streams: []
    readonly property int bestMatch: streams.reduce((best, stream) => Math.max(best, stream.rank), 0)
    readonly property real level: streams.reduce((peak, stream) => Math.max(peak, stream.peak), 0)

    function normalized(value) {
        return String(value || "").trim().toLowerCase().replace(/\.desktop$/, "")
    }

    Instantiator {
        model: meter.sources
        delegate: QtObject {
            required property int index
            required property var model
            // The first entry mirrors the currently active player.
            readonly property var player: index > 0 ? model.container : null
        }
        onObjectAdded: (index, row) => meter.playerRows = meter.playerRows.concat([row])
        onObjectRemoved: (index, row) => meter.playerRows = meter.playerRows.filter(other => other !== row)
    }
    Instantiator {
        model: Pulse.SinkInputModel {}
        delegate: QtObject {
            id: stream
            required property var model
            readonly property var info: model.Properties || ({})
            readonly property var client: model.Client?.properties || ({})
            function match(player) {
                const portal = info["pipewire.access.portal.app_id"] || client["pipewire.access.portal.app_id"]
                const pid = Number(client["application.process.id"] || info["application.process.id"])
                // A sandbox can report a PID from its own namespace.
                if (!portal && pid > 0 && (pid === player.kdePid || pid === player.instancePid)) return 3
                const entry = meter.normalized(player.desktopEntry)
                const appId = meter.normalized(portal || info["application.id"] || client["application.id"])
                if (entry && appId) return entry === appId ? 2 : 0
                const name = meter.normalized(info["application.name"] || client["application.name"] || model.Client?.name)
                const binary = meter.normalized(info["application.process.binary"] || client["application.process.binary"])
                return (name && name === meter.normalized(player.identity)) || (entry && entry === binary) ? 1 : 0
            }
            readonly property int rank: {
                const selected = meter.player
                if (!selected || model.VirtualStream || info["media.role"] === "event") return 0
                const score = match(selected)
                if (!score) return 0
                // If another player owns this stream, or both have the same app
                // identity and neither can claim it by PID, leave it unassigned.
                for (const row of meter.playerRows) {
                    if (row.player && row.player !== selected && match(row.player) >= score) return 0
                }
                return score
            }
            readonly property bool listen: rank > 0 && rank === meter.bestMatch && !model.Muted && !model.Corked && model.Volume > 0
            readonly property real peak: listen && taps.object?.available ? Math.max(0, taps.object.volume) : 0
            // Plasma's monitor binds to the owning output when it starts. Moving the
            // playback stream must create a fresh monitor on its new output.
            readonly property Instantiator taps: Instantiator {
                model: stream.listen ? [stream.model.DeviceIndex] : []
                delegate: Pulse.VolumeMonitor { target: stream.model.PulseObject }
            }
        }
        onObjectAdded: (index, stream) => meter.streams = meter.streams.concat([stream])
        onObjectRemoved: (index, stream) => meter.streams = meter.streams.filter(other => other !== stream)
    }
    Row {
        anchors.fill: parent; spacing: 1
        Repeater {
            model: 3
            Rectangle {
                required property int index
                width: 3; radius: 1; color: "#9dd9c9"; anchors.verticalCenter: parent.verticalCenter
                height: Math.max(2, (meter.height - 2) * Math.min(1, meter.level * (1.65 - 0.37 * index)))
            }
        }
    }
}
