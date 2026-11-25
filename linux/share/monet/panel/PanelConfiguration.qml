// Keep the native editor available if a future Plasma cannot load Monet's editor.
import QtQuick
import QtCore as Core

Item {
    id: root
    required property QtObject panelConfiguration
    property Item panelRuler: view.item ? view.item.panelRuler : null
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
    Loader {
        id: view
        anchors.fill: parent
        Component.onCompleted: {
            installed.sync()
            const page = String(installed.value("Page", ""))
            const path = /^monet-editor\/[0-9a-f]{64}\/MonetPanelConfiguration\.qml$/.test(page) ? page : "@PANEL_EDITOR@"
            setSource(root.configUrl(path), {panelConfiguration: root.panelConfiguration, advancedPage: root.kdePage})
        }
        onStatusChanged: {
            if (status === Loader.Error && String(source) !== String(root.kdePage))
                setSource(root.kdePage, {panelConfiguration: root.panelConfiguration})
        }
    }
}
