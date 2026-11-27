import QtQuick
import org.kde.kirigami as K

FocusScope {
    id: grip
    required property Item referenceItem
    property bool mirrored: false
    property string description: qsTr("Resize")
    readonly property bool dragging: pointer.pressed
    signal started()
    signal dragged(real dx, real dy)
    signal finished()
    signal canceled()
    signal nudged(int dx, int dy)
    width: 28; height: 28; z: 5
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: description
    Accessible.description: qsTr("Drag to resize. Arrow keys adjust the size; hold Shift for larger steps. Escape cancels a drag.")
    Rectangle {
        anchors.fill: parent; radius: width / 2
        color: grip.dragging || pointer.containsMouse ? K.Theme.highlightColor : K.Theme.backgroundColor
        border.color: K.Theme.highlightColor; border.width: grip.activeFocus ? 3 : 1.5
        Canvas {
            anchors.centerIn: parent; width: 18; height: 18
            rotation: grip.mirrored ? 90 : 0
            property color ink: grip.dragging || pointer.containsMouse ? K.Theme.highlightedTextColor : K.Theme.textColor
            onInkChanged: requestPaint()
            onPaint: {
                const ctx = getContext("2d")
                ctx.clearRect(0,0,width,height); ctx.strokeStyle = ink; ctx.lineWidth = 1.6; ctx.lineCap = "round"; ctx.lineJoin = "round"
                ctx.beginPath(); ctx.moveTo(4,4); ctx.lineTo(14,14)
                ctx.moveTo(4,9); ctx.lineTo(4,4); ctx.lineTo(9,4)
                ctx.moveTo(9,14); ctx.lineTo(14,14); ctx.lineTo(14,9); ctx.stroke()
            }
        }
    }
    MouseArea {
        id: pointer
        anchors.fill: parent; hoverEnabled: true; preventStealing: true
        cursorShape: grip.mirrored ? Qt.SizeBDiagCursor : Qt.SizeFDiagCursor
        property point origin
        property bool aborted: false
        onPressed: mouse => {
            grip.forceActiveFocus(Qt.MouseFocusReason)
            origin = mapToGlobal(mouse.x, mouse.y)
            aborted = false; grip.started()
        }
        onPositionChanged: mouse => {
            if (!pressed || aborted) return
            const point = mapToGlobal(mouse.x, mouse.y)
            grip.dragged(point.x-origin.x, point.y-origin.y)
        }
        onReleased: if (!aborted) grip.finished()
        onCanceled: { aborted = true; grip.canceled() }
    }
    Keys.onPressed: event => {
        if (event.key === Qt.Key_Escape && pointer.pressed) {
            pointer.aborted = true; grip.canceled(); event.accepted = true; return
        }
        const step = event.modifiers & Qt.ShiftModifier ? 10 : 2
        const dx = event.key === Qt.Key_Right ? step : event.key === Qt.Key_Left ? -step : 0
        const dy = event.key === Qt.Key_Down ? step : event.key === Qt.Key_Up ? -step : 0
        if (dx || dy) { grip.nudged(dx,dy); event.accepted = true }
    }
}
