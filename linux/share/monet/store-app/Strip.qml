/*
 * A strip of Monet's painting with a placard pinned to its lower edge, as in a gallery: the
 * name of a room of the Store (`title`), a line about it, and a small word above (`kicker`).
 */
import QtQuick
import QtQuick.Effects
import QtQuick.Layouts

Item {
    id: strip
    property string picture: ""
    property string kicker: ""
    property string title: ""
    property string subtitle: ""
    property var tone
    // How tall the painting is; the placard hangs below it by `overhang`.
    // Museum details are selected at 3:1. Show each complete crop at every width.
    property real paintingHeight: Math.round(width / 3)
    readonly property real overhang: Math.round(placard.height * 0.45)
    implicitHeight: paintingHeight + overhang

    Rectangle {
        id: painting
        width: parent.width
        height: strip.paintingHeight
        radius: 16
        clip: true
        color: strip.tone.wash2
        Image {
            id: artwork
            anchors.fill: parent
            source: strip.picture
            fillMode: Image.PreserveAspectFit
            sourceSize.width: 2172
            asynchronous: true
            layer.enabled: true
            layer.effect: MultiEffect {
                maskEnabled: true
                maskSource: paintingMask
                maskThresholdMin: 0.5
                maskSpreadAtMin: 1.0
            }
            opacity: status === Image.Ready ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Math.round(300 * strip.tone.speed) } }
        }
    }

    Rectangle {
        id: paintingMask
        width: painting.width
        height: painting.height
        radius: painting.radius
        color: "white"
        visible: false
        layer.enabled: true
    }

    Rectangle {
        id: card
        anchors.fill: placard
        radius: 10
        color: strip.tone.paper
        visible: false
    }
    MultiEffect {
        source: card
        anchors.fill: card
        shadowEnabled: true
        shadowColor: "#000000"
        shadowOpacity: strip.tone.dark ? 0.45 : 0.16
        shadowBlur: 0.7
        shadowVerticalOffset: 4
    }
    // The placard: Fraunces for the name, as on Monet's desktop.
    Rectangle {
        id: placard
        x: 24
        y: strip.paintingHeight - Math.round(height * 0.55)
        width: Math.min(column.implicitWidth + 40, strip.width - 48)
        height: column.implicitHeight + 26
        radius: 10
        color: strip.tone.paper
        border.width: 1
        border.color: strip.tone.line
        ColumnLayout {
            id: column
            x: 20
            y: 13
            width: placard.width - 40
            spacing: 2
            Text {
                horizontalAlignment: Text.AlignLeft
                visible: strip.kicker !== ""
                text: strip.kicker
                color: strip.tone.lily
                font.pixelSize: 11
                font.weight: Font.DemiBold
                font.letterSpacing: 0.8
                font.capitalization: Font.AllUppercase
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                text: strip.title
                color: strip.tone.ink
                elide: Text.ElideRight
                font.family: "Fraunces 72pt SuperSoft"
                font.weight: Font.Light
                font.pixelSize: 26
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                Layout.maximumWidth: 560
                visible: strip.subtitle !== ""
                text: strip.subtitle
                color: strip.tone.dim
                font.pixelSize: 13
                wrapMode: Text.Wrap
            }
        }
    }
}
