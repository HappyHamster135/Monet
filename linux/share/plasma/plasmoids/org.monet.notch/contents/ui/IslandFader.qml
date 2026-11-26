import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kirigami as K

ColumnLayout {
    id: strip
    required property string title
    required property string symbol
    required property string muteLabel
    required property string levelLabel
    required property int percent
    required property bool muted
    property int maximum: 100
    property bool online: true
    property bool writable: online
    property bool application: false
    property bool marked: false
    property bool hasOptions: application
    readonly property alias nameItem: caption
    signal muteRequested()
    signal levelRequested(int percent)
    signal optionsRequested()
    spacing: 3

    Item {
        Layout.fillWidth: true; Layout.preferredHeight: 32
        C.AbstractButton {
            id: mute
            anchors.centerIn: parent
            width: 35; height: parent.height
            enabled: strip.online
            Accessible.name: strip.muteLabel
            C.ToolTip.visible: hovered; C.ToolTip.text: Accessible.name
            onClicked: strip.muteRequested()
            background: Rectangle {
                radius: 9; color: mute.hovered || mute.visualFocus ? "#303034" : "transparent"
                border.width: mute.visualFocus ? 1 : 0; border.color: "#adcfff"
            }
            contentItem: Item {
                K.Icon {
                    width: 23; height: width; anchors.centerIn: parent
                    source: strip.symbol; fallback: "applications-multimedia"
                    color: strip.muted ? "#929299" : "#f5f5f7"
                    opacity: strip.online && !strip.muted ? 1 : 0.55
                }
                Rectangle {
                    visible: strip.application && strip.online
                    anchors.right: parent.right; anchors.bottom: parent.bottom
                    width: 8; height: width; radius: width / 2
                    color: strip.muted ? "#909096" : "#63d89a"
                    border.color: "#141416"
                }
            }
        }
        K.Icon {
            visible: strip.marked; width: 12; height: width
            anchors.left: parent.left; anchors.leftMargin: 4; anchors.verticalCenter: parent.verticalCenter
            source: "pin-symbolic"; color: "#aaaaaf"; Accessible.name: i18n("Pinned")
        }
        IslandButton {
            id: options
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            width: 22; height: 26
            visible: strip.hasOptions; plain: true; icon.name: "overflow-menu"
            text: i18n("Options for %1",strip.title)
            onClicked: strip.optionsRequested()
        }
    }
    C.Label {
        id: caption
        Layout.fillWidth: true; Layout.preferredHeight: 18
        horizontalAlignment: Text.AlignHCenter
        text: strip.title; textFormat: Text.PlainText; elide: Text.ElideRight
        color: strip.online ? "#eeeeef" : "#99999f"; font.pixelSize: 11; font.weight: Font.DemiBold
        C.ToolTip.text: text; C.ToolTip.visible: labelHover.hovered && truncated
        HoverHandler { id: labelHover }
    }
    C.Slider {
        id: level
        Layout.fillHeight: true; Layout.preferredWidth: 43; Layout.alignment: Qt.AlignHCenter
        leftPadding: 5; rightPadding: 5; topPadding: 3; bottomPadding: 3
        from: 0; to: strip.maximum; stepSize: 1
        value: strip.percent; orientation: Qt.Vertical; enabled: strip.writable
        Accessible.name: strip.levelLabel
        Accessible.description: strip.maximum > 100 ? i18n("100% is normal volume. Higher levels boost this app.") : ""
        onMoved: strip.levelRequested(Math.round(value))
        handle: Item { implicitWidth: 0; implicitHeight: 0 }
        background: Rectangle {
            x: level.leftPadding; y: level.topPadding
            width: level.availableWidth; height: level.availableHeight
            radius: width / 2
            color: level.hovered ? "#3a3a40" : "#2d2d32"
            border.width: level.visualFocus ? 2 : 1
            border.color: level.visualFocus ? "#adcfff" : "#18ffffff"
            Rectangle {
                anchors.bottom: parent.bottom; width: parent.width
                height: Math.round(parent.height * level.position)
                radius: Math.min(width / 2,height / 2)
                color: !strip.online || strip.muted ? "#696970" : level.value > 100 ? "#ffae55" : "#f2f2f4"
            }
            Rectangle {
                visible: strip.maximum > 100
                x: 5; width: parent.width - 10; height: 1
                y: Math.round(parent.height * (1 - 100 / strip.maximum))
                color: level.value >= 100 ? "#865f3c" : "#7d7d85"
            }
        }
    }
    Item {
        Layout.fillWidth: true; Layout.preferredHeight: 26
        C.AbstractButton {
            id: number
            anchors.centerIn: parent; width: strip.application && strip.online ? Math.max(32,parent.width - 44) : parent.width; height: parent.height
            enabled: strip.writable; visible: !editor.visible
            Accessible.name: i18n("Volume percentage for %1",strip.title)
            background: Rectangle { radius: 6; color: number.hovered || number.visualFocus ? "#28282c" : "transparent" }
            contentItem: C.Label {
                text: strip.online ? i18n("%1%",strip.percent) : i18n("Not playing")
                color: strip.percent > 100 && !strip.muted ? "#ffb469" : "#bbbbc1"
                font.pixelSize: 11; font.weight: Font.DemiBold
                horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
            }
            onClicked: { editor.text = String(strip.percent); editor.visible = true; editor.forceActiveFocus(); editor.selectAll() }
        }
        IslandButton {
            anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; width: 21; height: 24
            visible: strip.application && strip.writable && strip.percent !== 100 && !editor.visible
            plain: true; text: i18n("Reset volume to 100%"); icon.name: "edit-undo"
            onClicked: strip.levelRequested(100)
        }
        IslandButton {
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; width: 21; height: 24
            visible: strip.application && strip.online && !editor.visible
            plain: true; text: strip.muteLabel; icon.name: strip.muted ? "audio-volume-muted" : "audio-volume-high"
            onClicked: strip.muteRequested()
        }
        C.TextField {
            id: editor
            width: Math.min(parent.width,55); height: parent.height; anchors.centerIn: parent
            visible: false; padding: 1; horizontalAlignment: TextInput.AlignHCenter
            Accessible.name: number.Accessible.name
            validator: IntValidator { bottom: 0; top: strip.maximum }
            onEditingFinished: {
                if (!visible) return
                visible = false
                if (acceptableInput && strip.writable) strip.levelRequested(Number(text))
            }
            Keys.onEscapePressed: event => { visible = false; number.forceActiveFocus(); event.accepted = true }
        }
    }
}
