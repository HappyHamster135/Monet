/*
 * The snap layouts as small screens with their parts, for the bar a dragged window comes up to
 * and for Windows+Z. A lit part is lily; a tap on one chooses it (the keyboard's picker only:
 * KWin keeps the pointer while a window is dragged).
 */
import QtQuick

Row {
    id: row

    property var layouts: []
    property bool smoke: false
    property color lily: "#357F72"
    property real speed: 1
    property int litLayout: -1
    property int litZone: -1
    // Windows+Z's numbers: -2 none (the bar), -1 each layout's, or that layout's parts'.
    property int numbered: -2
    // Each part's item, layout and place in it, for finding the one under a point.
    property var parts: []
    signal chosen(int layout, int zone)

    spacing: 12

    function partAt(item, x, y) {
        for (const part of parts) {
            if (!part.item || part.item.width <= 0) {
                continue
            }
            const at = part.item.mapToItem(item, 0, 0)
            if (x >= at.x - 2 && x <= at.x + part.item.width + 2 && y >= at.y - 2 && y <= at.y + part.item.height + 2) {
                return part
            }
        }
        return null
    }

    Repeater {
        model: row.layouts.length
        // One layout: a small screen with its parts.
        Rectangle {
            id: screenPicture
            required property int index
            readonly property int layoutIndex: index
            width: 76
            height: 48
            radius: 9
            color: row.smoke ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(0, 0, 0, 0.04)
            border.width: 1
            border.color: row.smoke ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(0, 0, 0, 0.08)
            Repeater {
                model: row.layouts[screenPicture.layoutIndex].length
                Rectangle {
                    id: partPicture
                    required property int index
                    readonly property var share: row.layouts[screenPicture.layoutIndex][index]
                    readonly property bool lit: row.litLayout === screenPicture.layoutIndex && row.litZone === index
                    x: 4 + share[0] * 68 + (share[0] > 0.001 ? 1.5 : 0)
                    y: 4 + share[1] * 40 + (share[1] > 0.001 ? 1.5 : 0)
                    width: share[2] * 68 - (share[0] > 0.001 ? 1.5 : 0) - (share[0] + share[2] < 0.999 ? 1.5 : 0)
                    height: share[3] * 40 - (share[1] > 0.001 ? 1.5 : 0) - (share[1] + share[3] < 0.999 ? 1.5 : 0)
                    radius: 5
                    color: lit ? row.lily : row.smoke ? Qt.rgba(1, 1, 1, 0.22) : Qt.rgba(0, 0, 0, 0.13)
                    scale: lit ? 1.04 : 1
                    Behavior on color { ColorAnimation { duration: Math.round(140 * row.speed) } }
                    Behavior on scale { NumberAnimation { duration: Math.round(160 * row.speed); easing.type: Easing.OutBack } }
                    Component.onCompleted: row.parts.push({ item: partPicture, layout: screenPicture.layoutIndex, zone: index })
                    Component.onDestruction: row.parts = row.parts.filter(p => p.item !== partPicture)
                    TapHandler {
                        onTapped: row.chosen(screenPicture.layoutIndex, partPicture.index)
                    }
                    Text {
                        anchors.centerIn: parent
                        visible: row.numbered === screenPicture.layoutIndex
                        text: partPicture.index + 1
                        color: partPicture.lit ? "#FFFFFF" : row.smoke ? "#EFECE6" : "#1C1B19"
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                    }
                }
            }
            // Its number, under it, in Windows+Z (lily once it's the one picked).
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.bottom
                anchors.topMargin: 4
                visible: row.numbered >= -1
                text: screenPicture.layoutIndex + 1
                color: row.numbered === screenPicture.layoutIndex ? row.lily
                     : row.smoke ? Qt.rgba(0.94, 0.93, 0.9, 0.7) : Qt.rgba(0.11, 0.106, 0.098, 0.6)
                font.pixelSize: 11
                font.weight: Font.DemiBold
            }
        }
    }
}
