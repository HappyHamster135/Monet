import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

MouseArea {
    id: strip
    required property var readings
    required property string style
    required property bool vertical
    required property bool sampling
    required property var power
    signal pressedReading()
    readonly property bool thin: !vertical && height < metrics.height * 2 + 5
    readonly property real rowHeight: Math.ceil(metrics.height * 2) + 7
    // Fixed widths for changing numbers keep adjacent task icons in place.
    Layout.minimumWidth: vertical ? -1 : Math.max(24, content.implicitWidth + 4)
    Layout.preferredWidth: Layout.minimumWidth
    Layout.maximumWidth: vertical ? Infinity : Layout.minimumWidth
    Layout.minimumHeight: vertical ? Math.max(24, content.implicitHeight + 4) : -1
    Layout.preferredHeight: Layout.minimumHeight
    Layout.maximumHeight: vertical ? Layout.minimumHeight : Infinity
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: i18nd("monet", "System")
    readonly property string summary: {
        const lines = []
        for (let i = 0; i < cells.count; ++i) {
            const cell = cells.itemAt(i)
            if (cell) lines.push(cell.description)
        }
        return lines.join("\n")
    }
    Accessible.description: summary
    Accessible.onPressAction: pressedReading()
    Keys.onSpacePressed: pressedReading()
    Keys.onReturnPressed: pressedReading()
    onClicked: pressedReading()

    ReadingNames { id: readingNames }
    FontMetrics { id: metrics; font: Kirigami.Theme.smallFont }
    Grid {
        id: content
        anchors.centerIn: parent
        columns: strip.vertical ? 1 : Math.max(1, cells.count)
        spacing: 2
        Repeater {
            id: cells
            model: strip.readings
            ReadingCell {
                required property string modelData
                reading: modelData; names: readingNames
                style: strip.style; power: strip.power; sampling: strip.sampling
                inlineLabel: strip.thin
                width: strip.vertical ? Math.max(0, strip.width - 4) : (inlineLabel ? wideSlot : slotWidth)
                height: strip.vertical ? strip.rowHeight : strip.height
            }
        }
    }
    Kirigami.Icon {
        visible: cells.count === 0
        anchors.centerIn: parent
        width: 18; height: 18; source: "utilities-system-monitor"
    }
    Rectangle {
        anchors.fill: parent; radius: 4; color: "transparent"
        border.width: strip.activeFocus ? 2 : 0
        border.color: Kirigami.Theme.highlightColor
    }
}
