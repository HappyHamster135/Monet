/* Native installed-app launches share pending state across menu/dock views. */
import QtQuick

Item {
    id: controller
    visible: false
    property var backend: null
    readonly property bool nativeReady: backend !== null
    readonly property var states: nativeReady ? backend.states : ({})
    function key(id) { return nativeReady ? backend.key(String(id || "")) : ""; }
    function open(id, source, newWindow) {
        if (!nativeReady || !key(id)) return false;
        backend.open(String(id), source || null, !!newWindow);
        return true; // Handled, including a failure with native retry feedback.
    }
    function fromModel(model, row, source) { return nativeReady ? backend.openModel(model, row, source || null) : 0; }
    function retry(id, source) { return nativeReady && backend.retry(id, source || null); }
    function dismiss(id) { if (nativeReady) backend.dismiss(id); }
    function canOpenNewWindow(id) { return nativeReady && backend.canOpenNewWindow(String(id)); }
    Component.onCompleted: {
        try {
            backend = Qt.createQmlObject('import org.monet.launcher 1.0; Launcher { activityAgent: "org.kde.plasma.kicker" }', controller, "LaunchController");
        } catch (error) {
            // Generic Linux installs and older account previews retain their
            // native launcher. OS images require the compiled module.
            backend = null;
        }
    }
}
