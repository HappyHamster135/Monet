import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.ksysguard.process as Process
import org.kde.ksysguard.table as Table
import "../../../org.monet.performance/contents/ui" as Performance
import "../../../org.monet.performance/contents/ui/appnames.js" as Names

// An app's name in KDE's Applications table, and under it what its front window shows
// (a browser's ChatGPT, "and 3 more"), from the windows of the row's own processes. A web
// app's window goes by the web app's name and icon. KDE's cell otherwise: its selection, hover
// and icon size.
Table.FirstCellDelegate {
    id: cell
    // KDE's ApplicationsTableView, and Monet's names for what it couldn't name (AppNames).
    property Item table
    property QtObject names

    readonly property var pids: model.PIDs || []
    readonly property string name: String(model.display || "")
    readonly property var source: table ? table.sourceModel : null
    readonly property int sourceRow: {
        cell.name  // the names Monet adds arrive as new names
        return table && table.model ? table.model.mapToSource(table.model.index(model.row, 0)).row : -1
    }
    function attribute(id, role) {
        const column = source && source.enabledAttributes ? source.enabledAttributes.indexOf(id) : -1
        return column < 0 || sourceRow < 0 ? "" : String(source.data(source.index(sourceRow, column), role) ?? "")
    }
    readonly property string appIcon: { cell.name; return attribute("iconName", Qt.DisplayRole) }
    readonly property string menuId: { cell.name; return attribute("menuId", Process.ProcessDataModel.Value) }
    readonly property var windows: Names.windowsOf(pids, Performance.MonitorWindows.windows)
    // Until monet-quick names a row KDE couldn't, its own windows may.
    readonly property var windowName: Names.unresolved(name, menuId, appIcon) ? Names.windowName({"id": name, "name": name}, windows) : null
    readonly property string shownName: windowName ? windowName.name : name
    readonly property var line: Names.windowLine({"name": shownName, "menuId": menuId, "id": name}, windows, names ? names.found : {})
    readonly property string detail: line.more > 0
        ? i18ndp("monet", "%2 and 1 more", "%2 and %1 more", line.more, line.text) : line.text

    iconName: appIcon
    Accessible.name: detail ? shownName + ", " + detail : shownName

    contentItem: RowLayout {
        // The style shows the whole name as a tooltip when it doesn't fit.
        readonly property bool truncated: title.truncated || subtitle.truncated
        spacing: Kirigami.Units.smallSpacing

        Kirigami.Icon {
            Layout.preferredWidth: cell.iconSize
            Layout.preferredHeight: Layout.preferredWidth
            Layout.alignment: Qt.AlignVCenter
            source: cell.windowName && cell.windowName.icon ? cell.windowName.icon : cell.appIcon
            fallback: ""
            animated: false
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            spacing: 0
            Label {
                id: title
                Layout.fillWidth: true
                text: cell.shownName
                elide: Text.ElideRight
                maximumLineCount: 1
            }
            RowLayout {
                Layout.fillWidth: true
                visible: cell.detail !== ""
                spacing: Kirigami.Units.smallSpacing
                Kirigami.Icon {
                    Layout.preferredWidth: Kirigami.Units.iconSizes.small
                    Layout.preferredHeight: Layout.preferredWidth
                    visible: !!cell.line.icon
                    source: cell.line.icon || ""
                    fallback: ""
                    animated: false
                }
                Label {
                    id: subtitle
                    Layout.fillWidth: true
                    text: cell.detail
                    elide: Text.ElideRight
                    maximumLineCount: 1
                    font: Kirigami.Theme.smallFont
                    color: cell.selected ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.disabledTextColor
                }
            }
        }
    }
}
