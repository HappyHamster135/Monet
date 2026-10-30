import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

QQC2.ScrollView {
    id: root
    property var sensorIds: []
    property bool sampling: true
    function compareIds(a, b) {
        const left = a.match(/\d+|\D+/g) || []
        const right = b.match(/\d+|\D+/g) || []
        for (let i = 0; i < Math.min(left.length, right.length); ++i) {
            if (left[i] === right[i]) continue
            if (/^\d+$/.test(left[i]) && /^\d+$/.test(right[i])) {
                const difference = Number(left[i]) - Number(right[i])
                if (difference) return difference
            } else return left[i] < right[i] ? -1 : 1
        }
        return left.length - right.length
    }
    clip: true
    Layout.minimumHeight: 240
    ListView {
        id: list
        objectName: "hardwareSensorsList"
        model: root.sensorIds.slice().sort(root.compareIds)
        reuseItems: true
        spacing: 10
        delegate: HardwareReadings {
            required property string modelData
            width: list.width
            sensorIds: [modelData]
            sampling: root.sampling && y + height > list.contentY && y < list.contentY + list.height
        }
        QQC2.Label {
            anchors.centerIn: parent
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            visible: list.count === 0
            text: i18nd("monet", "No supported hardware sensors were found.")
        }
    }
}
