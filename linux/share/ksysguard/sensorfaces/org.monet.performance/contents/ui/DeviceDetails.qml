import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.ksysguard.sensors as Sensors

ColumnLayout {
    id: details
    objectName: "deviceDetails"
    property var availableSensors: []
    property bool sampling: true
    property int category: 0
    property bool showCategorySelector: true
    property var topology: []
    readonly property var devices: availableSensors.filter(id => category === 0
        ? /^cpu\/cpu[0-9]+\/usage$/.test(id)
        : category === 1 ? /^network\/(?!all\/)[A-Za-z0-9_.:-]+\/download$/.test(id)
        : /^disk\/(?!all\/)[A-Za-z0-9_.:-]+\/read$/.test(id))
        .map(id => id.replace(/\/[^/]+$/, "")).sort((a, b) => details.category === 0
            ? Number(a.substring(7)) - Number(b.substring(7)) : a.localeCompare(b))
    spacing: 12
    QQC2.ComboBox {
        objectName: "detailCategory"
        visible: details.showCategorySelector
        Layout.fillWidth: true
        model: [i18nd("monet", "Logical processors"), i18nd("monet", "Network interfaces"), i18nd("monet", "Drives and filesystems")]
        currentIndex: details.category
        onActivated: details.category = currentIndex
        Accessible.name: i18nd("monet", "Hardware details")
    }
    QQC2.Label {
        Layout.fillWidth: true
        text: details.category === 0 ? i18nd("monet", "Each logical processor shows its own workload and current clock speed. Threads can share a physical core.")
            : details.category === 1 ? i18nd("monet", "Traffic and addresses for each connection.")
            : i18nd("monet", "Physical drives and mounted filesystems. Their totals can overlap; do not add them together.")
        wrapMode: Text.Wrap
        color: Kirigami.Theme.disabledTextColor
    }
    QQC2.ScrollView {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: 220
        clip: true
        ListView {
            id: list
            objectName: "hardwareDetailList"
            model: details.devices
            spacing: 8
            reuseItems: true
            delegate: Rectangle {
                id: device
                required property string modelData
                required property int index
                objectName: "hardwareDetail-" + modelData
                width: list.width
                height: body.implicitHeight + 24
                radius: 8
                color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.035)
                readonly property bool sampling: details.sampling && y + height > list.contentY && y < list.contentY + list.height
                readonly property var core: details.category === 0
                    ? details.topology.find(item => item.id === Number(device.modelData.replace("cpu/cpu", ""))) : null
                readonly property var fields: details.category === 0 ? [
                    [i18nd("monet", "Utilisation"), "usage"], [i18nd("monet", "Clock speed"), "frequency"],
                    [i18nd("monet", "User"), "user"], [i18nd("monet", "System"), "system"],
                    [i18nd("monet", "Waiting for disk"), "wait"], [i18nd("monet", "Temperature"), "temperature"]]
                    : details.category === 1 ? [
                    [i18nd("monet", "Download"), "download"], [i18nd("monet", "Upload"), "upload"],
                    [i18nd("monet", "IPv4 address"), "ipv4address"], [i18nd("monet", "IPv6 address"), "ipv6address"],
                    [i18nd("monet", "Downloaded"), "totalDownload"], [i18nd("monet", "Uploaded"), "totalUpload"]]
                    : [[i18nd("monet", "Read"), "read"], [i18nd("monet", "Write"), "write"],
                    [i18nd("monet", "Capacity"), "total"], [i18nd("monet", "Free space"), "free"]]
                Sensors.Sensor {
                    id: name
                    sensorId: device.modelData + (details.category === 1 ? "/network" : "/name")
                    enabled: device.sampling && details.availableSensors.includes(sensorId)
                    updateRateLimit: 1000
                }
                ColumnLayout {
                    id: body
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12 }
                    spacing: 12
                    QQC2.Label {
                        Layout.fillWidth: true
                        text: details.category === 0 ? i18nd("monet", "Logical processor %1", Number(device.modelData.replace("cpu/cpu", "")) + 1)
                            : (name.value || device.modelData)
                        font.weight: Font.DemiBold
                        wrapMode: Text.Wrap
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        visible: !!device.core
                        text: device.core ? i18nd("monet", "Linux CPU %1", device.core.id)
                            + (device.core.package !== null ? " · " + i18nd("monet", "Socket %1", device.core.package) : "")
                            + (device.core.core !== null ? " · " + i18nd("monet", "Physical core %1", device.core.core) : "")
                            + (device.core.siblings.length ? " · " + i18nd("monet", "Sibling CPUs: %1", device.core.siblings.join(", ")) : "") : ""
                        color: Kirigami.Theme.disabledTextColor
                        wrapMode: Text.Wrap
                    }
                    GridLayout {
                        Layout.fillWidth: true
                        columns: width >= 580 ? 3 : 2
                        columnSpacing: 16
                        rowSpacing: 12
                        Repeater {
                            model: device.fields
                            Metric {
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                label: modelData[0]
                                sensorId: device.modelData + "/" + modelData[1]
                                positiveOnly: modelData[1] === "temperature" || modelData[1] === "frequency"
                                allowText: modelData[1] === "ipv4address" || modelData[1] === "ipv6address"
                                paused: !device.sampling || !details.availableSensors.includes(sensorId)
                                compact: true
                            }
                        }
                    }
                }
            }
            QQC2.Label {
                anchors.centerIn: parent
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                visible: list.count === 0
                text: i18nd("monet", "No supported devices were found.")
            }
        }
    }
}
