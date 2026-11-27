// Keep the native editor available if a future Plasma cannot load Monet's editor.
import QtQuick
import "file://@DATADIR@/monet/panel/EditorWindows.js" as EditorWindows
import QtCore as Core

Item {
    id: root
    required property QtObject panelConfiguration
    property Item panelRuler: null
    function configUrl(name) {
        const nested = Qt.resolvedUrl(".").toString().endsWith("/monet-editor-entry/")
        return Qt.resolvedUrl((nested ? "../" : "") + name)
    }
    readonly property url kdePage: configUrl("KdePanelConfiguration.qml")
    signal closeContextMenu
    onCloseContextMenu: if (view.item) view.item.closeContextMenu()
    implicitWidth: view.item ? view.item.implicitWidth : 440
    implicitHeight: view.item ? view.item.implicitHeight : 600
    // Qt can keep this wrapper mapped throughout a login. Read the installed
    // revision each time Plasma opens the editor, including after a live update.
    Core.Settings {
        id: installed
        location: root.configUrl("MonetPanelEditor.ini")
        category: "Editor"
    }
    Timer { id: dismissRequest; interval: 120; onTriggered: configDialog.close() }
    Loader {
        id: view
        anchors.fill: parent
        Component.onCompleted: {
            installed.sync()
            const page = String(installed.value("Page", ""))
            const path = /^monet-editor\/[0-9a-f]{64}\/MonetPanelConfiguration\.qml$/.test(page) ? page : "@PANEL_EDITOR@"
            try {
                const parentItem = panel.contentItem.children.find(child => child.fixedTopFloatingPadding !== undefined)
                if (!parentItem) throw new Error("panel content unavailable")
                const host = EditorWindows.forParent(parentItem)
                if (!host.openPanel(panel, plasmoid, root.configUrl(path))) throw new Error("editor")
                configDialog.contentItem.opacity = 0
                dismissRequest.restart()
            } catch (error) {
                console.warn("Monet editor:", error)
                setSource(root.kdePage, {panelConfiguration: root.panelConfiguration})
            }
        }
        onStatusChanged: {
            if (status === Loader.Error && String(source) !== String(root.kdePage))
                setSource(root.kdePage, {panelConfiguration: root.panelConfiguration})
        }
    }
}
