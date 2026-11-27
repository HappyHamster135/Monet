import QtQuick
import QtQuick.Controls as C

C.ScrollView {
    id: scroll
    property alias editor: input
    property alias text: input.text
    property alias readOnly: input.readOnly
    property alias placeholderText: input.placeholderText
    property string accessibleName: ""
    property string editorName: ""
    implicitWidth: 240; implicitHeight: 150
    // The document is tall; the viewport must never inherit that height.
    contentWidth: availableWidth
    clip: true
    C.ScrollBar.horizontal.policy: C.ScrollBar.AlwaysOff
    C.TextArea {
        id: input
        objectName: scroll.editorName
        Accessible.name: scroll.accessibleName
        width: scroll.availableWidth
        padding: 12; rightPadding: 18
        wrapMode: TextEdit.Wrap
        textFormat: TextEdit.PlainText
        persistentSelection: true
        color: "#ededf2"; placeholderTextColor: "#858590"
        selectionColor: "#527ba6"; selectedTextColor: "white"
        font.pixelSize: 13
        background: null
    }
    background: Rectangle {
        radius: 12; color: "#17171b"
        border.width: 1; border.color: input.activeFocus ? "#526073" : "#1affffff"
    }
}
