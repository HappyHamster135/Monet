import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts

C.ScrollView {
    id: gridView
    required property var entries
    signal selected(string key)
    contentWidth: availableWidth
    clip: true
    readonly property int columns: width < 348 ? 3 : width < 426 ? 4 : 5
    C.ScrollBar.horizontal.policy: C.ScrollBar.AlwaysOff
    function focusFirst() { tiles.itemAt(0)?.forceActiveFocus(Qt.TabFocusReason) }
    GridLayout {
        width: gridView.availableWidth
        columns: gridView.columns
        rowSpacing: 6; columnSpacing: 6
        Repeater {
            id: tiles
            model: gridView.entries
            IslandButton {
                required property var modelData
                required property int index
                tile: true; Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.minimumWidth: 0
                text: modelData.label; icon.name: modelData.icon; tint: modelData.color
                objectName: "island-section-" + modelData.key
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
