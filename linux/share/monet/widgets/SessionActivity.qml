/* Shared native lock, display-power and battery state. No polling helper. */
import QtQuick
import QtQuick.Window

Item {
    id: gate
    visible: false
    property bool viewVisible: true
    property bool observePower: false
    property string outputName: Screen.name
    property var nativeState: null
    property bool initialized: false
    readonly property bool windowVisible: !Window.window || (Window.window.visible && Window.window.visibility !== Window.Minimized)
    readonly property bool nativeReady: nativeState !== null
    readonly property bool active: initialized && viewVisible && windowVisible && (!nativeReady || nativeState.active)
    readonly property bool powerReady: nativeReady && nativeState.powerReady
    readonly property bool powerLoading: nativeReady && nativeState.powerLoading
    readonly property var batteries: nativeReady ? nativeState.batteries : []
    readonly property var batteryState: nativeReady ? nativeState.batteryState : ({})

    Component.onCompleted: {
        try {
            nativeState = Qt.createQmlObject('import org.monet.activity 1.0; Activity {}', gate, "SessionActivity")
            nativeState.outputName = Qt.binding(() => gate.outputName)
            nativeState.enabled = Qt.binding(() => gate.viewVisible && gate.windowVisible)
            nativeState.observePower = Qt.binding(() => gate.observePower)
        } catch (error) {
            // A partial account preview or older host can keep drawing. The OS
            // image and native tests require and verify the installed module.
            nativeState = null
        }
        initialized = true
    }
}
