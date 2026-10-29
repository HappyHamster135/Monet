/*
 * An app hung like a painting: its first screenshot in a paper mat, with a shadow under it, the
 * app's picture pinned to the mat's edge, and its name and what it's for underneath, as on a
 * gallery's label. Before the screenshot arrives, a strip of Monet's painting stands in, the
 * app's picture on it. `rank` puts a numeral beside the name; `note` a line under it.
 */
import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import "../games"

Item {
    id: framed
    property var app: ({})
    property var tone
    // A painting to show until the screenshot is there.
    property string painting: ""
    property int rank: 0
    property string note: ""
    signal chosen()

    readonly property bool lit: mouse.containsMouse || activeFocus
    implicitWidth: 300
    implicitHeight: frame.height - 22 + label.implicitHeight + 4

    activeFocusOnTab: true
    Keys.onReturnPressed: framed.chosen()
    Keys.onEnterPressed: framed.chosen()
    Keys.onSpacePressed: framed.chosen()
    Accessible.role: Accessible.Button
    Accessible.name: (app.name || "") + ", " + (app.summary || "")
    Accessible.onPressAction: framed.chosen()

    // The mat and the screenshot in it, lifted a little under the pointer.
    Item {
        id: frame
        width: parent.width
        height: Math.round(width * 0.6)
        scale: framed.lit ? 1.015 : 1
        Behavior on scale { NumberAnimation { duration: Math.round(220 * framed.tone.speed); easing.type: Easing.OutCubic } }

        Rectangle {
            id: mat
            anchors.fill: parent
            radius: 12
            color: framed.tone.dark ? "#34322F" : "#FFFFFF"
            visible: false
        }
        MultiEffect {
            source: mat
            anchors.fill: mat
            shadowEnabled: true
            shadowColor: "#000000"
            shadowOpacity: framed.tone.dark ? 0.5 : (framed.lit ? 0.28 : 0.18)
            shadowBlur: framed.lit ? 0.9 : 0.6
            shadowVerticalOffset: framed.lit ? 10 : 5
            Behavior on shadowOpacity { NumberAnimation { duration: Math.round(220 * framed.tone.speed) } }
        }
        Item {
            anchors.fill: parent
            anchors.margins: 6
            layer.enabled: true
            layer.effect: MultiEffect {
                maskEnabled: true
                maskSource: shape
                maskThresholdMin: 0.5
                maskSpreadAtMin: 1.0
            }
            Image {
                anchors.fill: parent
                visible: shot.status !== Image.Ready
                source: framed.painting
                fillMode: Image.PreserveAspectCrop
                sourceSize.width: 900
                asynchronous: true
            }
            Image {
                anchors.centerIn: parent
                width: Math.round(parent.height * 0.36)
                height: width
                visible: shot.status !== Image.Ready
                source: framed.app.icon || ""
                sourceSize: Qt.size(160, 160)
                fillMode: Image.PreserveAspectFit
                asynchronous: true
            }
            Image {
                id: shot
                anchors.fill: parent
                source: framed.app.shot || ""
                fillMode: Image.PreserveAspectCrop
                verticalAlignment: Image.AlignTop
                sourceSize.width: 720
                asynchronous: true
                opacity: status === Image.Ready ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: Math.round(260 * framed.tone.speed) } }
            }
        }
        Item {
            id: shape
            anchors.fill: parent
            anchors.margins: 6
            visible: false
            layer.enabled: true
            Rectangle { anchors.fill: parent; radius: 8 }
        }
    }

    // The label: the app's picture pinned to the mat's edge, then its name, what it's for, and
    // whether you have it.
    RowLayout {
        id: label
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: frame.bottom
        anchors.topMargin: -22
        spacing: 12
        Rectangle {
            Layout.alignment: Qt.AlignTop
            Layout.leftMargin: 14
            Layout.preferredWidth: 54
            Layout.preferredHeight: 54
            radius: 14
            color: framed.tone.paper
            border.width: 1
            border.color: framed.tone.line
            Image {
                anchors.fill: parent
                anchors.margins: 5
                source: framed.app.icon || ""
                sourceSize: Qt.size(96, 96)
                fillMode: Image.PreserveAspectFit
                asynchronous: true
            }
        }
        Text {
            Layout.alignment: Qt.AlignTop
            Layout.topMargin: 26
            visible: framed.rank > 0
            text: framed.rank.toLocaleString(Qt.locale(), "f", 0)
            color: framed.tone.ochre
            font.family: "Fraunces 72pt SuperSoft"
            font.weight: Font.Light
            font.pixelSize: 30
            font.features: ({ "tnum": 1 })
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.topMargin: 28
            spacing: 2
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: framed.app.name || ""
                    textFormat: Text.PlainText
                    color: framed.tone.ink
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                Glyph {
                    Layout.preferredWidth: 14
                    Layout.preferredHeight: 14
                    visible: framed.app.verified === true
                    path: "M12 3l2.4 1.8 3-.2.9 2.9 2.4 1.8-1 2.8 1 2.8-2.4 1.8-.9 2.9-3-.2L12 21l-2.4-1.8-3 .2-.9-2.9-2.4-1.8 1-2.8-1-2.8 2.4-1.8.9-2.9 3 .2zM8.5 12.2l2.3 2.3 4.7-4.7"
                    color: framed.tone.lily
                    stroke: 1.8
                }
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                text: framed.app.summary || ""
                textFormat: Text.PlainText
                color: framed.tone.dim
                font.pixelSize: 13
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                visible: text !== ""
                text: framed.app.state === "installed" ? i18n("Installed")
                    : framed.app.state === "built-in" ? i18n("Part of Monet")
                    : framed.app.state === "working" ? i18n("Working on it…") : framed.note
                color: framed.app.state === "get" ? framed.tone.dim : framed.tone.lily
                font.pixelSize: 12
                font.weight: Font.DemiBold
            }
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: framed.chosen()
    }
    Rectangle {
        anchors.fill: frame
        anchors.margins: -3
        radius: 14
        color: "transparent"
        visible: framed.activeFocus
        border.width: 2
        border.color: framed.tone.lily
    }
}
