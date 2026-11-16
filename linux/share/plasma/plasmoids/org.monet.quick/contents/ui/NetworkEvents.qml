import QtQuick
import org.kde.plasma.networkmanagement as Network

Item {
    id: events
    visible: false
    signal changed()

    Network.NetworkStatus {
        onActiveConnectionsChanged: events.changed()
        onConnectivityChanged: events.changed()
    }
    Network.ConnectionIcon {
        onConnectingChanged: events.changed()
    }
    Network.WirelessStatus {
        onWifiSSIDChanged: events.changed()
    }
}
