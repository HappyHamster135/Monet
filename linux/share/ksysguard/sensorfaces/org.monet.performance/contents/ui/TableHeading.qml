import QtQuick
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

Item {
    id: cell
    required property var model
    readonly property var header: TableView.view
    readonly property string title: header ? String(model[header.textRole] ?? "") : ""
    // KDE's horizontal header uses a one-column list model. Only the sorted
    // entry has a sort role, including when columns are reordered or mirrored.
    readonly property bool sorted: model.sort !== undefined && model.sort !== null
    readonly property real padding: Kirigami.Units.smallSpacing / 2
    readonly property real arrowSpace: sorted ? arrow.width + padding : 0
    implicitWidth: label.implicitWidth + arrowSpace + 2 * padding
    implicitHeight: Math.ceil(label.implicitHeight) + 2 * Kirigami.Units.smallSpacing
    clip: true

    Item {
        id: group
        anchors.centerIn: parent
        width: Math.max(0, Math.min(cell.width, cell.implicitWidth) - 2 * cell.padding)
        height: parent.height

        Controls.Label {
            id: label
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: Math.max(0, group.width - cell.arrowSpace)
            text: cell.title
            textFormat: Text.PlainText
            elide: Text.ElideRight
            maximumLineCount: 1
            Accessible.name: cell.title
        }
        Kirigami.Icon {
            id: arrow
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            visible: cell.sorted
            width: Kirigami.Units.iconSizes.sizeForLabels
            height: width
            source: cell.model.sort === Qt.AscendingOrder ? "arrow-up-symbolic" : "arrow-down-symbolic"
            Accessible.ignored: true
        }
    }

    HoverHandler { id: hover }
    Controls.ToolTip.visible: hover.hovered && label.truncated
    Controls.ToolTip.text: cell.title
    Controls.ToolTip.delay: Kirigami.Units.toolTipDelay
}
