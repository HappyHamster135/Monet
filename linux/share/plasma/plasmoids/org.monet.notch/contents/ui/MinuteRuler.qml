import QtQuick

// The current minute stays under the amber mark as the scale moves beneath it.
Item {
    id: ruler
    required property int minutes
    signal chosen(int minutes)
    readonly property int pitch: 9
    readonly property int sideTicks: Math.ceil(width / (2 * pitch))
    property real wheelRemainder: 0
    implicitHeight: 54
    clip: true
    function choose(value) { chosen(Math.max(1, Math.min(1440, Math.round(value)))) }

    Repeater {
        model: 2 * ruler.sideTicks + 1
        Item {
            required property int index
            readonly property int step: ruler.minutes + index - ruler.sideTicks
            visible: step >= 1 && step <= 1440
            x: (ruler.width - 1) / 2 + (index - ruler.sideTicks) * ruler.pitch
            y: 8; width: 1; height: 39
            Rectangle {
                anchors.bottom: parent.bottom; width: 1
                height: parent.step % 5 === 0 ? 17 : 8
                color: parent.step === ruler.minutes ? "transparent" : "#87878c"
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                visible: parent.step % 5 === 0
                text: parent.step; font.pixelSize: 10; color: "#aca9a6"
            }
        }
    }
    Rectangle { anchors.horizontalCenter: parent.horizontalCenter; y: 26; width: 3; height: 23; radius: 1.5; color: "#ffab52" }
    DragHandler {
        id: drag
        target: null
        yAxis.enabled: false
        property int initial: 0
        onActiveChanged: if (active) initial = ruler.minutes
        onActiveTranslationChanged: if (active) ruler.choose(initial - activeTranslation.x / ruler.pitch)
    }
    TapHandler { onTapped: point => ruler.choose(ruler.minutes + (point.position.x - ruler.width / 2) / ruler.pitch) }
    WheelHandler {
        target: null
        onWheel: event => {
            const delta = event.pixelDelta.y ? event.pixelDelta.y / ruler.pitch : event.angleDelta.y / 120
            if (!delta) { event.accepted = false; return }
            ruler.wheelRemainder += delta
            const steps = Math.trunc(ruler.wheelRemainder)
            if (steps) { ruler.choose(ruler.minutes + steps); ruler.wheelRemainder -= steps }
            event.accepted = true
        }
    }
}
