import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.ksysguard.faces as Faces

Faces.SensorFace {
    id: face
    Layout.minimumWidth: 440
    SensorCatalog { id: catalog }
    // Instantiate readers only after metadata is available. The daemon can be
    // activated on first use; asking for individual metadata before it is ready
    // leaves some KDE readers in Loading even while numeric samples arrive.
    contentItem: Loader {
        Layout.minimumHeight: item ? item.Layout.minimumHeight : 80
        sourceComponent: catalog.ready ? performance : waiting
    }
    Component {
        id: performance
        Performance { availableSensors: catalog.sensorIds }
    }
    Component {
        id: waiting
        ColumnLayout {
            spacing: 12
            QQC2.Label {
                text: catalog.attempts < 2 ? i18nd("monet", "Loading hardware…")
                    : i18nd("monet", "Hardware statistics are unavailable.")
                wrapMode: Text.Wrap
            }
            QQC2.Button {
                visible: catalog.attempts >= 2
                text: i18nd("monet", "Try again")
                onClicked: { catalog.attempts = 0; catalog.discover() }
            }
        }
    }
}
