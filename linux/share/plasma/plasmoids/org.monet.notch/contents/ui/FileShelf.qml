import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: page
    required property var shelf
    property bool dragging: false
    property bool canGoBack: true
    signal backRequested()
    signal detachRequested()
    property var selected: []
    function toggle(key) {
        selected = selected.includes(key) ? selected.filter(other => other !== key) : [...selected, key]
    }
    function dragData(row) {
        const group = selected.includes(row.key) ? shelf.rows.filter(r => selected.includes(r.key)) : [row]
        const mime = {"text/plain": group.map(r => r.path).join("\n"), "application/x-monet-shelf-drag": "1"}
        if (group.every(r => r.url)) mime["text/uri-list"] = group.map(r => r.url).join("\r\n")
        return mime
    }
    Connections {
        target: page.shelf
        function onRowsChanged() {
            const keys = new Set(page.shelf.rows.map(row => row.key))
            page.selected = page.selected.filter(key => keys.has(key))
        }
    }
    RowLayout {
        Layout.fillWidth: true
        C.ToolButton {
            visible: page.canGoBack; icon.name: "go-previous"; Accessible.name: i18n("Back")
            onClicked: page.backRequested()
        }
        C.Label { text: i18n("File shelf"); font.bold: true; Layout.fillWidth: true }
        C.ToolButton {
            icon.name: "window-new"; Accessible.name: i18n("Open shelf in Utilities")
            C.ToolTip.text: Accessible.name; C.ToolTip.visible: hovered
            onClicked: page.detachRequested()
        }
    }
    Item {
        Layout.fillWidth: true; Layout.fillHeight: true
        C.ScrollView {
            id: scroll
            anchors.fill: parent; clip: true
            contentWidth: availableWidth
            ListView {
                id: list
                model: page.shelf.rows
                delegate: C.ItemDelegate {
                    id: file
                    required property var modelData
                    width: list.width
                    highlighted: page.selected.includes(modelData.key)
                    Accessible.name: modelData.kind === "text" ? modelData.name : modelData.path
                    Accessible.checkable: true; Accessible.checked: highlighted
                    onClicked: page.toggle(modelData.key)
                    contentItem: RowLayout {
                        Kirigami.Icon {
                            Layout.preferredWidth: 22; Layout.preferredHeight: 22
                            source: file.highlighted ? "emblem-checked" : file.modelData.icon || "text-x-generic"
                        }
                        ColumnLayout {
                            Layout.fillWidth: true; spacing: 0
                            C.Label {
                                Layout.fillWidth: true; text: file.modelData.name
                                textFormat: Text.PlainText; elide: Text.ElideMiddle
                            }
                            C.Label {
                                Layout.fillWidth: true; text: file.modelData.kind === "text" ? i18n("Text") : file.modelData.path
                                textFormat: Text.PlainText; elide: Text.ElideLeft
                                color: Kirigami.Theme.disabledTextColor; font: Kirigami.Theme.smallFont
                            }
                        }
                    }
                    Drag.dragType: Drag.Automatic
                    Drag.supportedActions: Qt.CopyAction
                    Drag.onDragStarted: page.dragging = true
                    Drag.onDragFinished: page.dragging = false
                    Drag.proposedAction: Qt.CopyAction

                    DragHandler {
                        id: handle
                        target: null
                        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad | PointerDevice.Stylus
                        onActiveChanged: {
                            if (!active) { file.Drag.active = false; return }
                            file.contentItem.grabToImage(result => {
                                if (!handle.active) return
                                file.Drag.mimeData = page.dragData(file.modelData)
                                file.Drag.imageSource = result.url
                                file.Drag.active = true
                            })
                        }
                    }
                }
            }
        }
        C.Label {
            anchors.centerIn: parent; width: parent.width - 16
            horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
            visible: !list.count
            text: page.shelf.pending ? i18n("Loading…") : i18n("Drop files, folders, links or selected text here.")
        }
        Rectangle {
            anchors.fill: parent; radius: 6; color: "transparent"
            visible: incoming.containsDrag; border.width: 2; border.color: Kirigami.Theme.highlightColor
        }
        DropArea {
            id: incoming
            anchors.fill: parent
            onEntered: drag => { drag.accepted = page.shelf.accepts(drag) }
            onDropped: drop => page.shelf.addDrop(drop)
        }
    }
    C.Label {
        Layout.fillWidth: true; wrapMode: Text.Wrap
        visible: text.length > 0
        text: page.shelf.message || (page.shelf.rows.length && !page.selected.length
            ? i18n("Drag an item out, or select several to drag together.") : "")
    }
    RowLayout {
        visible: page.selected.length > 0 || !!page.shelf.message
        C.Button {
            visible: page.selected.length > 0
            text: i18n("Remove from shelf"); icon.name: "list-remove"
            onClicked: page.shelf.change({action: "remove", keys: page.selected, urls: page.selected.filter(key => key.startsWith("file:///"))})
        }
        C.Button {
            visible: !!page.shelf.message
            text: i18n("Refresh"); onClicked: { page.shelf.message = ""; page.shelf.refresh() }
        }
    }
}
