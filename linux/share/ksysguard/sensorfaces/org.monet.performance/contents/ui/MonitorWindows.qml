pragma Singleton
import QtQuick
import org.kde.taskmanager as TaskManager

// One event-driven window model for the monitor's QML engine. Wayland does not
// reliably reflect compositor-initiated minimization in QWindow.visibility.
// The windows themselves (their process, title, app and place in front) say what each app
// in the Applications page shows; only their titles, never what's inside them.
QtObject {
    id: state
    property bool minimized: false
    property var windows: []
    function allMinimized(windows) {
        const matches = windows.filter(window => window.isWindow
            && ["org.kde.plasma-systemmonitor", "plasma-systemmonitor"].includes(String(window.appId).replace(/\.desktop$/, "")))
        // Missing metadata is not evidence that the window is hidden. If more
        // than one monitor is open, keep sampling while any is visible.
        return matches.length > 0 && matches.every(window => window.minimized === true)
    }
    function scan() {
        const all = [], shown = []
        let key = ""
        for (let row = 0; row < tasks.rowCount(); ++row) {
            const index = tasks.index(row, 0)
            const window = {appId: tasks.data(index, TaskManager.AbstractTasksModel.AppId),
                isWindow: tasks.data(index, TaskManager.AbstractTasksModel.IsWindow),
                minimized: tasks.data(index, TaskManager.AbstractTasksModel.IsMinimized)}
            all.push(window)
            if (window.isWindow !== true) continue
            const seen = {pid: Number(tasks.data(index, TaskManager.AbstractTasksModel.AppPid)) || 0,
                title: String(tasks.data(index, Qt.DisplayRole) || ""),
                appId: String(window.appId || ""),
                appName: String(tasks.data(index, TaskManager.AbstractTasksModel.AppName) || ""),
                active: tasks.data(index, TaskManager.AbstractTasksModel.IsActive) === true,
                minimized: window.minimized === true,
                order: Number(tasks.data(index, TaskManager.AbstractTasksModel.StackingOrder)) || 0}
            key += JSON.stringify(seen)
            seen.icon = tasks.data(index, Qt.DecorationRole)
            shown.push(seen)
        }
        minimized = allMinimized(all)
        // Unchanged windows keep the tables from looking at them again.
        if (key !== shownKey) {
            shownKey = key
            windows = shown
        }
    }
    property string shownKey: ""
    property QtObject tasks: TaskManager.TasksModel {
        groupMode: TaskManager.TasksModel.GroupDisabled
    }
    property QtObject updates: Connections {
        target: state.tasks
        function onDataChanged(topLeft, bottomRight, roles) { scanLater.restart() }
        function onRowsInserted() { scanLater.restart() }
        function onRowsRemoved() { scanLater.restart() }
        function onModelReset() { scanLater.restart() }
    }
    property Timer scanLater: Timer { interval: 25; onTriggered: state.scan() }
    Component.onCompleted: scanLater.start()
}
