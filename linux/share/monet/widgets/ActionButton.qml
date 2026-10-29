/* Painted text actions shared by the bar popups. */
import QtQuick
import QtQuick.Templates as T
import org.kde.kirigami as Kirigami

T.AbstractButton {
    id: control
    implicitWidth: label.implicitWidth + 28
    implicitHeight: Math.max(34, label.implicitHeight + 16)
    activeFocusOnTab: true
    opacity: enabled ? 1 : 0.5
    Accessible.name: text
    Keys.onReturnPressed: if (enabled) clicked()
    Keys.onEnterPressed: if (enabled) clicked()
    contentItem: Text {
        id: label
        text: control.text
        color: Kirigami.Theme.textColor
        font: Kirigami.Theme.defaultFont
        wrapMode: Text.Wrap
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: 12
        color: control.checked ? Qt.rgba(0.208, 0.498, 0.447, 0.22)
            : Qt.rgba(0.5, 0.5, 0.5, control.down ? 0.24 : control.hovered ? 0.18 : 0.09)
        border.width: control.visualFocus ? 2 : 0
        border.color: "#357F72"
    }
}
