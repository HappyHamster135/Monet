// Keep Plasma's own controls reachable when the panel editor is taller than the screen.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Window

Controls.ScrollView {
    id: scroll
    required property QtObject panelConfiguration
    property alias panelRuler: configuration.panelRuler
    signal closeContextMenu

    implicitWidth: Math.min(configuration.implicitWidth + rightPadding, Screen.width - 24)
    implicitHeight: Math.min(configuration.implicitHeight, Math.max(120, Screen.height - 140))
    contentWidth: Math.max(availableWidth, configuration.implicitWidth)
    contentHeight: configuration.implicitHeight
    clip: true
    onCloseContextMenu: configuration.closeContextMenu()

    KdePanelConfiguration {
        id: configuration
        panelConfiguration: scroll.panelConfiguration
        width: scroll.contentWidth
        height: implicitHeight
    }
}
