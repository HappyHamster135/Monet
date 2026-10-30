import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import org.kde.ksysguard.faces as Faces

Faces.CompactSensorFace {
    Layout.minimumWidth: 120
    Layout.minimumHeight: contentItem.implicitHeight
    contentItem: Metric {
        label: i18nd("monet", "CPU")
        sensorId: "cpu/all/usage"
        paused: !visible || (Window.window && (!Window.window.visible || Window.window.visibility === Window.Minimized))
    }
}
