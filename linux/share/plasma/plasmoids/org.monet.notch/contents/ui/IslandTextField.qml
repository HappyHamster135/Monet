import QtQuick
import QtQuick.Controls as C

C.TextField {
    id: field
    implicitHeight: 32
    leftPadding: 10; rightPadding: 10
    color: "#f5f5f7"; placeholderTextColor: "#93939f"
    selectionColor: "#527ba6"; selectedTextColor: "white"
    font.pixelSize: 12
    background: Rectangle {
        radius: 10; color: "#202024"
        border.width: 1; border.color: field.activeFocus ? "#a3ccff" : "#24ffffff"
    }
}
