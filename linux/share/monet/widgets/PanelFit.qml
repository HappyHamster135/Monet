import QtQuick
import QtQuick.Window
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

Item {
    id: fit
    visible: false
    property string helper
    readonly property real extent: Screen.width + Kirigami.Units.gridUnit
        + (Window.window ? Window.window.width : 0)
    onExtentChanged: settle.restart()
    Component.onCompleted: settle.restart()
    Timer { id: settle; interval: 900; onTriggered: runner.connectSource(fit.helper + " bar-layout") }
    P5Support.DataSource {
        id: runner
        engine: "executable"
        connectedSources: []
        onNewData: (source,data) => disconnectSource(source)
    }
}
