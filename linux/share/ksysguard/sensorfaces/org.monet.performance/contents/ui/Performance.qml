import QtQuick
import QtQuick.Window
import QtQuick.Controls as QQC2
import QtQuick.Templates as T
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.ksysguard.sensors as Sensors
import org.kde.plasma.plasma5support as P5Support

ColumnLayout {
    id: dashboard
    objectName: "monetPerformance"
    property var availableSensors: []
    property int section: 0
    property bool paused: false
    property int graphicsIndex: 0
    // A minimized QQuickWindow still leaves its items visible. Stop subscriptions
    // explicitly; an unfocused but visible monitor should continue updating.
    WindowActivity { id: activity; item: dashboard }
    readonly property bool monitoringActive: activity.active
    readonly property bool dark: Kirigami.Theme.backgroundColor.hslLightness < 0.5
    readonly property color accent: dark ? "#62B6A6" : "#357F72"
    // Each graphics device, not KDE's sum of them all (gpu/all), which has no name of its own.
    readonly property var graphics: Array.from(availableSensors).filter(id => /^gpu\/(?!all\/)[^/]+\/usage$/.test(id))
    readonly property string gpu: graphics.length ? graphics[Math.min(graphicsIndex, graphics.length - 1)].replace(/\/usage$/, "") : ""
    readonly property var headings: [i18nd("monet", "CPU"), i18nd("monet", "Memory"), i18nd("monet", "Graphics"),
        i18nd("monet", "Network"), i18nd("monet", "Storage")]
    readonly property var descriptions: [i18nd("monet", "Processor workload and temperature"), i18nd("monet", "Physical memory and swap"),
        i18nd("monet", "Graphics workload and video memory"), i18nd("monet", "Traffic across all connections"),
        i18nd("monet", "Activity and space on mounted drives")]
    readonly property var chartIds: section === 0 ? ["cpu/all/usage"] : section === 1 ? ["memory/physical/usedPercent"]
        : section === 2 ? (gpu ? [gpu + "/usage"] : []) : section === 3 ? ["network/all/download", "network/all/upload"]
        : section === 4 ? ["disk/all/read", "disk/all/write"] : []
    readonly property var chartLabels: section <= 2 ? [i18nd("monet", "Utilisation")]
        : section === 3 ? [i18nd("monet", "Download"), i18nd("monet", "Upload")] : [i18nd("monet", "Read"), i18nd("monet", "Write")]
    readonly property var details: {
        if (section === 0) return [
            {label: i18nd("monet", "Utilisation"), sensor: "cpu/all/usage"},
            {label: i18nd("monet", "Average frequency"), sensor: "cpu/all/averageFrequency"},
            {label: i18nd("monet", "Temperature"), sensor: "cpu/all/maximumTemperature", positive: true},
            {label: i18nd("monet", "Logical processors"), sensor: "cpu/all/coreCount"},
            {label: i18nd("monet", "Sockets"), sensor: "cpu/all/cpuCount"},
            {label: i18nd("monet", "Waiting for disk"), sensor: "cpu/all/wait"}]
        if (section === 1) return [
            {label: i18nd("monet", "In use"), sensor: "memory/physical/used"},
            {label: i18nd("monet", "Free"), sensor: "memory/physical/free"},
            {label: i18nd("monet", "Total memory"), sensor: "memory/physical/total"},
            {label: i18nd("monet", "Cached"), sensor: "memory/physical/cache"},
            {label: i18nd("monet", "Swap in use"), sensor: "memory/swap/used"},
            {label: i18nd("monet", "Total swap"), sensor: "memory/swap/total"},
            {label: i18nd("monet", "Application memory"), sensor: "memory/physical/application"},
            {label: i18nd("monet", "Buffers"), sensor: "memory/physical/buffer"}]
        if (section === 2) return gpu ? [
            {label: i18nd("monet", "Utilisation"), sensor: gpu + "/usage"},
            {label: i18nd("monet", "Temperature"), sensor: gpu + "/temperature", positive: true},
            {label: i18nd("monet", "Power"), sensor: gpu + "/power", positive: true},
            {label: i18nd("monet", "Video memory used"), sensor: gpu + "/usedVram", capacity: gpu + "/totalVram"},
            {label: i18nd("monet", "Video memory total"), sensor: gpu + "/totalVram", positive: true},
            {label: i18nd("monet", "Core frequency"), sensor: gpu + "/coreFrequency", positive: true}] : []
        if (section === 3) return [
            {label: i18nd("monet", "Download speed"), sensor: "network/all/download"},
            {label: i18nd("monet", "Upload speed"), sensor: "network/all/upload"},
            {label: i18nd("monet", "Downloaded"), sensor: "network/all/totalDownload"},
            {label: i18nd("monet", "Uploaded"), sensor: "network/all/totalUpload"}]
        if (section === 4) return [
            {label: i18nd("monet", "Read speed"), sensor: "disk/all/read"},
            {label: i18nd("monet", "Write speed"), sensor: "disk/all/write"},
            {label: i18nd("monet", "Free space"), sensor: "disk/all/free"},
            {label: i18nd("monet", "Used space"), sensor: "disk/all/used"},
            {label: i18nd("monet", "Total space"), sensor: "disk/all/total"}]
        return []
    }
    SummaryReadings { id: totals; sampling: dashboard.monitoringActive && !dashboard.paused; gpu: dashboard.gpu }
    readonly property var tabReadings: totals.values.map((value, index) => index === 3 ? value.replace("  ", "\n") : index === 4 ? value.replace(" · ", "\n") : value)
    readonly property var choices: headings.map((label, index) => label + (tabReadings[index] ? " · " + tabReadings[index] : ""))
    onSectionChanged: paused = false
    onGraphicsIndexChanged: paused = false
    onGraphicsChanged: graphicsIndex = Math.max(0, Math.min(graphicsIndex, graphics.length - 1))

    // KDE calls a graphics device it finds no name for "GPU 2", and that is usually the graphics
    // built into the processor. Monet's helper names them as KDE counts them (gpu0, gpu1, ...).
    property string helper: "@LIBEXECDIR@/monet-graphics-use"
    property var graphicsNamed: []
    property bool graphicsAsked: false
    readonly property bool graphicsShown: section === 2 && monitoringActive
    onGraphicsShownChanged: if (graphicsShown) askGraphicsNames()
    Component.onCompleted: if (graphicsShown) askGraphicsNames()
    function askGraphicsNames() {
        if (graphicsAsked) return
        graphicsAsked = true
        namer.connectSource("'" + helper.replace(/'/g, "'\\''") + "' --devices")
    }
    P5Support.DataSource {
        id: namer
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source)
            try {
                const result = JSON.parse(data.stdout)
                if (data["exit code"] === 0 && result.version === 1 && Array.isArray(result.devices))
                    dashboard.graphicsNamed = result.devices
            } catch (_) {}
        }
    }
    function graphicsLabel(index, kdeName) {
        const id = String(graphics[index] || "").split("/")[1] || ""
        const said = String(kdeName || "")
        const ours = graphicsNamed.length === graphics.length ? graphicsNamed.find(device => device.id === id) : undefined
        // KDE's own name where it found one that says who made it (NVIDIA's comes from the driver).
        const maker = /nvidia|geforce|quadro/i.test(said) ? "NVIDIA" : /\bamd\b|radeon/i.test(said) ? "AMD"
            : /intel/i.test(said) ? "Intel" : ""
        if (ours && maker && maker !== ours.maker) return said  // counted another way: KDE's alone
        const name = maker ? said : ours ? ours.name : said
        if (!name) return i18nd("monet", "Graphics device %1", index + 1)
        return ours && ours.builtIn ? i18nd("monet", "%1 (built into the processor)", name) : name
    }
    spacing: 16

    QQC2.TabBar {
        id: tabs
        objectName: "resourceTabs"
        Layout.fillWidth: true
        implicitWidth: 620
        visible: dashboard.width >= 620
        currentIndex: dashboard.section
        onCurrentIndexChanged: dashboard.section = currentIndex
        Repeater {
            model: dashboard.headings
            T.TabButton {
                id: tab
                required property int index
                required property string modelData
                objectName: "resourceTab" + index
                width: tabs.width / dashboard.headings.length
                implicitHeight: Math.max(78, Kirigami.Theme.defaultFont.pointSize * 4 + 26)
                padding: 8
                hoverEnabled: true
                focusPolicy: Qt.StrongFocus
                Keys.onLeftPressed: tabs.decrementCurrentIndex()
                Keys.onRightPressed: tabs.incrementCurrentIndex()
                text: modelData
                background: Rectangle {
                    radius: 8
                    color: tab.checked || tab.hovered ? Kirigami.Theme.backgroundColor : "transparent"
                    border.width: tab.checked || tab.activeFocus ? 1 : 0
                    border.color: tab.activeFocus ? dashboard.accent : Kirigami.Theme.disabledTextColor
                }
                contentItem: Column {
                    spacing: 4
                    QQC2.Label { width: parent.width; text: modelData; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight }
                    QQC2.Label {
                        width: parent.width
                        text: dashboard.tabReadings[index] || " "
                        horizontalAlignment: Text.AlignHCenter
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                    }
                }
                Accessible.name: dashboard.choices[index]
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.text: dashboard.choices[index]
            }
        }
    }
    QQC2.ComboBox {
        objectName: "resourceSelector"
        Layout.fillWidth: true
        visible: dashboard.width < 620
        model: dashboard.choices
        currentIndex: dashboard.section
        onActivated: dashboard.section = currentIndex
        Accessible.name: i18nd("monet", "Resource")
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: 12
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4
            QQC2.Label { text: dashboard.headings[dashboard.section]; font.pixelSize: 26; font.weight: Font.DemiBold }
            QQC2.Label {
                Layout.fillWidth: true
                text: dashboard.descriptions[dashboard.section]
                color: Kirigami.Theme.disabledTextColor
                wrapMode: Text.Wrap
            }
        }
        QQC2.Button {
            objectName: "pausePerformance"
            visible: dashboard.section < 5
            text: dashboard.paused ? i18nd("monet", "Resume") : i18nd("monet", "Pause")
            icon.name: dashboard.paused ? "media-playback-start" : "media-playback-pause"
            onClicked: dashboard.paused = !dashboard.paused
            Accessible.description: i18nd("monet", "Pause the graph and readings for this resource")
        }
    }
    RowLayout {
        Layout.fillWidth: true
        visible: dashboard.section === 2 && dashboard.graphics.length > 0
        QQC2.Label { text: i18nd("monet", "Device") }
        QQC2.ComboBox {
            id: graphicsChoice
            objectName: "graphicsDevice"
            Layout.fillWidth: true
            model: dashboard.graphics
            currentIndex: dashboard.graphicsIndex
            onActivated: dashboard.graphicsIndex = currentIndex
            displayText: dashboard.graphicsLabel(currentIndex, gpuName.value)
            delegate: QQC2.ItemDelegate {
                id: gpuDelegate
                required property int index
                required property string modelData
                width: parent ? parent.width : implicitWidth
                text: dashboard.graphicsLabel(index, deviceName.value)
                Sensors.Sensor {
                    id: deviceName
                    sensorId: gpuDelegate.modelData.replace(/\/usage$/, "/name")
                    enabled: dashboard.monitoringActive && dashboard.section === 2 && graphicsChoice.popup.visible
                }
            }
            Sensors.Sensor {
                id: gpuName
                sensorId: dashboard.gpu ? dashboard.gpu + "/name" : ""
                enabled: dashboard.monitoringActive && dashboard.section === 2
            }
        }
    }
    HistoryChart {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: 150
        Layout.preferredHeight: 220
        visible: dashboard.section < 5 && (dashboard.section !== 2 || dashboard.gpu !== "")
        sensorIds: visible ? dashboard.chartIds : []
        labels: dashboard.chartLabels
        colors: [dashboard.accent, dashboard.dark ? "#BDA2D0" : "#86639C"]
        percentage: dashboard.section <= 2
        paused: dashboard.paused || !dashboard.monitoringActive
    }
    Kirigami.Separator { Layout.fillWidth: true; visible: dashboard.section < 5 }
    GridLayout {
        Layout.fillWidth: true
        columns: dashboard.width >= 620 ? 3 : 2
        rowSpacing: 16
        columnSpacing: 24
        visible: dashboard.section < 5
        Repeater {
            model: dashboard.details
            Metric {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                label: modelData.label
                sensorId: modelData.sensor
                positiveOnly: modelData.positive || false
                capacityId: modelData.capacity || ""
                paused: dashboard.paused || !dashboard.monitoringActive
            }
        }
    }
    QQC2.Label {
        Layout.fillWidth: true
        visible: dashboard.section === 2 && dashboard.graphics.length === 0
        text: i18nd("monet", "No supported graphics device was found.")
        wrapMode: Text.Wrap
    }
    // Which apps the graphics card is working for, measured only while this is in view.
    Kirigami.Separator { Layout.fillWidth: true; visible: graphicsApps.visible }
    GraphicsApps {
        id: graphicsApps
        Layout.fillWidth: true
        visible: dashboard.section === 2
        sampling: visible && dashboard.monitoringActive && !dashboard.paused
        accent: dashboard.accent
    }
    QQC2.Label {
        Layout.fillWidth: true
        color: Kirigami.Theme.disabledTextColor
        wrapMode: Text.Wrap
        font.pointSize: Kirigami.Theme.smallFont.pointSize
        text: dashboard.paused ? i18nd("monet", "Paused — readings are frozen. Resume to collect a new history.")
            : i18nd("monet", "Live · updates every second")
    }
}
