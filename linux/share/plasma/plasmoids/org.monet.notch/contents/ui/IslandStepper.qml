pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as C

C.SpinBox {
    id: spin
    from: 1; to: 1440; editable: true
    implicitWidth: 106; implicitHeight: 30
    leftPadding: 30; rightPadding: 30; topPadding: 0; bottomPadding: 0
    background: Rectangle { radius: 9; color: "#202023"; border.width: spin.activeFocus ? 1 : 0; border.color: "#ffad53" }
    contentItem: TextInput {
        text: spin.displayText; font.pixelSize: 13; color: "#ffb669"; selectByMouse: true
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        validator: spin.validator; readOnly: !spin.editable; inputMethodHints: Qt.ImhDigitsOnly
    }
    component Mark: Text {
        width: 30; height: spin.height
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        color: enabled ? "#eeeeef" : "#727278"; font.pixelSize: 18
    }
    up.indicator: Mark { x: spin.mirrored ? 0 : spin.width - width; text: "+" }
    down.indicator: Mark { x: spin.mirrored ? spin.width - width : 0; text: "−" }
}
