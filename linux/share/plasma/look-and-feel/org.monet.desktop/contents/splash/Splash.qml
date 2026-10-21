/*
 * Monet's start: the dawn painting comes out of the dark, the sun rises
 * from its reflection, and the reflection ripples until the desktop is ready.
 */
import QtQuick

Rectangle {
    id: root
    color: "#0B0E18"
    property int stage

    readonly property color sun: "#F2552C"

    onStageChanged: {
        if (stage === 2) {
            intro.start()
        } else if (stage === 5) {
            outro.start()
        }
    }

    Image {
        id: painting
        anchors.fill: parent
        source: "images/background.jpg"
        fillMode: Image.PreserveAspectCrop
        opacity: 0
    }

    // Dusk over the painting, lifting as the sun comes up.
    Rectangle {
        id: shade
        anchors.fill: parent
        color: "#0B0E18"
        opacity: 0.7
    }

    Item {
        id: mark
        width: 128
        height: 128
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -24

        // The sun, rising out of the water.
        Rectangle {
            id: disc
            width: 54
            height: 54
            radius: 27
            x: 37
            y: 48
            opacity: 0
            gradient: Gradient {
                GradientStop { position: 0; color: "#FF8456" }
                GradientStop { position: 1; color: "#E8431F" }
            }
        }

        Dab { id: dab1; breathing: root.stage >= 2; x: 26; y: 80; width: 76; height: 10; delay: 0 }
        Dab { id: dab2; breathing: root.stage >= 2; x: 35; y: 95; width: 54; height: 8; delay: 180 }
        Dab { id: dab3; breathing: root.stage >= 2; x: 51; y: 108; width: 30; height: 6.5; delay: 360 }
    }

    // One brushstroke of the sun's reflection, breathing once it's visible.
    component Dab: Rectangle {
        property int delay
        property bool breathing
        radius: height / 2
        color: "#F2552C"
        opacity: 0
        SequentialAnimation on scale {
            loops: Animation.Infinite
            running: breathing
            PauseAnimation { duration: delay }
            NumberAnimation { to: 1.16; duration: 800; easing.type: Easing.InOutSine }
            NumberAnimation { to: 1; duration: 800; easing.type: Easing.InOutSine }
        }
    }


    Text {
        id: word
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: mark.bottom
        anchors.topMargin: 28
        text: "Monet"
        color: "#FFFFFF"
        opacity: 0
        font.family: "Fraunces 72pt SuperSoft"
        font.weight: Font.Light
        font.pixelSize: 40
        font.letterSpacing: -0.5
    }

    ParallelAnimation {
        id: intro
        NumberAnimation { target: painting; property: "opacity"; to: 1; duration: 1100; easing.type: Easing.OutCubic }
        NumberAnimation { target: shade; property: "opacity"; to: 0.32; duration: 1600; easing.type: Easing.InOutCubic }
        SequentialAnimation {
            PauseAnimation { duration: 250 }
            ParallelAnimation {
                NumberAnimation { target: disc; property: "opacity"; to: 1; duration: 500 }
                NumberAnimation { target: disc; property: "y"; to: 17; duration: 1300; easing.type: Easing.OutCubic }
            }
        }
        SequentialAnimation {
            PauseAnimation { duration: 700 }
            NumberAnimation { target: dab1; property: "opacity"; to: 0.9; duration: 500; easing.type: Easing.OutCubic }
        }
        SequentialAnimation {
            PauseAnimation { duration: 820 }
            NumberAnimation { target: dab2; property: "opacity"; to: 0.66; duration: 500; easing.type: Easing.OutCubic }
        }
        SequentialAnimation {
            PauseAnimation { duration: 940 }
            NumberAnimation { target: dab3; property: "opacity"; to: 0.42; duration: 500; easing.type: Easing.OutCubic }
        }
        SequentialAnimation {
            PauseAnimation { duration: 900 }
            NumberAnimation { target: word; property: "opacity"; to: 0.95; duration: 700; easing.type: Easing.OutCubic }
        }
    }

    NumberAnimation {
        id: outro
        target: root
        property: "opacity"
        to: 0
        duration: 400
        easing.type: Easing.InCubic
    }
}
