// Hand the native sidebar request to a regular editor application window.
import QtQuick
import "file://@DATADIR@/monet/panel/EditorWindows.js" as EditorWindows
import org.kde.plasma.core as PlasmaCore
Item {
    id: gallery
    property QtObject containment
    property PlasmaCore.Dialog sidePanel
    property bool preventWindowHide: false
    property bool outputOnly: false
    property bool floatingEditor: true
    signal closed()
    width: fallback.item ? fallback.item.width : 1
    height: fallback.item ? fallback.item.height : 1
    property bool handedOff: false
    Component.onDestruction: if (handedOff && sidePanel?.contentItem) sidePanel.contentItem.opacity = 1
    Timer { id: dismissRequest; interval: 120; onTriggered: gallery.closed() }
    Loader { id: fallback; anchors.fill: parent; onLoaded: item.closed.connect(gallery.closed) }
    Component.onCompleted: {
        try {
            const host = EditorWindows.forParent(root)
            if (!host.openWidgets(containment || root.containment.plasmoid, root, pendingUninstallTimer, Qt.resolvedUrl("MonetWidgetExplorer.qml"))) throw new Error("widgets")
            handedOff = true
            sidePanel.contentItem.opacity = 0
            dismissRequest.restart()
        } catch (error) {
            console.warn("Monet widgets:", error)
            fallback.setSource(Qt.resolvedUrl("KdeWidgetExplorer.qml"), {containment: containment, sidePanel: sidePanel})
        }
    }
}
