import QtQuick
import QtQuick.Layouts
import org.kde.ksysguard.faces as Faces
import "../../../org.monet.performance/contents/ui" as Performance

Faces.CompactSensorFace {
    Layout.minimumWidth: 120
    Layout.minimumHeight: contentItem.implicitHeight
    contentItem: Performance.Metric { label: i18nd("monet", "Graphics"); sensorId: "gpu/all/usage"; paused: !visible }
}
