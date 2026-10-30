import QtQuick
import QtQuick.Window

// KDE moves face content into its page. Observe the displayed item, not the
// detached face object, whose Window.window remains null.
QtObject {
    required property Item item
    property bool compositorMinimized: Qt.application.name === "plasma-systemmonitor" && MonitorWindows.minimized
    readonly property bool windowVisible: !compositorMinimized && !!item && (!item.Window.window
        || (item.Window.window.visible && item.Window.window.visibility !== Window.Minimized))
    readonly property bool active: !!item && item.visible && windowVisible
}
