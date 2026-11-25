// Keep the native editor available if a future Plasma cannot load Monet's editor.
import QtQuick

Item {
    id: root
    required property QtObject panelConfiguration
    property Item panelRuler: view.item ? view.item.panelRuler : null
    readonly property url kdePage: Qt.resolvedUrl("KdePanelConfiguration.qml")
    signal closeContextMenu
    onCloseContextMenu: if (view.item) view.item.closeContextMenu()
    implicitWidth: view.item ? view.item.implicitWidth : 440
    implicitHeight: view.item ? view.item.implicitHeight : 600
    Loader {
        id: view
        anchors.fill: parent
        Component.onCompleted: setSource(Qt.resolvedUrl("@PANEL_EDITOR@"), {
            panelConfiguration: root.panelConfiguration, advancedPage: root.kdePage
        })
        onStatusChanged: {
            if (status === Loader.Error && String(source) !== String(root.kdePage))
                setSource(root.kdePage, {panelConfiguration: root.panelConfiguration})
        }
    }
}
