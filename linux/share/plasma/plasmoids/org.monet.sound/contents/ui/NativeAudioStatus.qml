/* Optional native reader. Keep this import behind AudioLevel's Loader so an
 * older host can still use the wpctl fallback without losing its Sound widget. */
import QtQuick
import org.kde.plasma.private.volume 0.1 as Audio

QtObject {
    readonly property bool ready: Audio.Context.state === Audio.Context.Ready
    readonly property var sink: Audio.PreferredDevice.sink
    readonly property bool hasOutput: ready && !!sink && sink.name !== "auto_null"
    readonly property var volume: hasOutput && Number.isFinite(sink.volume)
        ? Math.round(sink.volume / Audio.PulseAudio.NormalVolume * 100) : null
    readonly property bool muted: hasOutput && sink.muted
    readonly property string description: hasOutput ? (sink.description || sink.name) : ""
}
