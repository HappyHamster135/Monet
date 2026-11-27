import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as C
import org.kde.ksysguard.sensors as Sensors

Item {
    id: system
    property int selected: -1
    readonly property bool editingEvent: selected >= 0
    function closeEditor() { selected = -1 }
    property var history: [[], [], [], []]
    GraphicsPolicy { id: gpuPolicy; monitorDedicatedGraphics: system.selected === 2 }
    readonly property var graphicsPolicy: gpuPolicy
    onEnabledChanged: if (!enabled) history = [[], [], [], []]
    onVisibleChanged: if (!visible) history = [[], [], [], []]
    readonly property var metrics: [
        {title:i18n("CPU"), glyph:"cpu", amount:cpu.shown, detail:clock.shown, value:cpu.valid ? Number(cpu.value) : null},
        {title:i18n("Memory"), glyph:"memory", amount:memory.shown, detail:used.valid && total.valid ? i18n("%1 of %2",used.shown,total.shown) : used.shown, value:memory.valid ? Number(memory.value) : null},
        {title:i18n("Graphics"), glyph:"display", amount:gpu.shown, detail:gpuName.valid ? String(gpuName.value) : "", value:gpu.valid ? Number(gpu.value) : null},
        {title:i18n("Network"), glyph:"network", amount:down.shown, detail:up.valid ? i18n("↑ %1",up.shown) : "", value:down.valid ? Number(down.value) : null}
    ]
    component Reading: Loader {
        id: reading
        required property string sensorId
        required property Item owner
        active: sensorId.length > 0 && owner.enabled && owner.visible && owner.graphicsPolicy.allows(sensorId)
        readonly property var value: item ? item.value : null
        readonly property bool valid: item !== null && item.status === Sensors.Sensor.Ready && value !== undefined && value !== null && Number.isFinite(Number(value))
        readonly property string shown: valid ? item.formattedValue : ""
        sourceComponent: Component { Sensors.Sensor { sensorId: reading.sensorId; updateRateLimit: 1600 } }
    }
    Reading { id: cpu; owner: system; sensorId: "cpu/all/usage" }
    Reading { id: clock; owner: system; sensorId: "cpu/all/averageFrequency" }
    Reading { id: used; owner: system; sensorId: "memory/physical/used" }
    Reading { id: total; owner: system; sensorId: "memory/physical/total" }
    Reading { id: memory; owner: system; sensorId: "memory/physical/usedPercent" }
    Reading { id: gpu0; owner: system; sensorId: "gpu/gpu0/usage" }
    Reading { id: gpu1; owner: system; sensorId: "gpu/gpu1/usage" }
    readonly property var gpu: gpu1.valid && (!gpu0.valid || gpu1.value > gpu0.value) ? gpu1 : gpu0
    // The name is textual, unlike the sampled metrics.
    Sensors.Sensor { id: gpuName; sensorId: system.gpu.valid ? system.gpu.sensorId.replace("/usage", "/name") : ""
        enabled: !!sensorId && system.enabled && system.visible
        readonly property bool valid: enabled && status === Sensors.Sensor.Ready && value !== undefined }
    Reading { id: down; owner: system; sensorId: "network/all/download" }
    Reading { id: up; owner: system; sensorId: "network/all/upload" }
    Timer {
        interval: 1600; repeat: true; running: system.visible && system.enabled
        onTriggered: system.history = system.metrics.map((m,i) => system.history[i].concat([m.value]).slice(-60))
    }
    GridLayout {
        anchors.fill: parent; visible: system.selected < 0
        columns: 2; rowSpacing: 8; columnSpacing: 8
        Repeater {
            model: system.metrics
            C.AbstractButton {
                id: card
                required property int index
                required property var modelData
                objectName: "notchMetric-" + index
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: 1; Layout.preferredHeight: 1
                padding: 12; hoverEnabled: true
                Accessible.name: [modelData.title, modelData.amount || i18n("Unavailable"), modelData.detail].filter(Boolean).join(" · ")
                Accessible.description: i18n("Show live history")
                onClicked: system.selected = index
                background: Rectangle { radius: 14; color: card.hovered ? "#272729" : "#19191c"; border.width: card.visualFocus ? 1 : 0; border.color: "#aaaab2" }
                contentItem: ColumnLayout {
                    spacing: 5
                    RowLayout {
                        IslandGlyph { source: card.modelData.glyph; color: "#a7a7af"; Layout.preferredWidth: 14; Layout.preferredHeight: 14 }
                        Text { Layout.fillWidth: true; text: card.modelData.title; color: "#aaaab2"; font.pixelSize: 11; elide: Text.ElideRight }
                        IslandGlyph { source: "forward"; color: "#66666e"; Layout.preferredWidth: 11; Layout.preferredHeight: 11 }
                    }
                    Text { Layout.fillWidth: true; text: card.modelData.amount || "—"; color: "#f5f5f7"; font.pixelSize: 23; font.weight: Font.DemiBold
                        font.features: ({"tnum":1}); fontSizeMode: Text.HorizontalFit; minimumPixelSize: 13; elide: Text.ElideRight }
                    Text { Layout.fillWidth: true; text: card.modelData.detail || (card.modelData.value === null ? i18n("Sensor unavailable") : i18n("Live usage"))
                        textFormat: Text.PlainText; color: "#9999a2"; font.pixelSize: 10; elide: Text.ElideRight }
                    Item { Layout.fillHeight: true; Layout.maximumHeight: 5 }
                    Rectangle {
                        Layout.fillWidth: true; implicitHeight: 3; radius: 1.5; color: "#333337"
                        visible: card.index !== 3 && card.modelData.value !== null
                        Rectangle { width: parent.width * Math.min(1,Math.max(0,card.modelData.value / 100)); height: 3; radius: 1.5
                            color: card.modelData.value >= 85 ? "#ffad53" : "#e3e3e8" }
                    }
                }
            }
        }
    }
    ColumnLayout {
        anchors.fill: parent; visible: system.selected >= 0; spacing: 10
        readonly property var metric: system.metrics[Math.max(0,system.selected)]
        RowLayout {
            IslandButton { objectName: "notchMetricBack"; plain: true; icon.name: "go-previous"; text: i18n("All metrics"); onClicked: system.closeEditor() }
            Text { Layout.fillWidth: true; text: parent.parent.metric.title; font.pixelSize: 13; font.weight: Font.DemiBold; color: "white" }
            Text { text: i18n("LIVE"); font.pixelSize: 9; color: "#ffad53" }
        }
        RowLayout {
            Text { text: parent.parent.metric.amount || "—"; color: "white"; font.pixelSize: 30; font.weight: Font.Light }
            Text { Layout.fillWidth: true; text: parent.parent.metric.detail; textFormat: Text.PlainText; elide: Text.ElideRight; color: "#aaaab2"; font.pixelSize: 11 }
        }
        IslandChart {
            objectName: "notchMetricChart"
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 40
            samples: system.history[Math.max(0,system.selected)]
            ceiling: system.selected === 3 ? Math.max(1,...samples.filter(v => v !== null)) : 100
        }
        RowLayout {
            Text { text: i18n("Last 96 seconds"); color: "#888891"; font.pixelSize: 10 }
            Item { Layout.fillWidth: true }
            Text { text: parent.parent.metric.value === null ? i18n("Sensor unavailable") : system.selected === 3 ? i18n("Download rate · auto scale") : "0–100%"; color: "#aaaab2"; font.pixelSize: 10 }
        }
    }
}
