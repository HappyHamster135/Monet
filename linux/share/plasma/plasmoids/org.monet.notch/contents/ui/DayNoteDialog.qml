import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts

C.Dialog {
    id: dialog
    property date day: new Date()
    property alias text: note.text
    signal saved(date day, string text)
    popupType: C.Popup.Item
    anchors.centerIn: parent
    width: Math.max(0, Math.min(420, parent.width - 26))
    height: Math.max(0, Math.min(286, parent.height - 18))
    padding: 12
    modal: true
    closePolicy: C.Popup.CloseOnEscape
    onOpened: { note.editor.forceActiveFocus(); note.editor.cursorPosition = note.editor.length }
    background: Rectangle { radius: 16; color: "#19191d"; border.width: 1; border.color: "#32ffffff" }
    header: Text {
        text: Qt.formatDate(dialog.day, Qt.locale().dateFormat(Locale.LongFormat))
        color: "#f5f5f7"; font.pixelSize: 13; font.weight: Font.DemiBold
        padding: 14; bottomPadding: 0; elide: Text.ElideRight
    }
    contentItem: IslandNoteEditor {
        id: note; objectName: "dayNoteViewport"
        editorName: "dayNoteText"; accessibleName: i18n("Day note")
        placeholderText: i18n("Day note")
    }
    footer: RowLayout {
        spacing: 8
        Item { Layout.fillWidth: true }
        IslandButton { caption: true; text: i18n("Cancel"); Layout.bottomMargin: 12; onClicked: dialog.reject() }
        IslandButton { caption: true; prominent: true; text: i18n("Save"); Layout.bottomMargin: 12; Layout.rightMargin: 12
            onClicked: dialog.accept() }
    }
    onAccepted: saved(day, text)
}
