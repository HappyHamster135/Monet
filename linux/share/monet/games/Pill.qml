/*
 * Every button but Play: a pebble of the glass, as Settings' are; "lily" for the one that
 * matters most in a note. A MouseArea rather than a TapHandler, so a pill on a cover never
 * also opens the cover's game.
 */
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Rectangle {
    id: pill
    property alias text: label.text
    property string iconName: ""
    // A drawn mark instead of an icon (a Glyph's path).
    property string glyph: ""
    property bool glyphFilled: false
    property string kind: "plain"
    property var tone
    signal clicked()
    readonly property bool lit: mouse.containsMouse
    implicitWidth: row.implicitWidth + (label.text === "" ? 18 : 28)
    implicitHeight: 34
    radius: 12
    opacity: enabled ? 1 : 0.5
    color: kind === "lily" ? (lit ? "#3F9483" : "#357F72")
        : tone.dark ? Qt.rgba(1, 1, 1, lit ? 0.16 : 0.1)
        : Qt.rgba(0.11, 0.106, 0.098, lit ? 0.11 : 0.07)
    scale: mouse.pressed ? 0.96 : 1
    border.width: activeFocus ? 2 : 0
    border.color: kind === "lily" ? "#FFFFFF" : tone.lily
    activeFocusOnTab: true
    Keys.onReturnPressed: if (enabled) pill.clicked()
    Keys.onEnterPressed: if (enabled) pill.clicked()
    Keys.onSpacePressed: if (enabled) pill.clicked()
    Behavior on scale {
        NumberAnimation { duration: Math.round(160 * pill.tone.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] }
    }
    Behavior on color { ColorAnimation { duration: Math.round(140 * pill.tone.speed) } }

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: 7
        Kirigami.Icon {
            visible: pill.iconName !== ""
            source: pill.iconName
            Layout.preferredWidth: 16
            Layout.preferredHeight: 16
        }
        Glyph {
            visible: pill.glyph !== ""
            path: pill.glyph
            filled: pill.glyphFilled
            color: pill.kind === "lily" ? "#FFFFFF" : pill.tone.ink
            stroke: 2
            Layout.preferredWidth: 15
            Layout.preferredHeight: 15
        }
        Text {
            id: label
            visible: text !== ""
            horizontalAlignment: Text.AlignLeft
            color: pill.kind === "lily" ? "#FFFFFF" : pill.tone.ink
            font.pixelSize: 13
            font.weight: Font.DemiBold
        }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        enabled: pill.enabled
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: pill.clicked()
    }
    Accessible.role: Accessible.Button
    Accessible.name: label.text
    Accessible.onPressAction: if (enabled) pill.clicked()
}
