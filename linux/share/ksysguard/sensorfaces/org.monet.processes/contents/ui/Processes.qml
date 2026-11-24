import QtQuick
import QtQuick.Controls as Controls
import Qt.labs.qmlmodels
import org.kde.ksysguard.process as Process
import "../../../org.monet.performance/contents/ui" as Performance

// Monet's part of KDE's Processes table: under each process, the app it belongs to by the name
// the Applications page gives it (ProcessCell, in place of KDE's first cell; KDE's cells for
// every other column). Which app is KDE's own grouping of the account's apps, read only while
// the page is in view. Should KDE's table ever look different, it stays KDE's own.
Item {
    id: processes
    visible: false
    // KDE's ProcessTableView, found in the face once it's made.
    property Item table: null
    property bool active: false
    property QtObject chooser: null
    // {pid: {id, name}} of the apps' processes.
    property var apps: ({})

    Component { id: headingDelegate; Performance.TableHeading {} }

    function find(item, depth) {
        if (!item || depth > 6) return null
        if (item.hasOwnProperty("processModel") && item.hasOwnProperty("flatList") && item.hasOwnProperty("view"))
            return item
        for (const child of Array.from(item.children || []).concat(Array.from(item.contentChildren || []))) {
            const found = find(child, depth + 1)
            if (found) return found
        }
        return null
    }
    function attach(content) {
        if (chooser) return true
        const found = find(content, 0)
        if (!found || !found.delegate || !found.processModel) return false
        table = found
        // Keep KDE's hit testing, sorting and column resize handles.
        const header = Array.from(found.children).find(child => child instanceof Controls.HorizontalHeaderView)
        if (header) header.delegate = headingDelegate
        chooser = chooserComponent.createObject(processes, {kde: found.delegate})
        found.delegate = chooser
        return true
    }
    // Names for the apps KDE couldn't name (a Steam game started before Monet made its entry).
    function lookNow() {
        appNames.look([])
    }
    function refresh() {
        const names = {}, nameColumn = grouping.enabledAttributes.indexOf("appName")
        const menuColumn = grouping.enabledAttributes.indexOf("menuId")
        if (nameColumn < 0) return
        for (let row = 0; row < grouping.rowCount(); ++row) {
            const name = String(grouping.data(grouping.index(row, nameColumn), Process.ProcessDataModel.Value) || "")
            const menu = menuColumn < 0 ? "" : String(grouping.data(grouping.index(row, menuColumn), Process.ProcessDataModel.Value) || "")
            for (const pid of grouping.data(grouping.index(row, nameColumn), Process.ProcessDataModel.PIDs) || [])
                names[Number(pid)] = {"id": menu || name, "name": name}
        }
        apps = names
    }

    // The account's apps, as the Applications page groups them: KDE's model, its own copy.
    Process.ApplicationDataModel {
        id: grouping
        enabled: processes.active && processes.table !== null
        enabledAttributes: ["appName", "iconName", "menuId"]
    }
    Performance.AppNames {
        id: appNames
        model: grouping
        active: processes.active && processes.table !== null
    }
    Timer {
        interval: 2000
        repeat: true
        running: processes.active && processes.table !== null
        triggeredOnStart: true
        onTriggered: processes.refresh()
    }
    Connections {
        target: grouping
        function onRowsInserted() { lookLater.restart() }
    }
    Timer {
        id: lookLater
        interval: 3000
        onTriggered: processes.lookNow()
    }
    onActiveChanged: if (active) lookLater.restart()

    Component {
        id: chooserComponent
        DelegateChooser {
            // KDE's own choice of cell for each column.
            property var kde
            DelegateChoice {
                column: processes.table && processes.table.model && processes.table.LayoutMirroring.enabled ? processes.table.model.columnCount() - 1 : 0
                ProcessCell {
                    table: processes.table
                    apps: processes.apps
                }
            }
            DelegateChoice { delegate: kde }
        }
    }
}
