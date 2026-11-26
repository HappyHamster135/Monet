import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import "IslandLayout.js" as IslandLayout

C.ScrollView {
    id: gridView
    required property var entries
    property string lastSection: ""
    property var detailFor: null
    signal selected(string key)
    signal previewRequested(string key)
    contentWidth: availableWidth
    clip: true
    readonly property int columns: IslandLayout.columns(width)
    C.ScrollBar.horizontal.policy: C.ScrollBar.AlwaysOff
    function focusFirst() {
        const index = entries.findIndex(entry => entry.key === lastSection)
        tiles.itemAt(Math.max(0,index))?.forceActiveFocus(Qt.OtherFocusReason)
    }
    GridLayout {
        width: gridView.availableWidth
        columns: gridView.columns
        rowSpacing: IslandLayout.gap; columnSpacing: IslandLayout.gap
        Repeater {
            id: tiles
            model: gridView.entries
            IslandButton {
                required property var modelData
                required property int index
                tile: true; Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.minimumWidth: 0
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
                    if (!d) return
                    const target = tiles.itemAt(Math.max(0, Math.min(tiles.count - 1, index + d)))
                    target?.forceActiveFocus(Qt.TabFocusReason)
                    if (target) {
                        const view = gridView.contentItem
                        if (target.y < view.contentY) view.contentY = target.y
                        else if (target.y + target.height > view.contentY + view.height)
                            view.contentY = target.y + target.height - view.height
                    }
                    event.accepted = true
                }
            }
        }
    }
}
