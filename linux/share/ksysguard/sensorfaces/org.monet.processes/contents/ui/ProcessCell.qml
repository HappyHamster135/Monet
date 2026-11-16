import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.ksysguard.process as Process
import org.kde.ksysguard.table as Table
import "../../../org.monet.performance/contents/ui/appnames.js" as Names

// A process in KDE's Processes table, and under its own name the app it belongs to, by the
// name the Applications page gives it (R.E.P.O. under REPO.exe, Chromium under chrome): in the
// list for each process of an app, in the tree where the app's group begins. KDE's cell otherwise.
Table.FirstCellDelegate {
    id: cell
    // KDE's ProcessTableView, and {pid: {id, name}} of the apps (Processes.qml).
    property Item table
    property var apps: ({})

    readonly property string name: String(model.display || "")
    readonly property bool flat: table ? table.flatList : true
    // The process and the one that started it, as the tree shows them.
    readonly property var place: {
        cell.name
        const processes = table ? table.processModel : null
        if (!processes || processes.pidColumn < 0) return {pid: 0, parent: 0}
        let index = treeView.index(model.row, 0)
        if (treeView.model !== table.model) index = treeView.model.mapToSource(index)
        // KDE's proxies: its filter, its chart cache and its column display, then the processes.
        let proxy = table.model
        for (let step = 0; proxy && proxy !== processes && step < 6; ++step, proxy = proxy.sourceModel) index = proxy.mapToSource(index)
        if (proxy !== processes) return {pid: 0, parent: 0}
        const pid = processes.data(processes.index(index.row, processes.pidColumn, index.parent), Process.ProcessDataModel.Value)
        const parent = index.parent.valid
            ? processes.data(processes.index(index.parent.row, processes.pidColumn, index.parent.parent), Process.ProcessDataModel.Value) : 0
        return {pid: Number(pid) || 0, parent: Number(parent) || 0}
    }
    readonly property string detail: Names.processApp(name, apps[place.pid], apps[place.parent], flat)

    treeDecorationVisible: !flat
    iconName: name.split(" ")[0].toLowerCase()
    Accessible.name: detail ? name + ", " + detail : name

    contentItem: RowLayout {
        // The style shows the whole name as a tooltip when it doesn't fit.
        readonly property bool truncated: title.truncated || subtitle.truncated
        spacing: Kirigami.Units.smallSpacing

        Kirigami.Icon {
            Layout.preferredWidth: cell.iconSize
            Layout.preferredHeight: Layout.preferredWidth
            Layout.alignment: Qt.AlignVCenter
            source: cell.iconName
            fallback: ""
            animated: false
            visible: status == Kirigami.Icon.Ready || !cell.isTreeNode
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            spacing: 0
            Label {
                id: title
                Layout.fillWidth: true
                text: cell.name
                elide: Text.ElideRight
                maximumLineCount: 1
            }
            Label {
                id: subtitle
                Layout.fillWidth: true
                visible: text !== ""
                text: cell.detail
                elide: Text.ElideRight
                maximumLineCount: 1
                font: Kirigami.Theme.smallFont
                color: cell.selected ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.disabledTextColor
            }
        }
    }
}
