import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: page
    required property var shelf
    property bool dragging: false
    spacing: 6
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
        C.Label {
            text: page.selected.length ? i18np("%1 selected", "%1 selected", page.selected.length)
                : i18np("%1 item", "%1 items", page.shelf.rows.length)
            color: "#b9d7f9"; font.weight: Font.Medium; Layout.fillWidth: true
        }
        IslandButton { caption: true; text: i18n("Open in Utilities"); onClicked: page.detachRequested() }
    }
    Rectangle {
        Layout.fillWidth: true; Layout.fillHeight: true
        radius: 16; color: incoming.containsDrag ? "#253649" : "#1c2026"
        border.width: 1; border.color: incoming.containsDrag ? "#98caff" : "#303944"
        C.ScrollView {
            id: scroll
            visible: !incoming.containsDrag
            anchors.fill: parent; anchors.margins: 6; clip: true
            contentWidth: availableWidth
            ListView {
                id: list
                model: page.shelf.rows
                delegate: C.ItemDelegate {
                    id: file
                    required property var modelData
                    width: list.width; height: 48; leftPadding: 10; rightPadding: 10
                    background: Rectangle {
                        radius: 10; color: file.highlighted ? "#30465d" : file.hovered ? "#2a3039" : "transparent"
                        border.width: file.visualFocus ? 1 : 0; border.color: "#98caff"
                    }
                    highlighted: page.selected.includes(modelData.key)
                    Accessible.name: modelData.kind === "text" ? modelData.name : modelData.path
                    Accessible.checkable: true; Accessible.checked: highlighted
                    onClicked: page.toggle(modelData.key)
                    contentItem: RowLayout {
                        Rectangle {
                            Layout.preferredWidth: 34; Layout.preferredHeight: 34; radius: 9; color: "#293544"
                            Kirigami.Icon { anchors.centerIn: parent; width: 21; height: width
                            source: file.highlighted ? "emblem-checked" : file.modelData.icon || "text-x-generic" }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true; spacing: 0
                            C.Label {
                                font.weight: Font.Medium; Layout.fillWidth: true; text: file.modelData.name
                                textFormat: Text.PlainText; elide: Text.ElideMiddle
                            }
                            C.Label {
                                Layout.fillWidth: true; text: file.modelData.kind === "text" ? i18n("Text") : file.modelData.path
                                textFormat: Text.PlainText; elide: Text.ElideLeft
                                color: "#b2bac5"; font: Kirigami.Theme.smallFont
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
        ColumnLayout {
            anchors.centerIn: parent; width: parent.width - 26; spacing: 6
            visible: !list.count || incoming.containsDrag
            Rectangle {
                Layout.alignment: Qt.AlignHCenter; implicitWidth: 50; implicitHeight: 48; radius: 15
                color: incoming.containsDrag ? "#354e6b" : "#263445"
                Kirigami.Icon { anchors.centerIn: parent; width: 26; height: width; source: "folder-download"; color: "#99caff" }
            }
            C.Label {
                Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; font.weight: Font.DemiBold
                text: incoming.containsDrag ? i18n("Release to add to shelf") : page.shelf.pending ? i18n("Loading…") : i18n("Drop items here")
            }
            C.Label {
                Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; font.pixelSize: 12
                visible: !incoming.containsDrag && !page.shelf.pending
                text: i18n("Keep files, folders, links and text here until you need them."); color: "#b2bac5"
            }
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
