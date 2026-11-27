import QtQuick
import org.kde.kirigami as K

// A centered, rounded wave. A real peak controls its envelope when available;
// the quiet fallback only indicates playback, never claims to be a spectrum.
Item {
    id: wave
    property int bars: 9
    property real barWidth: 2.2
    property color tint: "#dedee5"
    property bool playing: true
    property bool motion: K.Units.longDuration > 1
    property bool live: false
    property real level: 0
    property real phase: 0
    readonly property bool moving: playing && visible && motion
    implicitWidth: bars * barWidth + Math.max(0, bars - 1) * barWidth * 0.85
    implicitHeight: 16
    clip: true
    Accessible.ignored: true
    NumberAnimation on phase {
        from: 0; to: Math.PI * 2; duration: 1800; loops: Animation.Infinite
        running: wave.moving && !wave.live
    }
    Row {
        anchors.centerIn: parent; spacing: wave.barWidth * 0.85
        Repeater {
            model: wave.bars
            Rectangle {
                required property int index
                objectName: "notchAudioBar-" + index
                readonly property real envelope: 0.18 + 0.82 * Math.pow(1 - Math.abs(index - (wave.bars - 1) / 2) / Math.max(1, (wave.bars - 1) / 2), 0.85)
                readonly property real amplitude: wave.live ? Math.min(1, Math.max(0, wave.level) * 1.8)
                    : 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(wave.phase + index * 0.9))
                width: wave.barWidth; radius: width / 2; color: wave.tint
                anchors.verticalCenter: parent.verticalCenter
                height: !wave.playing ? width : Math.max(width, wave.height * envelope * (wave.motion ? amplitude : 0.65))
                Behavior on height { enabled: wave.live && wave.motion; NumberAnimation { duration: 75; easing.type: Easing.OutQuad } }
            }
        }
    }
}
