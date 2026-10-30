pragma Singleton
import QtQuick
import org.kde.taskmanager as TaskManager

// One event-driven window model for the monitor's QML engine. Wayland does not
// reliably reflect compositor-initiated minimization in QWindow.visibility.
QtObject {
    id: state
    property bool minimized: false
    function allMinimized(windows) {
        const matches = windows.filter(window => window.isWindow
            && ["org.kde.plasma-systemmonitor", "plasma-systemmonitor"].includes(String(window.appId).replace(/\.desktop$/, "")))
        // Missing metadata is not evidence that the window is hidden. If more
        // than one monitor is open, keep sampling while any is visible.
        return matches.length > 0 && matches.every(window => window.minimized === true)
    }
    function scan() {
        const windows = []
        for (let row = 0; row < tasks.rowCount(); ++row) {
            const index = tasks.index(row, 0)
            windows.push({appId: tasks.data(index, TaskManager.AbstractTasksModel.AppId),
                isWindow: tasks.data(index, TaskManager.AbstractTasksModel.IsWindow),
                minimized: tasks.data(index, TaskManager.AbstractTasksModel.IsMinimized)})
        }
        minimized = allMinimized(windows)
    }
    property QtObject tasks: TaskManager.TasksModel {
        groupMode: TaskManager.TasksModel.GroupDisabled
    }
    property QtObject updates: Connections {
        target: state.tasks
        function onDataChanged(topLeft, bottomRight, roles) {
            if (!roles.length || roles.includes(TaskManager.AbstractTasksModel.IsMinimized)
                    || roles.includes(TaskManager.AbstractTasksModel.AppId)
                    || roles.includes(TaskManager.AbstractTasksModel.IsWindow)) scanLater.restart()
        }
        function onRowsInserted() { scanLater.restart() }
        function onRowsRemoved() { scanLater.restart() }
        function onModelReset() { scanLater.restart() }
    }
    property Timer scanLater: Timer { interval: 25; onTriggered: state.scan() }
    Component.onCompleted: scanLater.start()
}
