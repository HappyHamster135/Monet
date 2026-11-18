import QtQuick
import org.kde.bluezqt 1.0 as BluezQt

Item {
    id: events
    signal changed()
    visible: false
    BluezQt.DevicesModel { id: devices }
    Connections {
        target: devices
        function onDataChanged() { events.changed() }
        function onRowsInserted() { events.changed() }
        function onRowsRemoved() { events.changed() }
        function onModelReset() { events.changed() }
    }
    Connections {
        target: BluezQt.Manager
        function onBluetoothOperationalChanged() { events.changed() }
    }
}
