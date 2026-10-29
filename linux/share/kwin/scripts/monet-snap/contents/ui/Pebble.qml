/*
 * Monet's glass for the snap bar and the picker: a little more solid than the bar's, as it sits
 * over whatever is open, with light along its rim and a hairline outside.
 */
import QtQuick

Rectangle {
    property bool smoke: false

    radius: Math.min(height / 2, 22)
    color: smoke ? Qt.rgba(0.14, 0.137, 0.13, 0.92) : Qt.rgba(0.97, 0.96, 0.945, 0.92)
    border.width: 1
    border.color: smoke ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(1, 1, 1, 0.9)
    Rectangle {
        anchors.fill: parent
        anchors.margins: -1
        z: -1
        radius: parent.radius + 1
        color: "transparent"
        border.width: 1
        border.color: Qt.rgba(0, 0, 0, parent.smoke ? 0.4 : 0.10)
    }
}
