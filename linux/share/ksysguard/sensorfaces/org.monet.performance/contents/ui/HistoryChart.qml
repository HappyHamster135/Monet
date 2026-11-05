// Native chart rendering and KDE's sensor model; only the selected resource is sampled.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.ksysguard.sensors as Sensors
import org.kde.ksysguard.formatter as Formatter
import org.kde.quickcharts as Charts
import org.kde.quickcharts.controls as ChartControls

ColumnLayout {
    id: history
    objectName: "historyChart"
    property var sensorIds: []
    property var labels: []
    property var colors: ["#357F72", "#9275A5"]
    property bool percentage: true
    property bool paused: false
    readonly property bool ready: sensorsModel.ready && sensorIds.length > 0
    readonly property int sampleCount: readings.samples.length
    readonly property var firstValues: sampleCount === 1 ? readings.samples[0].values : []
    spacing: 6

    // Start with the readings we have. Keep a bounded, shared timeline so paired
    // network/disk series never acquire different lengths or invented zeroes.
    HistoryBuffer { id: readings; objectName: "performanceHistory" }
    onSensorIdsChanged: readings.clear()
    onPausedChanged: { if (!paused) readings.clear() }
    function sample() {
        if (!ready || paused) return
        const values = sensorIds.map((_, column) =>
            sensorsModel.data(sensorsModel.index(0, column), Sensors.SensorDataModel.Value))
        readings.append(values, Date.now())
    }
    Timer {
        interval: 1000
        repeat: true
        running: history.ready && !history.paused
        triggeredOnStart: true
        onTriggered: history.sample()
    }
    Connections {
        target: sensorsModel
        // Metadata can arrive before the first value. Show that first real
        // reading immediately, then collect at the regular one-second cadence.
        function onDataChanged() { if (!history.sampleCount) history.sample() }
    }

    RowLayout {
        Layout.fillWidth: true
        Repeater {
            model: history.labels
            RowLayout {
                required property int index
                required property string modelData
                spacing: 6
                Rectangle { width: 8; height: 8; radius: 2; color: history.colors[index % history.colors.length] }
                QQC2.Label { text: modelData; font.pixelSize: 12 }
            }
        }
        Item { Layout.fillWidth: true }
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        spacing: 8
        ChartControls.AxisLabels {
            Layout.fillHeight: true
            Layout.preferredWidth: history.percentage ? 38 : 66
            direction: ChartControls.AxisLabels.VerticalBottomTop
            delegate: QQC2.Label {
                anchors.right: parent.right
                font.pixelSize: 11
                color: Kirigami.Theme.disabledTextColor
                text: Formatter.Formatter.formatValueShowNull(ChartControls.AxisLabels.label, history.percentage
                    ? Formatter.Units.UnitPercent : (sensorsModel.ready ? sensorsModel.headerData(0, Qt.Horizontal, Sensors.SensorDataModel.Unit) : Formatter.Units.UnitByteRate))
            }
            source: Charts.ChartAxisSource { chart: plot; axis: Charts.ChartAxisSource.YAxis; itemCount: 3 }
        }
        Charts.LineChart {
            id: plot
            objectName: "performancePlot"
            Layout.fillWidth: true
            Layout.fillHeight: true
            direction: Charts.XYChart.ZeroAtEnd
            lineWidth: history.sampleCount > 1 ? 2 : 0
            fillOpacity: history.sampleCount > 1 ? 0.08 : 0
            interpolate: false
            // QuickCharts' upper bound is exclusive. Two readings already fill
            // the graph; a single reading is shown as a point at "Now".
            xRange { from: 0; to: Math.max(2, history.sampleCount); automatic: false }
            yRange { from: 0; to: history.percentage ? 100 : 1; automatic: !history.percentage }
            colorSource: Charts.ArraySource { array: history.colors }
            Repeater {
                model: history.sampleCount === 1 ? history.sensorIds.length : 0
                Rectangle {
                    required property int index
                    objectName: "firstHistoryPoint" + index
                    readonly property real value: history.firstValues[index] ?? 0
                    readonly property real ceiling: history.percentage ? 100
                        : (Math.max(0, ...history.firstValues) || 1)
                    width: 6; height: 6; radius: 3
                    x: plot.width - width / 2
                    y: plot.height * (1 - Math.min(1, value / ceiling)) - height / 2
                    color: history.colors[index % history.colors.length]
                }
            }
            ChartControls.GridLines {
                anchors.fill: parent
                z: -1
                chart: plot
                direction: ChartControls.GridLines.Vertical
                major.count: 5
                major.lineWidth: 1
                major.color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.10)
                minor.visible: false
            }
            QQC2.Label {
                anchors.centerIn: parent
                visible: history.sampleCount === 0
                text: i18nd("monet", "Waiting for sensor readings…")
                color: Kirigami.Theme.disabledTextColor
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: history.percentage ? 46 : 74
        QQC2.Label {
            objectName: "historyDuration"
            text: history.sampleCount > 1 ? i18nd("monet", "%1 s", readings.duration) : ""
            font.pixelSize: 11
            color: Kirigami.Theme.disabledTextColor
        }
        Item { Layout.fillWidth: true }
        QQC2.Label { text: history.paused ? i18nd("monet", "Paused") : i18nd("monet", "Now"); font.pixelSize: 11; color: Kirigami.Theme.disabledTextColor }
    }

    Sensors.SensorDataModel {
        id: sensorsModel
        objectName: "performanceData"
        sensors: history.sensorIds
        enabled: !history.paused
        updateRateLimit: 1000
    }
    Instantiator {
        model: history.sensorIds
        delegate: Charts.ArraySource {
            objectName: "historySeries" + index
            required property int index
            array: readings.samples.map(row => row.values[index]).reverse()
        }
        onObjectAdded: (index, object) => plot.insertValueSource(index, object)
        onObjectRemoved: (index, object) => plot.removeValueSource(object)
    }
}
