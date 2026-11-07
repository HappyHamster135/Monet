/* Native notifications keep the closed panel current without periodic commands.
 * wpctl is used only while the native reader is unavailable or disconnected. */
import QtQuick
import org.kde.plasma.plasma5support as P5Support

Item {
    id: level
    visible: false
    property bool active: true
    property url nativeSource: "NativeAudioStatus.qml"
    property string fallbackCommand: "wpctl get-volume @DEFAULT_AUDIO_SINK@"
    property var volume: null
    property bool muted: false
    readonly property bool nativeReady: native.status === Loader.Ready && !!native.item.ready
    readonly property bool hasOutput: nativeReady && native.item.hasOutput
    readonly property string description: nativeReady ? native.item.description : ""
    property string pending: ""
    property int serial: 0

    function refresh() {
        if (!active) return;
        if (nativeReady) {
            volume = native.item.volume;
            muted = native.item.muted;
        } else if (!pending) {
            // The executable engine may retain the last reply for a command.
            // A fresh source also prevents a fast retry from accepting old data.
            pending = fallbackCommand + " # monet-audio-" + (++serial);
            runner.connectSource(pending);
        }
    }
    onNativeReadyChanged: refresh()
    onActiveChanged: if (active) refresh()
    Loader { id: native; source: level.nativeSource }
    Connections {
        target: native.item
        function onVolumeChanged() { level.refresh(); }
        function onMutedChanged() { level.refresh(); }
    }
    P5Support.DataSource {
        id: runner
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source);
            if (source !== level.pending) return;
            level.pending = "";
            if (level.nativeReady) return;
            const found = (data.stdout || "").match(/Volume:\s*([0-9.]+)/);
            const value = found ? Number(found[1]) * 100 : NaN;
            level.volume = data["exit code"] === 0 && Number.isFinite(value) ? Math.round(value) : null;
            level.muted = level.volume !== null && data.stdout.indexOf("[MUTED]") !== -1;
        }
    }
    Timer {
        interval: 2000
        repeat: true
        running: level.active && !level.nativeReady
        triggeredOnStart: true
        onTriggered: level.refresh()
    }
}
