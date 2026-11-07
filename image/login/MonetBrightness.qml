// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Window
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.brightnesscontrolplugin

Item {
    id: root
    width: 48; height: 48
    visible: screen.isBrightnessAvailable
    ScreenBrightnessControl { id: screen; isSilent: true }
    function keyPressed(key) {
        if (key === Qt.Key_Escape && popup.opened) { popup.close(); return true }
        if (!screen.isBrightnessAvailable) return false
        if (key === Qt.Key_MonBrightnessUp || key === Qt.Key_MonBrightnessDown) {
            screen.adjustBrightnessStep(key === Qt.Key_MonBrightnessUp
                ? ScreenBrightnessControl.Increase : ScreenBrightnessControl.Decrease)
            return true
        }
        return false
    }
    function handleKey(event) {
        if (keyPressed(event.key)) event.accepted = true
    }
    QQC2.AbstractButton {
        id: button
        objectName: "monetLoginBrightness"
        anchors.fill: parent
        activeFocusOnTab: true
        Accessible.name: i18nd("monet", "Brightness")
        onClicked: popup.open()
        background: Rectangle {
            radius: 14
            color: button.down ? "#357F72" : button.hovered ? "#45433D" : "#322F2B"
            border.width: button.visualFocus ? 2 : 1
            border.color: button.visualFocus ? "#73C7B3" : "#55B4AEA5"
        }
        contentItem: Kirigami.Icon {
            source: "video-display-brightness"
            isMask: true; color: "#EFECE6"
            implicitWidth: 24; implicitHeight: 24
        }
    }
    QQC2.Popup {
        id: popup
        objectName: "monetLoginBrightnessPopup"
        parent: root
        x: root.width - width
        y: root.height + 8
        width: Math.min(320, root.Window.window ? root.Window.window.width - 32 : 320)
        padding: 18
        focus: true
        closePolicy: QQC2.Popup.CloseOnEscape | QQC2.Popup.CloseOnPressOutside
        background: Rectangle { color: "#292824"; radius: 18; border.color: "#555149" }
        contentItem: ColumnLayout {
            spacing: 14
            Repeater {
                model: screen.displays
                ColumnLayout {
                    required property string displayName
                    required property string label
                    required property int brightness
                    required property int maxBrightness
                    Layout.fillWidth: true
                    QQC2.Label { text: label; color: "#EFECE6"; wrapMode: Text.Wrap; Layout.fillWidth: true }
                    QQC2.Slider {
                        objectName: "monetLoginBrightnessSlider"
                        Layout.fillWidth: true
                        from: Math.max(1, maxBrightness / 100); to: Math.max(from, maxBrightness)
                        value: brightness; stepSize: Math.max(1, maxBrightness / 100)
                        Accessible.name: label + " · " + i18nd("monet", "Brightness")
                        onMoved: screen.setBrightness(displayName, Math.round(value))
                        palette.highlight: "#73C7B3"
                        Component.onCompleted: forceActiveFocus(Qt.TabFocusReason)
                    }
                }
            }
        }
    }
}
