import QtQuick
import QtQuick.Controls as C

C.TabBar {
    id: strip
    objectName: "notchTabStrip"
    required property var tabs
    required property var labels
    required property int page
    signal chosen(int tab)

    property var order: []
    property bool syncing: false
    property bool ready: false
    function syncSelection() {
        // TabBar selects an interim item while Repeater replaces its delegates.
        // Only a completed native selection should navigate to another page.
        if (!ready) return
        syncing = true
        if (order !== tabs) order = tabs
        setCurrentIndex(order.indexOf(page))
        syncing = false
    }
    Component.onCompleted: { ready = true; syncSelection() }
    onTabsChanged: syncSelection()
    onPageChanged: syncSelection()
    onCurrentIndexChanged: {
        if (!syncing && currentItem && order[currentIndex] === currentItem.modelData)
            chosen(currentItem.modelData)
    }
    Repeater {
        model: strip.order
        C.TabButton {
            required property int modelData
            text: strip.labels[modelData]
            onClicked: strip.chosen(modelData)
            Accessible.onPressAction: click()
        }
    }
}
