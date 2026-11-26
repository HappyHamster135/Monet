import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kirigami as K
import "IslandLayout.js" as IslandLayout

ColumnLayout {
    id: gridView
    required property var entries
    property string lastSection: ""
    property var detailFor: null
    signal selected(string key)
    signal previewRequested(string key)
    signal pageSelected(int page)
    property int initialPage: 0
    spacing: 0
    readonly property int columns: IslandLayout.columns(width)
    // Balance the ordinary section grid across two sheets. Smaller displays
    // and a larger tool collection can use as many sheets as actually fit.
    readonly property int rows: Math.max(1, Math.min(3, Math.ceil(entries.length / (columns * 2)),
        Math.floor((height - 23 + IslandLayout.gap) / 54)))
    readonly property int capacity: Math.max(1, rows * columns)
    readonly property int sheetIndex: sheets.currentIndex
    readonly property int count: Math.ceil(entries.length / capacity)
    readonly property real cellWidth: Math.max(1, (width - (columns - 1) * IslandLayout.gap) / columns)
    readonly property real cellHeight: Math.min(IslandLayout.tileHeight, Math.max(1,(sheets.height - (rows - 1)*IslandLayout.gap) / rows))
    function focusTile(index, reason) {
        if (!entries.length) return
        index = Math.max(0, Math.min(entries.length-1, index))
        sheets.setCurrentIndex(Math.floor(index / capacity))
        groups.itemAt(sheets.currentIndex)?.focusAt(index % capacity, reason)
    }
    function focusFirst() {
        const index = entries.findIndex(entry => entry.key === lastSection)
        focusTile(index >= 0 ? index : Math.max(0, initialPage) * capacity, Qt.OtherFocusReason)
    }
    C.SwipeView {
        id: sheets
        Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 0
        clip: true; interactive: count > 1
        onCurrentIndexChanged: if (currentIndex >= 0) gridView.pageSelected(currentIndex)
        Repeater {
            id: groups
            model: gridView.count
            Item {
                id: group
                required property int index
                function focusAt(i, reason) { tiles.itemAt(i)?.forceActiveFocus(reason) }
                Grid {
                    width: parent.width; columns: gridView.columns; spacing: IslandLayout.gap
                    Repeater {
                        id: tiles
                        model: gridView.entries.slice(group.index*gridView.capacity,(group.index+1)*gridView.capacity)
                        IslandButton {
                            required property var modelData
                            required property int index
                            readonly property int absoluteIndex: group.index * gridView.capacity + index
                            tile: true; width: gridView.cellWidth; height: gridView.cellHeight
                            detail: gridView.detailFor ? gridView.detailFor(modelData.key) : ""
                            text: modelData.label; icon.name: modelData.icon; tint: modelData.color
                            objectName: "island-section-" + modelData.key
                            Accessible.description: [detail, modelData.key === gridView.lastSection ? i18n("Selected") : ""].filter(Boolean).join(" · ")
                            Text {
                                visible: modelData.key === gridView.lastSection
                                anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 7
                                text: "✓"; color: "#c4c5cc"; font.pixelSize: 11
                                Accessible.ignored: true
                            }
                            onHoveredChanged: if (hovered) gridView.previewRequested(modelData.key)
                            onVisualFocusChanged: if (visualFocus) gridView.previewRequested(modelData.key)
                            onClicked: gridView.selected(modelData.key)
                            Keys.onPressed: event => {
                                const d = event.key === Qt.Key_Left ? -1 : event.key === Qt.Key_Right ? 1 :
                                    event.key === Qt.Key_Up ? -gridView.columns : event.key === Qt.Key_Down ? gridView.columns : 0
                                if (d) { gridView.focusTile(absoluteIndex + d, Qt.TabFocusReason); event.accepted = true }
                            }
                        }
                    }
                }
            }
        }
    }
    Row {
        Layout.alignment: Qt.AlignHCenter; visible: gridView.count > 1
        Repeater {
            model: gridView.count
            C.AbstractButton {
                id: dot
                required property int index
                objectName: "island-dot-" + index
                width: 25; height: 23; checked: sheets.currentIndex === index
                Accessible.name: i18n("Page %1 of %2", index+1, gridView.count)
                onClicked: gridView.focusTile(index * gridView.capacity, Qt.OtherFocusReason)
                contentItem: Item {
                    Rectangle {
                        anchors.centerIn: parent; radius: 4; height: 6; width: dot.checked ? 16 : 6
                        color: dot.checked ? "#f5f5f7" : dot.hovered || dot.visualFocus ? "#aaaab3" : "#57575e"
                        Behavior on width { NumberAnimation { duration: K.Units.shortDuration } }
                    }
                }
            }
        }
    }
}
