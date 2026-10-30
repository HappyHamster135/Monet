import QtQuick
import QtQuick.Window
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as P5Support
import "../../../org.monet.performance/contents/ui" as Performance
import "../../../org.monet.hardware/contents/ui" as Hardware

ColumnLayout {
    id: details
    objectName: "systemDetails"
    property int section: 0
    property var snapshot: ({})
    property bool busy: false
    property int requestSerial: 0
    property string error: ""
    property string helper: "@LIBEXECDIR@/monet-system-info"
    // Also injectable by native fixtures; static identification never needs sensors.
    property var sensorIds: catalogLoader.item ? catalogLoader.item.sensorIds : []
    Performance.WindowActivity { id: activity; item: details }
    readonly property bool sampling: activity.active
    readonly property var sections: [i18nd("monet", "Hardware overview"), i18nd("monet", "CPU cores"),
        i18nd("monet", "Network interfaces"), i18nd("monet", "Drives and filesystems"), i18nd("monet", "Sensors")]
    spacing: 12

    function refresh() {
        if (busy) return
        busy = true
        error = ""
        reader.connectSource("'" + helper.replace(/'/g, "'\\''") + "' # system-refresh-" + (++requestSerial))
    }
    Component.onCompleted: if (sampling) refresh()
    onSamplingChanged: if (sampling && !snapshot.version && !busy && !error) refresh()
    P5Support.DataSource {
        id: reader
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source)
            details.busy = false
            try {
                if (data["exit code"] !== 0) throw new Error("helper failed")
                const result = JSON.parse(data.stdout)
                if (result.version !== 1 || !result.cpu || !result.system || !result.memory
                        || !Array.isArray(result.cpu.topology) || !Array.isArray(result.cpu.caches)
                        || !Array.isArray(result.graphics) || !Array.isArray(result.networks)
                        || !Array.isArray(result.disks)) throw new Error("invalid snapshot")
                details.snapshot = result
            } catch (_) {
                details.error = i18nd("monet", "Could not read system details. Try refreshing.")
            }
        }
    }
    function value(v) { return v === undefined || v === null || v === "" ? i18nd("monet", "Not reported") : String(v) }
    function bytes(v) {
        if (typeof v !== "number" || v < 0) return value(null)
        const units = ["B", "KiB", "MiB", "GiB", "TiB"]
        let unit = 0
        while (v >= 1024 && unit < units.length - 1) { v /= 1024; ++unit }
        return v.toLocaleString(Qt.locale(), "f", unit ? 1 : 0) + " " + units[unit]
    }
    readonly property var rows: {
        const result = []
        function group(title) { result.push({heading: title}) }
        function row(label, val) { result.push({label: label, value: details.value(val)}) }
        const s = snapshot.system || {}, cpu = snapshot.cpu || {}, mem = snapshot.memory || {}
        if (!snapshot.version) return result
        group(i18nd("monet", "System"))
        row(i18nd("monet", "Operating system"), s.os)
        row(i18nd("monet", "Kernel"), s.kernel)
        row(i18nd("monet", "Architecture"), s.architecture)
        row(i18nd("monet", "Computer"), [s.vendor, s.model].filter(Boolean).join(" · "))
        row(i18nd("monet", "Firmware"), [s.firmware, s.firmwareDate].filter(Boolean).join(" · "))
        group(i18nd("monet", "Processor"))
        row(i18nd("monet", "Model"), (cpu.models || []).join(" · "))
        row(i18nd("monet", "Sockets"), cpu.sockets)
        row(i18nd("monet", "Physical cores"), cpu.cores)
        row(i18nd("monet", "Logical processors"), cpu.logical)
        row(i18nd("monet", "Online processors"), cpu.online)
        row(i18nd("monet", "Maximum supported clock"), cpu.maxMHz ? (cpu.maxMHz / 1000).toLocaleString(Qt.locale(), "f", 2) + " GHz" : null)
        row(i18nd("monet", "Virtualization capability"), cpu.virtualization)
        for (const c of cpu.caches || []) {
            const kind = c.kind === "Data" ? i18nd("monet", "Data") : c.kind === "Instruction" ? i18nd("monet", "Instruction") : i18nd("monet", "Unified")
            row(i18nd("monet", "L%1 cache", c.level) + " · " + kind, bytes(c.bytes) + " · " + i18nd("monet", "Instances: %1", c.instances))
        }
        group(i18nd("monet", "Memory"))
        row(i18nd("monet", "Usable physical memory"), bytes(mem.MemTotal))
        row(i18nd("monet", "Configured swap"), bytes(mem.SwapTotal))
        for (const gpu of snapshot.graphics) {
            group(i18nd("monet", "Graphics") + " · " + gpu.id)
            row(i18nd("monet", "Model"), gpu.model)
            row(i18nd("monet", "PCI device"), gpu.pci)
            row(i18nd("monet", "Hardware ID"), gpu.vendor + ":" + gpu.product)
            row(i18nd("monet", "Kernel driver"), gpu.driver)
            row(i18nd("monet", "Driver version"), gpu.driverVersion || (gpu.driver ? i18nd("monet", "Not separately reported · kernel %1", s.kernel) : ""))
        }
        for (const net of snapshot.networks) {
            group(i18nd("monet", "Network") + " · " + net.id)
            row(i18nd("monet", "Kernel driver"), net.driver)
            row(i18nd("monet", "Driver version"), net.driverVersion || (net.driver ? i18nd("monet", "Not separately reported · kernel %1", s.kernel) : ""))
            row(i18nd("monet", "Link speed (snapshot)"), net.speedMbps ? net.speedMbps + " Mb/s" : null)
            row(i18nd("monet", "MTU"), net.mtu)
        }
        for (const disk of snapshot.disks) {
            group(i18nd("monet", "Storage") + " · " + disk.id)
            row(i18nd("monet", "Model"), [disk.vendor, disk.model].filter(Boolean).join(" "))
            row(i18nd("monet", "Firmware"), disk.firmware)
            row(i18nd("monet", "Physical capacity"), bytes(disk.bytes))
            row(i18nd("monet", "Media"), disk.rotational === true ? i18nd("monet", "Rotating disk")
                : disk.rotational === false ? i18nd("monet", "Solid-state storage") : null)
        }
        return result
    }
    RowLayout {
        Layout.fillWidth: true
        QQC2.ComboBox {
            objectName: "systemSection"
            Layout.fillWidth: true
            model: details.sections
            currentIndex: details.section
            onActivated: details.section = currentIndex
            Accessible.name: i18nd("monet", "System details section")
        }
        QQC2.Button {
            objectName: "refreshSystemDetails"
            text: i18nd("monet", "Refresh hardware")
            icon.name: "view-refresh"
            enabled: !details.busy
            onClicked: { details.refresh(); if (catalogLoader.item) catalogLoader.item.discover() }
        }
    }
    QQC2.Label {
        Layout.fillWidth: true
        visible: details.section === 0
        text: details.busy ? i18nd("monet", "Reading system details…") : details.error || i18nd("monet", "Hardware identity is read on demand. Refresh after changing devices. Select text to copy it.")
        wrapMode: Text.Wrap
    }
    QQC2.ScrollView {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: 240
        visible: details.section === 0
        clip: true
        ListView {
            id: overview
            objectName: "systemOverviewList"
            model: details.rows
            reuseItems: true
            spacing: 2
            delegate: ColumnLayout {
                required property var modelData
                width: overview.width
                QQC2.Label {
                    Layout.fillWidth: true
                    Layout.topMargin: 12
                    Layout.bottomMargin: 4
                    visible: !!modelData.heading
                    text: modelData.heading || ""
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.2
                    font.weight: Font.DemiBold
                }
                RowLayout {
                    Layout.fillWidth: true
                    visible: !modelData.heading
                    QQC2.Label {
                        Layout.preferredWidth: Math.min(230, overview.width * 0.4)
                        Layout.alignment: Qt.AlignTop
                        text: modelData.label || ""
                        color: Kirigami.Theme.disabledTextColor
                        wrapMode: Text.Wrap
                    }
                    TextEdit {
                        Layout.fillWidth: true
                        text: modelData.value || ""
                        color: Kirigami.Theme.textColor
                        selectionColor: Kirigami.Theme.highlightColor
                        selectedTextColor: Kirigami.Theme.highlightedTextColor
                        font: Kirigami.Theme.defaultFont
                        textFormat: TextEdit.PlainText
                        readOnly: true
                        selectByMouse: true
                        wrapMode: TextEdit.Wrap
                        Accessible.name: (modelData.label || "") + ": " + text
                    }
                }
            }
        }
    }
    Loader {
        id: catalogLoader
        // Overview has no sensor discovery or sampling overhead.
        active: details.section > 0
        visible: false
        sourceComponent: Performance.SensorCatalog {}
    }
    Loader {
        Layout.fillWidth: true
        Layout.fillHeight: true
        active: details.section > 0 && details.section < 4
        visible: active
        sourceComponent: Performance.DeviceDetails {
            availableSensors: details.sensorIds
            category: details.section - 1
            showCategorySelector: false
            topology: details.snapshot.cpu ? details.snapshot.cpu.topology : []
            sampling: details.sampling
        }
    }
    Loader {
        Layout.fillWidth: true
        Layout.fillHeight: true
        active: details.section === 4
        visible: active
        sourceComponent: Hardware.SensorList {
            sensorIds: details.sensorIds.filter(id => id === "cpu/all/maximumTemperature"
                || /\/temperature$/.test(id) || /\/fan[0-9]+$/.test(id))
            sampling: details.sampling
        }
    }
}
