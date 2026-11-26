import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as C
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: page
    required property var pads
    onEnabledChanged: if (!enabled) padPicker.popup.close()
    RowLayout {
        Layout.fillWidth: true
        C.ComboBox {
            id: padPicker
            objectName: "scratchpadChoice"
            Layout.fillWidth: true
            Layout.minimumWidth: 40
            Accessible.name: i18n("Choose a pad")
            model: page.pads.choices
            textRole: "name"
            currentIndex: page.pads.choices.findIndex(p => p.id === page.pads.ident)
            enabled: page.pads.revision > 0 && !page.pads.switching
            onActivated: index => page.pads.select("select", page.pads.choices[index].id)
        }
        C.ToolButton {
            icon.name: "list-add"
            text: i18n("New pad"); display: C.AbstractButton.IconOnly
            Accessible.name: text
            enabled: page.pads.revision > 0 && !page.pads.switching
            onClicked: page.pads.select("new")
        }
        C.ToolButton {
            icon.name: "window-new"
            text: i18n("Open floating pad"); display: C.AbstractButton.IconOnly
            Accessible.name: text
            enabled: page.pads.revision > 0 && !page.pads.switching
            onClicked: page.pads.select("float")
        }
    }
    C.ScrollView {
        Layout.fillHeight: true; Layout.fillWidth: true
        contentWidth: availableWidth
        C.TextArea {
            id: editor
            objectName: "scratchpadText"
            Accessible.name: i18n("Pad text")
            placeholderText: i18n("Write a note…")
            readOnly: !page.pads.revision || page.pads.switching
            wrapMode: TextEdit.Wrap
            textFormat: TextEdit.PlainText
            onTextChanged: if (activeFocus && !readOnly) page.pads.edit(text)
            Component.onCompleted: text = page.pads.draft
            Connections {
                target: page.pads
                function onDraftChanged() { if (editor.text !== page.pads.draft) editor.text = page.pads.draft }
            }
            Keys.onPressed: event => {
                if (event.matches(StandardKey.Save)) { page.pads.flush(); event.accepted = true }
            }
        }
    }
    RowLayout {
        visible: !!page.pads.problem
        Layout.fillWidth: true
        C.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: page.pads.problem }
        C.Button { text: i18n("Try again"); onClicked: page.pads.refresh() }
    }
}
