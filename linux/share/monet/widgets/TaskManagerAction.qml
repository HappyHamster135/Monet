import QtQuick
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.kde.taskmanager as TaskManager

PlasmaCore.Action {
    id: action
    text: i18nd("monet", "Task Manager")
    icon.name: "utilities-system-monitor"
    // Creating the window model only on demand avoids a resident model in every
    // panel action. Activating a task also restores a minimized Wayland window.
    onTriggered: {
        cleanup.stop()
        if (!tasks) tasks = taskFactory.createObject(action)
        activateLater.restart()
    }
    function isTaskManager(appId) {
        return ["org.kde.plasma-systemmonitor", "plasma-systemmonitor"].includes(String(appId).replace(/\.desktop$/, ""))
    }
    property QtObject tasks: null
    property Component taskFactory: Component { TaskManager.TasksModel { groupMode: TaskManager.TasksModel.GroupDisabled } }
    property Timer activateLater: Timer {
        interval: 150
        onTriggered: {
            let restored = false
            for (let row = 0; row < action.tasks.rowCount(); ++row) {
                const index = action.tasks.index(row, 0)
                const appId = action.tasks.data(index, TaskManager.AbstractTasksModel.AppId)
                if (action.isTaskManager(appId)
                        && action.tasks.data(index, TaskManager.AbstractTasksModel.IsWindow)) {
                    action.tasks.requestActivate(index)
                    restored = true
                    break
                }
            }
            if (!restored) action.runner.connectSource("'@LIBEXECDIR@/monet-quick' search-open system-monitor")
            cleanup.restart()
        }
    }
    property Timer cleanup: Timer {
        // requestActivate obtains a Wayland activation token asynchronously.
        // Keep its model alive until the request has been sent to KWin.
        interval: 1000
        onTriggered: { if (action.tasks) action.tasks.destroy(); action.tasks = null }
    }
    property QtObject runner: P5Support.DataSource {
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => disconnectSource(source)
    }
}
