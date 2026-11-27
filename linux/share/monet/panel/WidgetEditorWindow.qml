import QtQuick
EditorAppWindow {
    id: window
    required property QtObject containment
    required property QtObject desktopRoot
    required property QtObject pendingUninstallTimer
    readonly property bool contentReady: page.status === Loader.Ready
    required property url pageSource
    property QtObject root: desktopRoot
    geometryKey: "Widgets-" + containment.id
    title: i18nd("monet", "Widgets")
    Connections {
        target: window.containment.corona
        function onEditModeChanged() { if (!window.containment.corona.editMode) window.close() }
    }
    onFinished: {
        if (host.widgetWindow === window) host.widgetWindow = null
        Qt.callLater(window.destroy)
    }
    Loader {
        id: page
        anchors.fill: parent
        Component.onCompleted: setSource(window.pageSource, {containment: window.containment, sidePanel: window})
        onLoaded: item.closed.connect(window.close)
    }
    onContainmentChanged: if (page.item) page.item.containment = containment
}
