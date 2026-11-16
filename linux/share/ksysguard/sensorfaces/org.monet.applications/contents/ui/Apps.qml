import QtQuick
import Qt.labs.qmlmodels
import org.kde.ksysguard.formatter as Formatter
import org.kde.ksysguard.table as Table
import "../../../org.monet.performance/contents/ui" as Performance

// Monet's part of KDE's Applications table, added to it as it is: each app by its own name
// and icon (AppNames), what its front window shows under its name (AppCell, in place of KDE's
// first cell), and rows that add up to the cards: an app's row with the processes it started
// in units of their own, Other for the rest of this account's, and System (Accounting,
// PinnedRow). Should KDE's table ever look different, it stays KDE's own.
Item {
    id: apps
    visible: false
    // KDE's ApplicationsTableView, found in the face once it's made.
    property Item table: null
    property bool active: false
    property QtObject chooser: null
    property var pinned: []
    readonly property QtObject names: appNames
    readonly property QtObject sums: accounting

    // The table in KDE's face: what has its app model, view and selection.
    function find(item, depth) {
        if (!item || depth > 6) return null
        if (item.hasOwnProperty("sourceModel") && item.hasOwnProperty("selectedApplications") && item.hasOwnProperty("view"))
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
        if (!found || !found.delegate || !found.sourceModel || !found.parent) return false
        table = found
        chooser = chooserComponent.createObject(apps, {kde: found.delegate})
        found.delegate = chooser
        pinned = [otherComponent.createObject(found.parent, {table: found}), systemComponent.createObject(found.parent, {table: found})]
        return true
    }

    Performance.AppNames {
        id: appNames
        model: apps.table ? apps.table.sourceModel : null
        active: apps.active
    }
    Accounting {
        id: accounting
        table: apps.table
        names: appNames
        active: apps.active && apps.table !== null
    }
    // New rows (a game just started) and new windows, a moment after they settle.
    Connections {
        target: apps.table ? apps.table.sourceModel : null
        function onRowsInserted() { lookLater.restart() }
        function onModelReset() { lookLater.restart() }
    }
    Connections {
        target: Performance.MonitorWindows
        function onWindowsChanged() { lookLater.restart() }
    }
    Timer {
        id: lookLater
        interval: 3000
        onTriggered: appNames.look(Performance.MonitorWindows.windows)
    }
    onActiveChanged: if (active) lookLater.restart()

    Component {
        id: chooserComponent
        DelegateChooser {
            role: "displayStyle"
            // KDE's own choice of cell for each column.
            property var kde
            DelegateChoice {
                column: apps.table && apps.table.model && apps.table.LayoutMirroring.enabled ? apps.table.model.columnCount() - 1 : 0
                AppCell {
                    table: apps.table
                    names: appNames
                }
            }
            // A text column's reading from its value: KDE shows Monet's sums as they are.
            DelegateChoice {
                column: apps.table && apps.table.sourceModel && apps.table.model
                    && apps.table.sourceModel.enabledAttributes.includes("command") ? apps.table.model.commandColumn : 9999
                delegate: kde
            }
            DelegateChoice {
                roleValue: "text"
                Table.TextCellDelegate {
                    text: Formatter.Formatter.formatValue(model.Value, model.Unit)
                }
            }
            DelegateChoice { delegate: kde }
        }
    }
    Component {
        id: otherComponent
        PinnedRow {
            objectName: "monetOtherRow"
            title: accounting.mostly ? i18nd("monet", "%1 (%2)", accounting.mostly.program, accounting.mostly.count)
                : i18nd("monet", "Other processes from you")
            subtitle: i18nd("monet", "Yours, outside your apps")
            icon: "utilities-terminal"
            values: accounting.other
            busiest: accounting.otherBusiest
            cpuMax: accounting.cpuMax
            visible: accounting.otherCount > 0
        }
    }
    Component {
        id: systemComponent
        PinnedRow {
            objectName: "monetSystemRow"
            title: i18nd("monet", "System")
            subtitle: i18nd("monet", "Services and the kernel")
            icon: "computer"
            values: accounting.system
            busiest: accounting.systemBusiest
            cpuMax: accounting.cpuMax
        }
    }
}
