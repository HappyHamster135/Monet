import QtQuick
import QtQuick.Controls as C

C.ScrollView {
    id: page
    contentWidth: availableWidth
    clip: true
    function revealFocus() {
        const item = page.Window.window?.activeFocusItem
        let ancestor = item
        while (ancestor && ancestor !== page.contentItem) ancestor = ancestor.parent
        if (!ancestor) return
        const view = page.contentItem
        const bounds = item.mapToItem(view, 0, 0, item.width, item.height)
        const delta = bounds.y < 0 ? bounds.y : Math.max(0, bounds.y + bounds.height - view.height)
        view.contentY = Math.max(0, Math.min(view.contentHeight - view.height, view.contentY + delta))
    }
    Connections {
        target: page.Window.window
        function onActiveFocusItemChanged() { Qt.callLater(page.revealFocus) }
    }
}
