import QtQuick
import QtQuick.Controls as C
import "IslandLayout.js" as IslandLayout

Flickable {
    id: gridView
    required property var entries
    property string lastSection: ""
    property var detailFor: null
    signal selected(string key)
    signal previewRequested(string key)

    readonly property int columns: IslandLayout.columns(width)
    readonly property real cellHeight: Math.max(60, Math.floor((height - 2 * IslandLayout.gap) / 3))
    readonly property real cellWidth: Math.max(1, (tilesGrid.width - (columns - 1) * IslandLayout.gap) / columns)

    clip: true
    contentWidth: width
    contentHeight: tilesGrid.implicitHeight
    flickableDirection: Flickable.VerticalFlick
    boundsBehavior: Flickable.StopAtBounds
    interactive: contentHeight > height
    ScrollInput { view: gridView; enabled: gridView.interactive }
    C.ScrollIndicator.vertical: C.ScrollIndicator { id: indicator }

    function revealTile(item) {
        const top = item.y
        const bottom = top + item.height
        if (top < contentY || bottom > contentY + height) {
            cancelFlick()
            contentY = Math.max(0, Math.min(contentHeight - height, top < contentY ? top : bottom - height))
        }
    }
    function focusTile(index, reason) {
        tilesGrid.forceLayout()
        const item = tiles.itemAt(Math.max(0, Math.min(entries.length - 1, index)))
        if (item) {
            revealTile(item)
            item.forceActiveFocus(reason)
        }
    }
    function focusFirst() {
        focusTile(entries.findIndex(entry => entry.key === lastSection), Qt.OtherFocusReason)
    }

    Grid {
        id: tilesGrid
        width: Math.max(0, gridView.width - (gridView.interactive ? indicator.width : 0))
        columns: gridView.columns
        spacing: IslandLayout.gap
        Repeater {
            id: tiles
            model: gridView.entries
            IslandButton {
                id: tile
                required property var modelData
                required property int index
                tile: true
                width: gridView.cellWidth
                height: gridView.cellHeight
                detail: gridView.detailFor ? gridView.detailFor(modelData.key) : ""
                text: modelData.label
                icon.name: modelData.icon
                tint: modelData.color
                objectName: "island-section-" + modelData.key
                Accessible.description: [detail, modelData.key === gridView.lastSection ? i18n("Selected") : ""].filter(Boolean).join(" · ")
                Text {
                    visible: tile.modelData.key === gridView.lastSection
                    anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 7
                    text: "✓"; color: "#c4c5cc"; font.pixelSize: 11
                    Accessible.ignored: true
                }
                onHoveredChanged: if (hovered) gridView.previewRequested(modelData.key)
                onVisualFocusChanged: if (visualFocus) {
                    gridView.revealTile(tile)
                    gridView.previewRequested(modelData.key)
                }
                onClicked: gridView.selected(modelData.key)
                Keys.onPressed: event => {
                    const delta = event.key === Qt.Key_Left ? -1 : event.key === Qt.Key_Right ? 1 :
                        event.key === Qt.Key_Up ? -gridView.columns : event.key === Qt.Key_Down ? gridView.columns : 0
                    if (delta) {
                        gridView.focusTile(index + delta, Qt.TabFocusReason)
                        event.accepted = true
                    }
                }
            }
        }
    }
}
