// Created in the lifetime of the panel/desktop, never in a temporary popup.
import QtQuick
Item {
    id: host
    visible: false
    objectName: "monetEditorHost"
    property var panelWindow: null
    property var widgetWindow: null
    property Component panelFactory: Component { PanelEditorWindow {} }
    property Component widgetFactory: Component { WidgetEditorWindow {} }
    function openPanel(panel, plasmoid, page) {
        if (panelWindow?.closingPending) panelWindow.completeClose()
        plasmoid.corona.editMode = true
        if (!panelWindow) panelWindow = panelFactory.createObject(host, {panel: panel, plasmoid: plasmoid, pageSource: page})
        else panelWindow.editPanel(panel, plasmoid, page)
        if (!panelWindow || !panelWindow.contentReady) {
            if (panelWindow) panelWindow.destroy()
            panelWindow = null
            return false
        }
        panelWindow.present()
        return true
    }
    function openWidgets(containment, desktopRoot, timer, page) {
        if (widgetWindow?.closingPending) widgetWindow.completeClose()
        if (!widgetWindow) widgetWindow = widgetFactory.createObject(host, {
            containment: containment, desktopRoot: desktopRoot, pendingUninstallTimer: timer, pageSource: page})
        else widgetWindow.containment = containment
        if (!widgetWindow || !widgetWindow.contentReady) {
            if (widgetWindow) widgetWindow.destroy()
            widgetWindow = null
            return false
        }
        widgetWindow.present()
        return true
    }
}
