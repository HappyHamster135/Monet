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
    function toggle(url) {
        selected = selected.includes(url) ? selected.filter(other => other !== url) : [...selected, url]
    }
    Connections {
        target: page.shelf
        function onRowsChanged() {
            const urls = new Set(page.shelf.rows.map(row => row.url))
            page.selected = page.selected.filter(url => urls.has(url))
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
                    highlighted: page.selected.includes(modelData.url)
                    Accessible.name: modelData.path
                    Accessible.checkable: true; Accessible.checked: highlighted
                    onClicked: page.toggle(modelData.url)
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
                                Layout.fillWidth: true; text: file.modelData.path
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
                    Drag.mimeData: ({"text/uri-list": (highlighted ? page.selected : [modelData.url]).join("\r\n")})
                    DragHandler {
                        id: handle
                        target: null
                        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad | PointerDevice.Stylus
                        onActiveChanged: {
                            if (!active) { file.Drag.active = false; return }
                            file.contentItem.grabToImage(result => {
                                if (!handle.active) return
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
            text: page.shelf.pending ? i18n("Loading…") : i18n("Drop files or folders here.")
        }
        Rectangle {
            anchors.fill: parent; radius: 6; color: "transparent"
            visible: incoming.containsDrag; border.width: 2; border.color: Kirigami.Theme.highlightColor
        }
        DropArea {
            id: incoming
            anchors.fill: parent
            onEntered: drag => { drag.accepted = page.shelf.accepts(drag) }
            onDropped: drop => {
                if (!page.shelf.accepts(drop)) return
                page.shelf.change("add", Array.from(drop.urls))
                drop.accept(Qt.CopyAction)
            }
        }
    }
    C.Label {
        Layout.fillWidth: true; wrapMode: Text.Wrap
        visible: text.length > 0
        text: page.shelf.message || (page.shelf.rows.length && !page.selected.length
            ? i18n("Drag a file out, or select several to drag together.") : "")
    }
    RowLayout {
        visible: page.selected.length > 0 || !!page.shelf.message
        C.Button {
            visible: page.selected.length > 0
            text: i18n("Remove from shelf"); icon.name: "list-remove"
            onClicked: page.shelf.change("remove", page.selected)
        }
        C.Button {
            visible: !!page.shelf.message
            text: i18n("Refresh"); onClicked: { page.shelf.message = ""; page.shelf.refresh() }
        }
    }
}
