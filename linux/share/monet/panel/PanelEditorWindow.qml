import QtQuick
EditorAppWindow {
    id: window
    required property QtObject panel
    required property QtObject plasmoid
    readonly property bool contentReady: page.status === Loader.Ready
    required property url pageSource
    property QtObject configDialog: window
    property QtObject panelConfiguration: QtObject {
        property QtObject panelRulerView: QtObject { property bool visible: false }
    }
    geometryKey: "Panel-" + plasmoid.id
    initialScreenName: panel.screenToFollow?.name || ""
    title: i18nd("monet", "Desktop layout")
    function editPanel(nextPanel, nextPlasmoid, source) {
        const notch = Array.from(nextPlasmoid.applets || []).some(a => a.pluginName === "org.monet.notch")
        // A notch on this screen belongs to the same desktop editor. Retain the
        // taskbar context so switching back does not open a second window.
        if (nextPlasmoid === plasmoid || (notch && nextPanel.screenToFollow === panel.screenToFollow)) {
            page.item?.selectPage?.(notch ? 3 : 0)
            return
        }
        page.source = ""
        panel = nextPanel
        plasmoid = nextPlasmoid
        pageSource = source
        page.setSource(source, {panelConfiguration: window.panelConfiguration})
    }
    function showAddWidgetDialog() { plasmoid.internalAction("add widgets")?.trigger() }
    function finishEditing() { plasmoid.corona.editMode = false; close() }
    Connections {
        target: window.plasmoid.corona
        function onEditModeChanged() { if (!window.plasmoid.corona.editMode) window.close() }
    }
    onFinished: {
        if (host.panelWindow === window) host.panelWindow = null
        if (plasmoid?.corona.editMode) plasmoid.corona.editMode = false
        Qt.callLater(window.destroy)
    }
    Loader {
        id: page
        anchors.fill: parent
        onLoaded: item.panelConfiguration = window.panelConfiguration
        // Required properties must be supplied before construction.
        Component.onCompleted: setSource(window.pageSource, {panelConfiguration: window.panelConfiguration})
    }
}
