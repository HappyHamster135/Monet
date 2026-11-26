import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as K
import org.kde.ksysguard.sensors as Sensors

GridLayout {
    id: system
    columns: 2; rowSpacing: 7; columnSpacing: 7
    component Reading: Sensors.Sensor {
        updateRateLimit: 1600
        enabled: sensorId.length > 0 && system.enabled
        readonly property bool valid: enabled && status === Sensors.Sensor.Ready && value !== undefined && value !== null
        readonly property string shown: valid ? formattedValue : ""
    }
    Reading { id: cpu; sensorId: "cpu/all/usage" }
    Reading { id: clock; sensorId: "cpu/all/averageFrequency" }
    Reading { id: used; sensorId: "memory/physical/used" }
    Reading { id: total; sensorId: "memory/physical/total" }
    Reading { id: memory; sensorId: "memory/physical/usedPercent" }
    Reading { id: gpu0; sensorId: "gpu/gpu0/usage" }
    Reading { id: gpu1; sensorId: "gpu/gpu1/usage" }
    readonly property var gpu: gpu1.valid && (!gpu0.valid || gpu1.value > gpu0.value) ? gpu1 : gpu0
    Reading { id: gpuName; sensorId: system.gpu.valid ? system.gpu.sensorId.replace("/usage", "/name") : "" }
    Reading { id: down; sensorId: "network/all/download" }
    Reading { id: up; sensorId: "network/all/upload" }

    component Metric: Rectangle {
        id: card
        required property string title
        required property string glyph
        required property color tint
        required property string amount
        required property string detail
        property real percent: -1
        Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: 1; Layout.preferredHeight: 1
        radius: 15; color: "#232327"
        Accessible.role: Accessible.StaticText
        Accessible.name: [title, amount || i18n("Unavailable"), detail].filter(Boolean).join(" · ")
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 12; spacing: 3
            RowLayout {
                spacing: 6
                K.Icon { Layout.preferredWidth: 15; Layout.preferredHeight: 15; source: card.glyph; isMask: true; color: card.tint }
                Text { Layout.fillWidth: true; text: card.title; color: "#ededf2"; elide: Text.ElideRight; font.weight: Font.Medium }
            }
            Text {
                Layout.fillWidth: true; Layout.minimumWidth: 0; text: card.amount || i18n("Unavailable")
                textFormat: Text.PlainText; font.pixelSize: 24; font.weight: Font.DemiBold; font.features: ({"tnum": 1})
                color: card.amount ? "white" : "#ababaf"; elide: Text.ElideRight; fontSizeMode: Text.HorizontalFit; minimumPixelSize: 13
            }
            Text { Layout.fillWidth: true; Layout.minimumWidth: 0; text: card.detail; color: "#c0c0c8"; font.pixelSize: 12
                textFormat: Text.PlainText; elide: Text.ElideRight }
            Rectangle {
                visible: card.percent >= 0; Layout.fillWidth: true; implicitHeight: 3; radius: 1.5; color: "#414146"
                Rectangle { width: parent.width * Math.max(0,Math.min(1,card.percent / 100)); height: parent.height; radius: 1.5; color: card.tint }
            }
        }
    }
    Metric { title: i18n("CPU"); glyph: "cpu"; tint: "#88bdff"; amount: cpu.shown
        detail: clock.valid ? i18n("Average %1", clock.shown) : ""; percent: cpu.valid ? cpu.value : -1 }
    Metric { title: i18n("Memory"); glyph: "memory"; tint: "#bca2ff"; amount: memory.shown
        detail: used.valid && total.valid ? i18n("%1 of %2", used.shown, total.shown) : used.shown; percent: memory.valid ? memory.value : -1 }
    Metric { title: i18n("Graphics"); glyph: "video-display"; tint: "#8fdbaa"; amount: system.gpu.shown
        detail: gpuName.valid ? String(gpuName.value) : ""; percent: system.gpu.valid ? system.gpu.value : -1 }
    Metric { title: i18n("Network"); glyph: "network-connect"; tint: "#8cd8df"; amount: down.valid ? i18n("↓ %1", down.shown) : ""
        detail: up.valid ? i18n("Upload %1", up.shown) : "" }
}
