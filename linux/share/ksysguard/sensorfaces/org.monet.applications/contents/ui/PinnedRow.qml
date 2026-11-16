import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.ksysguard.formatter as Formatter
import org.kde.ksysguard.process as Process
import "../../../org.monet.performance/contents/ui/appnames.js" as Names

// A row of Monet's under KDE's apps (Other, System), its readings under each of the table's
// columns, as Windows' Task Manager has Background processes and Windows processes. Opened, it
// lists the busiest processes in it.
Rectangle {
    id: pinned
    // KDE's ApplicationsTableView, whose columns the row follows.
    property Item table
    property string title
    property string subtitle
    property string icon
    // {attribute: value in its column's units}, and [{name, usage}] of the busiest in it.
    property var values: ({})
    property var busiest: []
    property real cpuMax: 0
    property bool expanded: false
    // [{attribute, x, width}] of each of the table's columns.
    property var cells: []

    Layout.fillWidth: true
    implicitHeight: content.implicitHeight
    // The table's own background (KDE's View colors are the palette's base).
    color: palette.base
    Accessible.role: Accessible.Row
    Accessible.name: title + ", " + subtitle

    readonly property QtObject source: table ? table.sourceModel : null
    readonly property Item view: table ? table.view : null

    function header(attribute, role) {
        const column = source ? source.enabledAttributes.indexOf(attribute) : -1
        return column < 0 ? undefined : source.headerData(column, Qt.Horizontal, role)
    }
    // A reading as KDE's column shows it: CPU scaled to every processor where the column is.
    function text(attribute, value) {
        if (typeof value !== "number" || !isFinite(value)) return ""
        const unit = Number(header(attribute, Process.ProcessDataModel.Unit)) || 0
        return attribute === "usage"
            ? Formatter.Formatter.formatValue(Names.cpuShown(value, cpuMax, ((table && table.columnDisplay) || {}).usage), unit)
            : Formatter.Formatter.formatValue(value, unit)
    }
    function measure() {
        if (!source || !view || !source.enabledAttributes) return
        const hidden = source.hiddenAttributes || []
        const shown = Array.from(source.enabledAttributes).filter(a => !hidden.includes(a))
        if (table.LayoutMirroring.enabled) shown.reverse()
        let x = view.contentItem ? view.contentItem.mapToItem(pinned, 0, 0).x : 0
        const found = []
        for (let column = 0; column < shown.length; ++column) {
            const width = Math.max(0, view.columnWidth(column))
            found.push({attribute: shown[column], x: x, width: width})
            x += width + (view.columnSpacing || 0)
        }
        if (JSON.stringify(found) !== JSON.stringify(cells)) cells = found
    }
    function cell(attribute) {
        return cells.find(c => c.attribute === attribute) || null
    }
    readonly property var nameCell: cell("appName") || cells[table && table.LayoutMirroring.enabled ? cells.length - 1 : 0] || null
    readonly property var cpuCell: cell("usage")
    readonly property real indent: (nameCell ? nameCell.x : 0) + Kirigami.Units.largeSpacing * 2 + Kirigami.Units.iconSizes.smallMedium

    onValuesChanged: measure()
    Component.onCompleted: measure()
    Connections {
        target: pinned.view
        ignoreUnknownSignals: true
        function onWidthChanged() { Qt.callLater(pinned.measure) }
        function onContentXChanged() { Qt.callLater(pinned.measure) }
        function onLayoutChanged() { Qt.callLater(pinned.measure) }
    }

    ColumnLayout {
        id: content
        anchors { left: parent.left; right: parent.right }
        spacing: 0

        Kirigami.Separator { Layout.fillWidth: true }

        // The row itself.
        Item {
            id: row
            Layout.fillWidth: true
            implicitHeight: Math.max(Kirigami.Units.iconSizes.smallMedium, label.implicitHeight) + Kirigami.Units.smallSpacing * 2
            activeFocusOnTab: true

            Repeater {
                model: pinned.cells
                Label {
                    required property var modelData
                    visible: !pinned.nameCell || modelData.attribute !== pinned.nameCell.attribute
                    x: modelData.x + Kirigami.Units.smallSpacing
                    width: Math.max(0, modelData.width - Kirigami.Units.smallSpacing * 2)
                    anchors.verticalCenter: parent.verticalCenter
                    text: pinned.text(modelData.attribute, pinned.values[modelData.attribute])
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                }
            }
            RowLayout {
                id: label
                x: (pinned.nameCell ? pinned.nameCell.x : 0) + Kirigami.Units.largeSpacing
                width: Math.max(0, (pinned.nameCell ? pinned.nameCell.width : pinned.width) - Kirigami.Units.largeSpacing)
                anchors.verticalCenter: parent.verticalCenter
                spacing: Kirigami.Units.smallSpacing
                Kirigami.Icon {
                    Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
                    Layout.preferredHeight: Layout.preferredWidth
                    source: pinned.icon
                    animated: false
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Label {
                        objectName: "pinnedTitle"
                        Layout.fillWidth: true
                        text: pinned.title
                        elide: Text.ElideRight
                    }
                    Label {
                        Layout.fillWidth: true
                        text: pinned.subtitle
                        elide: Text.ElideRight
                        font: Kirigami.Theme.smallFont
                        color: Kirigami.Theme.disabledTextColor
                    }
                }
                Kirigami.Icon {
                    Layout.preferredWidth: Kirigami.Units.iconSizes.small
                    Layout.preferredHeight: Layout.preferredWidth
                    source: pinned.expanded ? "arrow-up" : "arrow-down"
                    animated: false
                }
            }
            HoverHandler { id: hover }
            Rectangle {
                anchors.fill: parent
                z: -1
                color: Kirigami.Theme.highlightColor
                opacity: hover.hovered || row.activeFocus ? 0.12 : 0
            }
            TapHandler { onTapped: pinned.expanded = !pinned.expanded }
            Accessible.role: Accessible.Button
            Accessible.name: pinned.expanded ? i18nd("monet", "Hide what's in %1", pinned.title) : i18nd("monet", "Show what's in %1", pinned.title)
            Accessible.onPressAction: pinned.expanded = !pinned.expanded
            Keys.onSpacePressed: pinned.expanded = !pinned.expanded
            Keys.onReturnPressed: pinned.expanded = !pinned.expanded
        }

        // Opened: its busiest processes, with their CPU under the CPU column.
        Repeater {
            model: pinned.expanded ? pinned.busiest : []
            Item {
                required property var modelData
                Layout.fillWidth: true
                implicitHeight: processName.implicitHeight + Kirigami.Units.smallSpacing
                Label {
                    id: processName
                    x: pinned.indent
                    width: Math.max(0, (pinned.nameCell ? pinned.nameCell.x + pinned.nameCell.width : pinned.width) - x)
                    text: modelData.name
                    elide: Text.ElideRight
                    color: Kirigami.Theme.disabledTextColor
                }
                Label {
                    visible: !!pinned.cpuCell
                    x: pinned.cpuCell ? pinned.cpuCell.x + Kirigami.Units.smallSpacing : 0
                    width: pinned.cpuCell ? Math.max(0, pinned.cpuCell.width - Kirigami.Units.smallSpacing * 2) : 0
                    horizontalAlignment: Text.AlignHCenter
                    text: pinned.text("usage", modelData.usage)
                    color: Kirigami.Theme.disabledTextColor
                }
            }
        }
        Label {
            Layout.fillWidth: true
            Layout.leftMargin: pinned.indent
            Layout.bottomMargin: Kirigami.Units.smallSpacing
            visible: pinned.expanded && pinned.busiest.length === 0
            text: i18nd("monet", "Nothing busy right now.")
            color: Kirigami.Theme.disabledTextColor
        }
    }
}
