/* One explicit folder-opening action; no metadata reads while idle or hidden. */
import QtQuick
import org.kde.plasma.plasma5support as P5Support

Item {
    id: controller
    visible: false
    property var backend: null
    property var fallbackRunner: null
    property string fallbackSource: ""
    property string fallbackError: ""
    readonly property bool nativeReady: backend !== null
    readonly property bool busy: nativeReady ? backend.busy : fallbackSource !== ""
    readonly property bool cancellable: nativeReady && busy
    readonly property string error: nativeReady ? backend.error : fallbackError
    function open(url, directory, source) {
        if (busy) return false;
        if (nativeReady) return backend.open(url, !!directory, source || null);
        fallbackError = "";
        const bytes = unescape(encodeURIComponent(JSON.stringify({url: String(url), directory: !!directory})));
        let encoded = "";
        for (let i = 0; i < bytes.length; i++) encoded += bytes.charCodeAt(i).toString(16).padStart(2, "0");
        fallbackSource = "'@LIBEXECDIR@/monet-files-tools' --open-folder " + encoded;
        if (!fallbackRunner) fallbackRunner = fallbackComponent.createObject(controller);
        fallbackRunner.connectSource(fallbackSource);
        return true;
    }
    function cancel() { if (nativeReady) backend.cancel(); }
    function dismissError() {
        if (busy) return;
        if (nativeReady) backend.cancel();
        else fallbackError = "";
    }
    function plainText(formatted) {
        if (nativeReady && typeof backend.plainText === "function") return backend.plainText(String(formatted || ""));
        // Compatibility with an older native module: retain literal text while
        // removing the native job description's links, rather than render HTML.
        return String(formatted || "").replace(/<br\s*\/?>/gi, "\n").replace(/<[^>]*>/g, "")
            .replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'").replace(/&lt;/g, "<")
            .replace(/&gt;/g, ">").replace(/&nbsp;/g, " ").replace(/&amp;/g, "&");
    }
    Component {
        id: fallbackComponent
        P5Support.DataSource {
            engine: "executable"
            onNewData: (source, data) => {
                disconnectSource(source);
                if (source !== controller.fallbackSource) return;
                controller.fallbackSource = "";
                try {
                    const result = JSON.parse(data.stdout);
                    if (data["exit code"] !== 0 || !result.ok) throw new Error(result.error || "");
                } catch (error) {
                    controller.fallbackError = String(error.message || "") || i18nd("monet", "Couldn't open Files. Try again.");
                }
            }
        }
    }
    Component.onCompleted: {
        try { backend = Qt.createQmlObject('import org.monet.launcher 1.0; FolderOpener {}', controller, "TransferFolderOpener"); }
        catch (error) { backend = null; } // Older generic Linux/account previews.
    }
}
