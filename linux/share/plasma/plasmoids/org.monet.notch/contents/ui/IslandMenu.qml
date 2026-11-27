import QtQuick
import QtQuick.Controls as C

C.Menu {
    id: menu
    required property Item bounds
    required property Item anchorItem
    property real preferredWidth: 210
    property point origin: Qt.point(0, 0)
    parent: bounds
    popupType: C.Popup.Item
    modal: true; dim: false
    margins: 0
    leftPadding: 5; rightPadding: 12; topPadding: 5; bottomPadding: 5
    font.pixelSize: 12
    width: Math.min(preferredWidth, bounds.width)
    height: Math.min(implicitHeight, bounds.height)
    x: Math.max(0, Math.min(origin.x + anchorItem.width - width, bounds.width - width))
    y: Math.max(0, Math.min(origin.y + anchorItem.height + 4, bounds.height - height))
    onAboutToShow: origin = anchorItem.mapToItem(bounds, 0, 0)
    onCurrentIndexChanged: if (visible && currentIndex >= 0) Qt.callLater(() => {
        if (visible && currentIndex >= 0) contentItem.positionViewAtIndex(currentIndex, ListView.Contain)
    })
    background: Rectangle { radius: 12; color: "#26262b"; border.width: 1; border.color: "#38ffffff" }
    // The desktop style only enables scrolling when a menu exceeds the entire
    // window. A notch menu has the smaller page viewport as its limit.
    Binding {
        target: menu.contentItem
        property: "interactive"
        value: menu.contentItem.contentHeight > menu.availableHeight
    }
    Connections {
        target: menu.bounds
        function onVisibleChanged() { if (!target.visible) menu.close() }
        function onEnabledChanged() { if (!target.enabled) menu.close() }
    }
}
