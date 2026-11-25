import QtQuick
import QtQuick.Controls as C
import org.kde.plasma.plasma5support as P5

C.ToolButton {
    id: button
    required property string command
    required property string generation
    required property string pendingLabel
    required property bool active
    readonly property string requested: active ? generation : ""
    property string inFlight: ""
    property var reading: ({})
    signal preferencesChanged()

    visible: requested.length > 0
    text: reading.summary || pendingLabel
    Accessible.description: reading.details || ""
    C.ToolTip.visible: hovered && !!reading.details
    C.ToolTip.text: reading.details || ""
    contentItem: C.Label { text: button.text; elide: Text.ElideRight; textFormat: Text.PlainText }

    function refresh() {
        if (requested && !inFlight) {
            inFlight = requested
            source.connectSource(command)
        }
    }
    onRequestedChanged: {
        reading = ({})
        Qt.callLater(refresh)
    }
    Timer {
        interval: 60000; repeat: true; running: !!button.requested
        onTriggered: button.refresh()
    }
    P5.DataSource {
        id: source
        engine: "executable"
        connectedSources: []
        onNewData: (name, data) => {
            disconnectSource(name)
            const previous = button.inFlight
            button.inFlight = ""
            if (!button.requested) return
            if (previous !== button.requested) {
                Qt.callLater(button.refresh)
                return
            }
            try {
                const result = JSON.parse(data.stdout)
                if (result.state === "off" || result.generation !== button.requested) button.preferencesChanged()
                else button.reading = result
            } catch (_) { button.reading = ({}) }
        }
    }
}
