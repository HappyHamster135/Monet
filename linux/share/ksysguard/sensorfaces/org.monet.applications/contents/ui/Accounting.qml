import QtQuick
import org.kde.ksysguard.process as Process
import "../../../org.monet.performance/contents/ui" as Performance
import "../../../org.monet.performance/contents/ui/appnames.js" as Names

// So the Applications rows add up to the cards above them, as Windows' Task Manager's do. KDE's
// rows hold this account's apps (each app's systemd unit) and its Background Services; every
// other process of this account joins the row of the app that started it (KDE's sums for that
// row become its own processes' and theirs), else Other ("Java (8)" when it's mostly one busy
// program); what's left of each card is System: the PC's own services, other accounts, and the
// kernel with its interrupts. Every two seconds while the page is in view, from KDE's own
// process list (which KDE's rows read anyway).
QtObject {
    id: accounting
    // KDE's ApplicationsTableView, and Monet's names and overrides for its model (AppNames).
    property Item table
    property QtObject names
    property bool active: false
    // The cards' own readings (the CPU, Memory, Network and Storage cards).
    property QtObject readings: Performance.SummaryReadings { sampling: accounting.active }

    // {attribute: value in its column's units} of Other and System, and their busiest processes.
    property var other: ({})
    property var otherBusiest: []
    property var mostly: null
    property int otherCount: 0
    property var system: ({})
    property var systemBusiest: []
    property real cpuMax: 0

    readonly property QtObject source: table ? table.sourceModel : null
    // The table's columns, left to right, by attribute: KDE leaves out the ones it only reads.
    function shown() {
        if (!source || !source.enabledAttributes) return []
        const hidden = source.hiddenAttributes || []
        return Array.from(source.enabledAttributes).filter(a => !hidden.includes(a))
    }
    function header(attribute, role) {
        const column = source ? source.enabledAttributes.indexOf(attribute) : -1
        return column < 0 ? undefined : source.headerData(column, Qt.Horizontal, role)
    }
    function total(attribute) {
        const which = Names.card(attribute)
        const sensor = which === "cpu" ? readings.cpu : which === "used" ? readings.used : which === "read" ? readings.read
            : which === "write" ? readings.write : which === "download" ? readings.download : which === "upload" ? readings.upload : null
        return sensor && typeof sensor.value === "number" ? sensor.value : NaN
    }
    // KDE's process list, read as plain values.
    function snapshot(attributes) {
        const columns = processes.enabledAttributes
        const at = {}
        for (let i = 0; i < columns.length; ++i) at[columns[i]] = i
        const found = []
        for (let row = 0; row < processes.rowCount(); ++row) {
            const value = name => name in at ? processes.data(processes.index(row, at[name]), Process.ProcessDataModel.Value) : undefined
            const values = {}
            for (const attribute of attributes) values[attribute] = Number(value(attribute)) || 0
            found.push({pid: Number(value("pid")) || 0, ppid: Number(value("parentPid")) || 0, uid: value("uid"),
                name: String(value("name") || ""), values: values})
        }
        return found
    }
    function refresh() {
        if (!active || !source || !names) return
        const columns = shown()
        const added = columns.filter(Names.addable)
        const all = snapshot(added)
        const rows = []
        const nameColumn = source.enabledAttributes.indexOf("appName"), menuColumn = source.enabledAttributes.indexOf("menuId")
        for (let row = 0; row < source.rowCount(); ++row) {
            const value = column => column < 0 ? "" : source.data(source.index(row, column), Process.ProcessDataModel.Value)
            rows.push({key: names.key(String(value(nameColumn) || ""), String(value(menuColumn) || "")),
                pids: Array.from(source.data(source.index(row, 0), Process.ProcessDataModel.PIDs) || [])})
        }
        const result = Names.account(rows, all, added)
        names.numbers = result.totals
        // A row KDE files under an id Monet can't know (an autostart entry's own file) keeps its own
        // sums: what it would have gained goes to Other, so nothing is counted twice or not at all.
        const usage = source.enabledAttributes.indexOf("usage")
        for (let row = 0; usage >= 0 && row < rows.length; ++row) {
            const wanted = result.totals[rows[row].key]
            if (wanted && Number(source.data(source.index(row, usage), Process.ProcessDataModel.Value)) !== wanted.usage)
                result.other = result.other.concat(result.added[rows[row].key])
        }
        // What every row says now, the ones that gained processes with them.
        const counted = {}
        for (const attribute of columns) {
            counted[attribute] = 0
            const column = source.enabledAttributes.indexOf(attribute)
            for (let row = 0; row < source.rowCount(); ++row)
                counted[attribute] += Number(source.data(source.index(row, column), Process.ProcessDataModel.Value)) || 0
        }
        cpuMax = Number(header("usage", Process.ProcessDataModel.Maximum)) || 0
        const others = Names.sums(result.other, added)
        const left = {}
        for (const attribute of columns) {
            const unit = Number(header(attribute, Process.ProcessDataModel.Unit)) || 0
            left[attribute] = Names.systemShare(attribute, unit, total(attribute), counted[attribute] + (others[attribute] || 0), cpuMax)
        }
        other = others
        otherCount = result.other.length
        otherBusiest = Names.busiest(result.other, 5)
        mostly = Names.mostlyOne(result.other)
        system = left
        systemBusiest = Names.busiest(Names.systemProcesses(all, result.mine), 5)
    }

    // Every process, with what the table's columns add up.
    property QtObject processes: Process.ProcessDataModel {
        flatList: true
        enabled: accounting.active
        enabledAttributes: ["pid", "parentPid", "uid", "name"].concat(accounting.shown().filter(Names.addable))
    }
    property Timer timer: Timer {
        interval: 2000
        repeat: true
        running: accounting.active && accounting.source !== null
        triggeredOnStart: true
        onTriggered: accounting.refresh()
    }
}
