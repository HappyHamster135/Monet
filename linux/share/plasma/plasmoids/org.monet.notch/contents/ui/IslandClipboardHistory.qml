import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.plasma.extras as Extras
import org.kde.plasma.private.clipboard as Clipboard
import org.kde.kitemmodels as Models

Extras.Representation {
    id: page
    objectName: "notchClipboardHistory"
    property bool menuOpen: false
    signal requestHidePopup()
    readonly property bool inDetail: stack.depth > 1
    function back() { if (inDetail) stack.pop() }
    header: null
    focus: true; collapseMarginsHint: true
    required property var historyModel
    function copy(uuid) { page.historyModel.moveToTop(uuid); page.requestHidePopup() }
    Component {
        id: barcodePage
        Clipboard.BarcodePage { expanded: page.visible; stack: stack; barcodeType: "QRCode"; showHeader: false }
    }
    Component {
        id: editorPage
        ColumnLayout {
            id: edit
            required property var target
            required property string entryId
            property string problem: ""
            function save() {
                // History may change while this editor is open. Never edit a replacement row.
                if (!target || target.uuid !== entryId) { problem = i18n("This item is no longer in page.historyModel."); return }
                target.display = editor.text
                page.historyModel.moveToTop(entryId)
                page.back()
            }
            RowLayout {
                Text { Layout.fillWidth: true; text: i18n("Edit clipboard text"); color: "white"; font.pixelSize: 13 }
                IslandButton { caption: true; text: i18n("Cancel"); onClicked: page.back() }
                IslandButton { objectName: "notchClipboardSave"; caption: true; prominent: true; text: i18n("Save"); onClicked: edit.save() }
            }
            IslandNoteEditor { id: editor; editorName: "notchClipboardEditor"; Layout.fillWidth: true; Layout.fillHeight: true; text: edit.target?.display || ""; accessibleName: i18n("Clipboard text") }
            Text { visible: !!edit.problem; Layout.fillWidth: true; text: edit.problem; wrapMode: Text.Wrap; color: "#ffad53"; font.pixelSize: 11 }
            Shortcut { sequences: [StandardKey.Save]; onActivated: edit.save() }
        }
    }
    C.StackView {
        id: stack
        anchors.fill: parent; clip: true
        initialItem: ColumnLayout {
            spacing: 8
            RowLayout {
                IslandTextField {
                    id: search; objectName: "notchClipboardSearch"
                    Layout.fillWidth: true; Layout.minimumWidth: 0
                    placeholderText: i18n("Search clipboard…"); Accessible.name: placeholderText
                    Keys.onDownPressed: { entries.forceActiveFocus(); entries.currentIndex = 0 }
                    onAccepted: if (entries.currentItem) entries.currentItem.copy()
                }
                IslandButton { caption: true; text: i18n("Pinned"); checkable: true; checked: page.historyModel.starredOnly; onClicked: page.historyModel.starredOnly = checked }
            }
            RowLayout {
                visible: !!page.historyModel.sourceModel?.hasPassword
                Text { Layout.fillWidth: true; text: i18n("Sensitive clipboard data isn’t saved in page.historyModel."); font.pixelSize: 11; color: "#ffad53"; wrapMode: Text.Wrap }
                IslandButton { caption: true; text: i18n("Clear"); onClicked: page.historyModel.sourceModel.clearSecret() }
            }
            ListView {
                id: entries; objectName: "notchClipboardEntries"
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true; spacing: 6
                boundsBehavior: Flickable.StopAtBounds
                model: Models.KSortFilterProxyModel {
                    sourceModel: page.historyModel; filterRoleName: "display"
                    // Search text literally, including punctuation and backslashes.
                    filterRegularExpression: new RegExp(search.text.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"), "i")
                }
                C.ScrollBar.vertical: C.ScrollBar {}
                Keys.onReturnPressed: if (currentItem) currentItem.copy()
                Keys.onEnterPressed: if (currentItem) currentItem.copy()
                Keys.onDeletePressed: if (currentItem) page.historyModel.remove(currentItem.model.uuid)
                delegate: C.AbstractButton {
                    id: row
                    objectName: "notchClipboardRow-" + index
                    required property var model
                    required property int index
                    width: entries.width; implicitHeight: 90; padding: 10; hoverEnabled: true
                    function copy() { page.copy(model.uuid) }
                    function edit() { stack.push(editorPage,{target:model,entryId:model.uuid}) }
                    Accessible.name: String(model.display || i18n("Clipboard image"))
                    Accessible.description: i18n("Copy to clipboard")
                    onClicked: copy()
                    background: Rectangle { radius: 12; color: row.hovered || row.visualFocus ? "#27272c" : "#19191d"; border.width: row.visualFocus ? 1 : 0; border.color: "#9999a4" }
                    contentItem: ColumnLayout {
                        spacing: 5
                        RowLayout {
                            IslandGlyph { source: row.model.type === 4 ? "image" : row.model.type === 8 ? "folder" : "text"; color: "#9999a4"; Layout.preferredWidth: 12; Layout.preferredHeight: 12 }
                            Text { Layout.fillWidth: true; text: row.model.type === 4 ? i18n("Image") : row.model.type === 8 ? i18n("Files") : i18n("Text"); color: "#888893"; font.pixelSize: 10 }
                            IslandButton { implicitWidth: 24; implicitHeight: 24; glyphSize: 12; objectName: "notchClipboardPin-" + row.index; plain: true; icon.name: "pin"; checked: !!row.model.starred; text: checked ? i18n("Unpin") : i18n("Pin"); onClicked: row.model.starred = !row.model.starred }
                            IslandButton { implicitWidth: 24; implicitHeight: 24; glyphSize: 12; plain: true; icon.name: "edit-copy"; text: i18n("Copy"); onClicked: row.copy() }
                            IslandButton { id: more; objectName: "notchClipboardMore-" + row.index; implicitWidth: 24; implicitHeight: 24; glyphSize: 12; plain: true; icon.name: "forward"; text: i18n("More actions"); onClicked: actions.open() }
                        }
                        Text { visible: row.model.type !== 4; Layout.fillWidth: true; Layout.fillHeight: true; text: row.model.display || ""; textFormat: Text.PlainText
                            color: "#dedee5"; font.pixelSize: 12; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight }
                        Image { visible: row.model.type === 4; Layout.fillWidth: true; Layout.fillHeight: true; source: visible ? row.model.decoration : ""; sourceSize.height: 100; fillMode: Image.PreserveAspectFit; horizontalAlignment: Image.AlignLeft }
                    }
                    IslandMenu {
                        id: actions
                        objectName: "notchClipboardMenu-" + row.index
                        bounds: page; anchorItem: more
                        onVisibleChanged: page.menuOpen = visible
                        C.MenuItem { text: i18n("Edit text…"); visible: row.model.type === 2; height: visible ? implicitHeight : 0; onTriggered: row.edit() }
                        C.MenuItem { text: i18n("Show QR code"); visible: row.model.type === 2; height: visible ? implicitHeight : 0; onTriggered: stack.push(barcodePage,{text:row.model.display}) }
                        C.MenuItem { text: i18n("Run clipboard action…"); onTriggered: page.historyModel.invokeAction(row.model.uuid) }
                        C.MenuItem { text: i18n("Remove from history"); onTriggered: page.historyModel.remove(row.model.uuid) }
                    }
                }
                IslandEmpty { anchors.fill: parent; visible: !entries.count; symbol: "clipboard"
                    title: search.text ? i18n("No matches") : page.historyModel.starredOnly ? i18n("No pinned items") : i18n("Clipboard is empty")
                    detail: i18n("Copy text, an image, or a file to keep it here.") }
            }
            Text { text: i18n("Click a card to copy · Pin to keep"); color: "#777781"; font.pixelSize: 10 }
            Shortcut { sequences: [StandardKey.Find]; enabled: !page.inDetail; onActivated: { search.forceActiveFocus(); search.selectAll() } }
        }
    }
}
