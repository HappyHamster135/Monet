// A managed app window using the same permanent title bar as Settings and Store.
import QtQuick
import QtQuick.Window
import QtCore as Core
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami
import "../games" as Shared
Shared.MonetWindow {
    id: appWindow
    property string geometryKey: "Editor"
    property string initialScreenName: ""
    property bool ready: false
    property string nativeId: ""
    property bool nativeGeometry: true
    property bool closeReady: false
    property bool closingPending: false
    property bool geometryPending: false
    property bool blurBehind: false
    property bool finishedOnce: false
    function i18n(text) { return i18nd("monet", text) }
    function geometryCommand(action) {
        const caption = encodeURIComponent(title).replace(/[!'()*]/g, c => "%" + c.charCodeAt(0).toString(16))
        geometryPending = true
        geometryRunner.connectSource("@LIBEXECDIR@/monet-editor-window " + action + " " + geometryKey + " " + caption + (nativeId ? " " + nativeId : ""))
    }
    function completeClose() {
        if (finishedOnce) return
        closeDeadline.stop()
        closeReady = true
        close()
    }
    P5Support.DataSource {
        id: geometryRunner
        engine: "executable"
        onNewData: (source, data) => {
            disconnectSource(source)
            appWindow.geometryPending = false
            try { const reply = JSON.parse(data.stdout); if (reply.ok) appWindow.nativeId = reply.id } catch (_) {}
            if (source.includes(" restore ")) { appWindow.contentItem.opacity = 1; revealDeadline.stop() }
            if (appWindow.closingPending && source.includes(" capture ")) appWindow.completeClose()
        }
    }
    Timer { id: restoreTimer; interval: 180; onTriggered: if (appWindow.nativeGeometry) appWindow.geometryCommand("restore") }
    Timer { id: revealDeadline; interval: 1200; onTriggered: appWindow.contentItem.opacity = 1 }
    onNativeGeometryChanged: if (!nativeGeometry) contentItem.opacity = 1
    Timer { id: closeDeadline; interval: 1200; onTriggered: appWindow.completeClose() }
    signal finished()
    transientParent: null
    color: "transparent"
    minimumWidth: Math.min(420, screen.width - 40)
    minimumHeight: Math.min(400, screen.height - 80)
    width: 640
    height: 760
    Core.Settings {
        id: saved
        category: "MonetEditor/" + appWindow.geometryKey
        property int windowWidth: 640
        property int windowHeight: 760
        property int windowX: -1
        property int windowY: -1
        property string screenName: ""
        property bool maximized: false
    }
    function present() {
        if (!ready) {
            const target = Application.screens.find(s => s.name === saved.screenName)
                || Application.screens.find(s => s.name === initialScreenName) || screen
            screen = target
            width = Math.max(minimumWidth, Math.min(saved.windowWidth, target.width - 48))
            height = Math.max(minimumHeight, Math.min(saved.windowHeight, target.height - 144))
            x = Math.max(target.virtualX + 16, Math.min(saved.windowX < 0 ? target.virtualX + 40 : saved.windowX, target.virtualX + target.width - width - 16))
            y = Math.max(target.virtualY + 48, Math.min(saved.windowY < 0 ? target.virtualY + 80 : saved.windowY, target.virtualY + target.height - height - 48))
            ready = true
            contentItem.opacity = nativeGeometry ? 0 : 1
            if (nativeGeometry) revealDeadline.restart()
            restoreTimer.restart()
            if (saved.maximized) showMaximized()
            else showNormal()
        } else {
            if (visibility === Window.Minimized) {
                if (saved.maximized) showMaximized(); else showNormal()
            } else visible = true
            // Wayland doesn't report compositor-side minimization to clients.
            // Activate this exact window when its editor is opened again.
            if (nativeGeometry) geometryCommand("activate")
        }
        raise()
        requestActivate()
    }
    function remember() {
        if (!ready) return
        if (visibility === Window.Windowed) {
            saved.windowWidth = width; saved.windowHeight = height
            saved.windowX = x; saved.windowY = y
        }
        saved.screenName = screen.name
        if (visibility === Window.Windowed || visibility === Window.Maximized)
            saved.maximized = visibility === Window.Maximized
        saved.sync()
    }
    Timer { id: rememberTimer; interval: 200; onTriggered: appWindow.remember() }
    onWidthChanged: if (ready) rememberTimer.restart()
    onHeightChanged: if (ready) rememberTimer.restart()
    onXChanged: if (ready) rememberTimer.restart()
    onYChanged: if (ready) rememberTimer.restart()
    onVisibilityChanged: if (ready && visible) rememberTimer.restart()
    onClosing: event => {
        remember()
        restoreTimer.stop()
        revealDeadline.stop()
        if (nativeGeometry && !closeReady) {
            event.accepted = false
            if (!closingPending) {
                closingPending = true
                restoreTimer.stop()
                closeDeadline.restart()
                geometryCommand("capture")
            }
            // Capture compositor geometry asynchronously, but dismiss at once.
            visible = false
        } else if (!finishedOnce) {
            finishedOnce = true
            finished()
        }
    }
}
