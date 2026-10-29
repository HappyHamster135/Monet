/*
 * The sun sets: the whole screen fades to night while the PC restarts in Windows.
 */
import QtQuick
import QtQuick.Window

Window {
    id: sunset
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    color: "transparent"
    visible: false
    property string game: ""
    property real speed: 1

    function begin(name) {
        game = name
        night.opacity = 0
        disc.y = 17
        showFullScreen()
        fall.restart()
        // If the PC is still here after a while, something is holding it up.
        giveUp.restart()
    }

    Timer {
        id: giveUp
        interval: 45000
        onTriggered: sunset.close()
    }

    Rectangle {
        id: night
        anchors.fill: parent
        color: "#05070E"
        opacity: 0

        Item {
            id: mark
            width: 128
            height: 128
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -40

            Rectangle {
                id: disc
                x: 37
                y: 17
                width: 54
                height: 54
                radius: 27
                gradient: Gradient {
                    GradientStop { position: 0; color: "#FF8456" }
                    GradientStop { position: 1; color: "#E8431F" }
                }
            }
            Repeater {
                model: [[26, 80, 76, 10, 0.9], [35, 95, 54, 8, 0.66], [51, 108, 30, 6.5, 0.42]]
                Rectangle {
                    required property var modelData
                    required property int index
                    x: modelData[0]
                    y: modelData[1]
                    width: modelData[2]
                    height: modelData[3]
                    radius: height / 2
                    color: "#F2552C"
                    opacity: modelData[4]
                    SequentialAnimation on scale {
                        loops: Animation.Infinite
                        running: sunset.visible
                        PauseAnimation { duration: index * 180 }
                        NumberAnimation { to: 1.16; duration: 800; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 1; duration: 800; easing.type: Easing.InOutSine }
                    }
                }
            }
        }

        Column {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: mark.bottom
            anchors.topMargin: 30
            spacing: 10
            Text {
                horizontalAlignment: Text.AlignLeft
                anchors.horizontalCenter: parent.horizontalCenter
                color: "#FFFFFF"
                font.family: "Fraunces 72pt SuperSoft"
                font.weight: Font.Light
                font.pixelSize: 34
                text: sunset.game !== "" ? i18n("Opening %1", sunset.game) : i18n("Opening Windows")
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                anchors.horizontalCenter: parent.horizontalCenter
                color: "#A8FFFFFF"
                font.pixelSize: 15
                text: i18n("Restarting in Windows")
            }
        }

        TapHandler { onTapped: sunset.close() }
    }

    ParallelAnimation {
        id: fall
        NumberAnimation { target: night; property: "opacity"; to: 1; duration: Math.round(900 * sunset.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.4, 0, 0.2, 1, 1, 1] }
        NumberAnimation { target: disc; property: "y"; to: 40; duration: Math.round(1800 * sunset.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.4, 0, 0.2, 1, 1, 1] }
    }
}
