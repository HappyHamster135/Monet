import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as C

Item {
    id: page
    required property var pads
    readonly property bool ready: pads.revision > 0 && !pads.switching
    readonly property bool canManage: ready && !pads.dirty && !pads.pending
    readonly property bool menuOpen: actions.opened || !!management
    readonly property bool editingEvent: !!management || searching
    readonly property string padName: pads.choices.find(p => p.id === pads.ident)?.name || i18n("Notes")
    property string management: ""
    property bool searching: false
    property bool matchFound: true
    implicitWidth: 240; implicitHeight: 210
    function closeEditor() {
        if (management) management = ""
        else searching = false
        note.editor.forceActiveFocus()
    }
    function focusEditor() {
        if (!enabled || !visible || !ready || management) return
        note.editor.forceActiveFocus()
        note.editor.cursorPosition = note.editor.length
    }
    function copyNote() {
        const start = note.editor.selectionStart, end = note.editor.selectionEnd
        note.editor.selectAll(); note.editor.copy(); note.editor.select(start, end)
    }
    function find(backwards = false, fromStart = false) {
        const query = findField.text
        if (!query) { matchFound = true; return }
        // Match the original text so Unicode case folding cannot shift cursor offsets.
        const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
        const pattern = new RegExp(escaped, "giu"), matches = []
        let result
        while ((result = pattern.exec(note.text)) !== null) matches.push(result)
        const match = fromStart ? matches[0] : backwards
            ? matches.slice().reverse().find(m => m.index < note.editor.selectionStart) || matches[matches.length - 1]
            : matches.find(m => m.index >= note.editor.selectionEnd) || matches[0]
        matchFound = !!match
        if (match) note.editor.select(match.index, match.index + match[0].length)
    }
    onEnabledChanged: if (!enabled) { actions.close(); management = ""; pads.flush() }
    onVisibleChanged: if (!visible) pads.flush()
    ColumnLayout {
        anchors.fill: parent; spacing: 7
        RowLayout {
            Layout.fillWidth: true; spacing: 5
            ListView {
                id: tabs
                objectName: "scratchpadTabs"
                Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredHeight: 30
                orientation: ListView.Horizontal; spacing: 4; clip: true
                boundsBehavior: Flickable.StopAtBounds
                model: page.pads.choices
                currentIndex: page.pads.choices.findIndex(p => p.id === page.pads.ident)
                onCurrentIndexChanged: Qt.callLater(() => positionViewAtIndex(currentIndex, ListView.Contain))
                delegate: IslandButton {
                    required property var modelData
                    objectName: "scratchpadTab-" + modelData.id
                    caption: true; text: modelData.name
                    width: Math.min(150, implicitWidth); height: 28
                    checked: modelData.id === page.pads.ident
                    enabled: page.ready
                    onClicked: page.pads.select("select", modelData.id)
                }
            }
            IslandButton {
                objectName: "scratchpadNew"
                plain: true; icon.name: "list-add"; text: i18n("New pad")
                enabled: page.ready; onClicked: page.pads.select("new")
            }
            IslandButton {
                plain: true; icon.name: "window-new"; text: i18n("Open floating pad")
                enabled: page.ready; onClicked: page.pads.select("float")
            }
            IslandButton {
                id: more
                objectName: "scratchpadActions"
                plain: true; icon.name: "application-menu"; text: i18n("Pad actions")
                enabled: page.ready; onClicked: actions.open()
                IslandMenu {
                    id: actions
                    objectName: "scratchpadMenu"
                    bounds: page; anchorItem: more; preferredWidth: 200
                    delegate: C.MenuItem {}
                    C.MenuItem { text: i18n("Rename pad…"); enabled: page.canManage
                        onTriggered: { nameField.text = page.padName; page.management = "rename"; nameField.forceActiveFocus(); nameField.selectAll() } }
                    C.MenuItem { text: i18n("Copy note"); enabled: note.text.length > 0; onTriggered: page.copyNote() }
                    C.MenuItem { text: i18n("Find in note…"); onTriggered: { page.searching = true; findField.forceActiveFocus(); findField.selectAll() } }
                    C.MenuItem { text: i18n("Clear note"); enabled: note.text.length > 0
                        onTriggered: { note.editor.forceActiveFocus(); note.editor.selectAll(); note.editor.remove(0, note.editor.length) } }
                    C.MenuSeparator {}
                    C.MenuItem { text: i18n("Delete pad…"); enabled: page.canManage
                        onTriggered: { page.management = "delete"; cancel.forceActiveFocus() } }
                }
            }
        }
        RowLayout {
            visible: page.searching
            Layout.fillWidth: true; spacing: 5
            IslandTextField {
                id: findField; objectName: "scratchpadFind"
                Layout.fillWidth: true; Layout.minimumWidth: 0
                placeholderText: i18n("Find in note…"); Accessible.name: placeholderText
                onTextEdited: page.find(false, true)
                onAccepted: page.find()
                Keys.onEscapePressed: { page.searching = false; note.editor.forceActiveFocus() }
            }
            Text { visible: !page.matchFound; text: i18n("No matches"); color: "#b8b8c2"; font.pixelSize: 11 }
            IslandButton { plain: true; icon.name: "go-up"; text: i18n("Previous match"); onClicked: page.find(true) }
            IslandButton { plain: true; icon.name: "go-down"; text: i18n("Next match"); onClicked: page.find() }
            IslandButton { plain: true; icon.name: "window-close"; text: i18n("Close search")
                onClicked: { page.searching = false; note.editor.forceActiveFocus() } }
        }
        IslandNoteEditor {
            id: note
            objectName: "scratchpadViewport"
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 0
            editorName: "scratchpadText"; accessibleName: i18n("Pad text")
            placeholderText: i18n("Write a note…")
            readOnly: !page.ready
            Component.onCompleted: { text = page.pads.draft; Qt.callLater(page.focusEditor) }
            Connections {
                target: note.editor
                function onTextChanged() { if (note.editor.activeFocus && !note.readOnly) page.pads.edit(note.text) }
            }
            Connections {
                target: page.pads
                function onDraftChanged() { if (note.text !== page.pads.draft) note.text = page.pads.draft }
                function onIdentChanged() { Qt.callLater(page.focusEditor) }
            }
            Keys.forwardTo: [note.editor]
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            Text {
                Layout.fillWidth: true; Layout.minimumWidth: 0; font.pixelSize: 11
                text: page.pads.problem || (!page.pads.revision ? i18n("Loading…")
                    : page.pads.dirty || page.pads.pending ? i18n("Saving…") : i18n("Saved"))
                color: page.pads.problem ? "#f1b38e" : "#94949e"
                textFormat: Text.PlainText; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
            }
            IslandButton { visible: !!page.pads.problem; caption: true; text: i18n("Try again"); onClicked: page.pads.refresh() }
        }
    }
    Shortcut { sequences: [StandardKey.Save]; enabled: page.visible && page.enabled && !page.management; onActivated: page.pads.flush() }
    Shortcut { sequences: [StandardKey.Find]; enabled: page.visible && page.enabled && !page.management
        onActivated: { page.searching = true; findField.forceActiveFocus(); findField.selectAll() } }
    Shortcut { sequences: [StandardKey.FindNext]; enabled: page.visible && page.enabled && page.searching && !page.management; onActivated: page.find() }
    Shortcut { sequences: [StandardKey.FindPrevious]; enabled: page.visible && page.enabled && page.searching && !page.management; onActivated: page.find(true) }
    Shortcut { sequence: "Ctrl+T"; enabled: page.visible && page.enabled && page.ready && !page.management; onActivated: page.pads.select("new") }
    FocusScope {
        parent: page
        anchors.fill: parent; visible: !!page.management; z: 2
        Keys.onEscapePressed: page.closeEditor()
        Rectangle { anchors.fill: parent; radius: 14; color: "#17171b"; border.width: 1; border.color: "#2affffff" }
        MouseArea { anchors.fill: parent; onWheel: wheel => wheel.accepted = true }
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 14; spacing: 10
            Text {
                Layout.fillWidth: true; color: "#f5f5f7"; font.pixelSize: 15; font.weight: Font.DemiBold
                text: page.management === "rename" ? i18n("Rename pad") : i18n("Delete pad?")
            }
            Text {
                Layout.fillWidth: true; visible: page.management === "delete"
                text: i18n("Delete “%1” and its text?", page.padName); textFormat: Text.PlainText
                color: "#b8b8c2"; wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight
            }
            IslandTextField {
                id: nameField; objectName: "scratchpadName"
                visible: page.management === "rename"; Layout.fillWidth: true
                Accessible.name: i18n("Pad name"); maximumLength: 100
                onAccepted: if (text.trim() && page.canManage) confirm.clicked()
            }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.alignment: Qt.AlignRight; spacing: 8
                IslandButton { id: cancel; caption: true; text: i18n("Cancel"); onClicked: page.closeEditor() }
                IslandButton {
                    id: confirm; objectName: "scratchpadConfirm"; caption: true; prominent: true
                    text: page.management === "rename" ? i18n("Save name") : i18n("Delete")
                    enabled: page.canManage && (page.management !== "rename" || nameField.text.trim().length > 0)
                    onClicked: { page.pads.manage(page.management, nameField.text.trim()); page.closeEditor() }
                }
            }
        }
    }
}
