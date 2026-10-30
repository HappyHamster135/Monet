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
    spacing: 6

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
            lineWidth: 2
            fillOpacity: 0.08
            interpolate: false
            xRange { from: 0; to: 59; automatic: false }
            yRange { from: 0; to: history.percentage ? 100 : 1; automatic: !history.percentage }
            colorSource: Charts.ArraySource { array: history.colors }
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
                visible: !history.ready
                text: i18nd("monet", "Waiting for sensor readings…")
                color: Kirigami.Theme.disabledTextColor
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: history.percentage ? 46 : 74
        QQC2.Label { text: i18nd("monet", "60 seconds"); font.pixelSize: 11; color: Kirigami.Theme.disabledTextColor }
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
        delegate: Charts.HistoryProxySource {
            id: series
            objectName: "historySeries" + index
            required property int index
            source: Charts.ModelSource { model: sensorsModel; column: index; roleName: "Value" }
            // DoNotFill leaves uncollected history empty, rather than inventing zeros.
            fillMode: Charts.HistoryProxySource.DoNotFill
            maximumHistory: 60
            interval: history.ready && !history.paused ? 1000 : -1
            property var restart: Connections {
                target: history
                function onPausedChanged() { if (!history.paused) series.clear() }
            }
        }
        onObjectAdded: (index, object) => plot.insertValueSource(index, object)
        onObjectRemoved: (index, object) => plot.removeValueSource(object)
    }
}
