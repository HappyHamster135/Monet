import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.ksysguard.faces as Faces
import "../../../org.monet.performance/contents/ui" as Performance

Faces.SensorFace {
    id: face
    Layout.minimumWidth: 440
    Performance.SensorCatalog { id: catalog }
    contentItem: Loader {
        Layout.minimumHeight: item ? item.Layout.minimumHeight : 80
        sourceComponent: catalog.ready ? graphics : waiting
    }
    Component {
        id: graphics
        Performance.Performance { availableSensors: catalog.sensorIds; section: 2; graphicsOnly: true }
    }
    Component {
        id: waiting
        ColumnLayout {
            QQC2.Label { text: catalog.attempts < 2 ? i18nd("monet", "Loading graphics hardware…") : i18nd("monet", "Hardware statistics are unavailable."); wrapMode: Text.WordWrap }
            QQC2.Button { visible: catalog.attempts >= 2; text: i18nd("monet", "Try again"); onClicked: { catalog.attempts = 0; catalog.discover() } }
        }
    }
}
