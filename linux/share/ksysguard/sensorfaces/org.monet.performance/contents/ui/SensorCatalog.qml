import QtQuick
import org.kde.ksysguard.sensors as Sensors

Item {
    id: catalog
    visible: false
    property var sensorIds: []
    property var tree: null
    property int attempts: 0
    property bool ready: false

    // Optional devices belong in discovery, not the page's required-sensor list.
    // The KDE model also follows sensors added/removed after the page opens.
    function scan() {
        if (!tree) return
        const found = []
        function visit(parentIndex) {
            for (let row = 0; row < tree.rowCount(parentIndex); ++row) {
                const node = tree.index(row, 0, parentIndex)
                const sensor = tree.data(node, Sensors.SensorTreeModel.SensorId)
                // Metadata discovery is cheap; it does not subscribe to values.
                // Keep IDs for per-core and per-device detail views as well.
                // The tree also offers regular-expression selectors (for example
                // network/(?!all).*/download); these are not physical devices.
                if (sensor && /^(cpu|memory|gpu|network|disk|lmsensors)\//.test(sensor)
                        && !/[()[\]*?^$|\\]/.test(sensor)) found.push(sensor)
                if (tree.rowCount(node)) visit(node)
            }
        }
        const root = tree.index(-1, 0)
        ready = tree.rowCount(root) > 0
        visit(root)
        found.sort()
        if (JSON.stringify(found) !== JSON.stringify(sensorIds)) sensorIds = found
    }
    function discover() {
        if (tree) tree.destroy()
        tree = treeComponent.createObject(catalog)
        scanLater.restart()
    }
    Component { id: treeComponent; Sensors.SensorTreeModel {} }
    Connections {
        target: catalog.tree
        function onModelReset() { scanLater.restart() }
        function onRowsInserted() { scanLater.restart() }
        function onRowsRemoved() { scanLater.restart() }
    }
    Timer { id: scanLater; interval: 100; onTriggered: catalog.scan() }
    Timer {
        interval: 2000
        repeat: true
        running: catalog.attempts < 2 && !catalog.ready
        onTriggered: { catalog.attempts++; catalog.discover() }
    }
    Component.onCompleted: discover()
}
