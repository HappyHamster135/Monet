import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import QtCore as Core
import QtMultimedia as Media
import org.kde.ki18n as I18n

ColumnLayout {
    id: feed
    readonly property bool menuOpen: picker.popup.visible
    signal stopRequested()
    readonly property bool software: GraphicsInfo.api === GraphicsInfo.Software
    property bool opened: false
    property bool started: false
    property bool gotFrame: false
    property string selectedId: ""
    property string selectedName: ""
    property string problem: ""
    readonly property var inputs: devices.videoInputs
    function i18n(message) { return words.i18n(message) }
    I18n.KLocalizedQmlContext { id: words; translationDomain: "monet" }
    Core.Settings {
        id: saved
        location: Core.StandardPaths.writableLocation(Core.StandardPaths.GenericConfigLocation) + "/Monet/CameraMirror.conf"
    }
    Media.MediaDevices {
        id: devices
        onVideoInputsChanged: if (feed.opened) Qt.callLater(feed.refreshDevices, false)
    }
    function key(device) {
        // Camera IDs are opaque byte arrays and may contain non-text bytes.
        return Array.from(new Uint8Array(device.id), n => n.toString(16).padStart(2, "0")).join("")
    }
    function refreshDevices(first) {
        const ids = Array.from(inputs, key)
        const preferred = selectedId || saved.value("preferredDevice", "")
        const name = selectedName || saved.value("preferredName", "")
        let index = ids.findIndex((id, i) => id === preferred && inputs[i].description === name)
        // Some backends assign fresh device IDs on each launch.
        if (first && index < 0 && name) {
            const same = Array.from(inputs).filter(d => d.description === name)
            if (same.length === 1) index = ids.indexOf(key(same[0]))
        }
        const missing = !!preferred && index < 0
        if (missing) {
            stop()
            problem = i18n("The selected camera is disconnected.")
        }
        if (index < 0 && ids.length)
            index = Math.max(0, Array.from(inputs).findIndex(device => device.isDefault))
        picker.model = Array.from(inputs, device => device.description)
        picker.currentIndex = index
        selectedId = ids[index] || ""
        selectedName = inputs[index]?.description || ""
        if (first && selectedId && !missing) start()
    }
    function remember() {
        saved.setValue("preferredDevice", selectedId)
        saved.setValue("preferredName", selectedName)
        saved.sync()
    }
    function stop() {
        started = false
        startup.stop()
        nextImage.stop()
        camera.stop()
        video.clearOutput()
        gotFrame = false
    }
    function start() {
        const device = Array.from(inputs).find(d => key(d) === selectedId)
        if (!device) return
        stop()
        problem = ""
        camera.cameraDevice = device
        const formats = Array.from(device.videoFormats)
        // A small mirror needs a smooth preview. Let the backend choose when it
        // doesn't publish suitable capture formats.
        const smooth = formats.filter(f => f.maxFrameRate >= 15)
        if (smooth.length) {
            const target = Math.min(1280, Math.max(320, video.width * feed.Screen.devicePixelRatio))
            const score = f => {
                const width = Math.max(f.resolution.width, f.resolution.height)
                return width >= target ? width - target : (target - width) * 3
            }
            camera.cameraFormat = smooth.reduce((best, f) => score(f) < score(best) ? f : best)
        }
        started = true
        startup.start()
        camera.start()
    }
    function unavailable(message) {
        if (!started) return
        stop()
        problem = message
    }
    Component.onCompleted: { opened = true; saved.sync(); refreshDevices(true) }
    Media.CaptureSession {
        // Qt's video scene-graph node needs a graphics API. The software renderer
        // can display a scaled in-memory image, requested only as new frames arrive.
        imageCapture: softwareCapture.item || null
        camera: Media.Camera {
            id: camera
            onErrorOccurred: (code, message) => feed.unavailable(message || i18n("The camera is unavailable."))
        }
        videoOutput: video
    }
    Loader {
        id: softwareCapture
        active: feed.software && feed.started
        visible: false
        sourceComponent: Media.ImageCapture {}
    }
    Timer {
        id: nextImage
        interval: 100
        onTriggered: {
            const source = softwareCapture.item
            if (feed.started && source?.readyForCapture) source.capture()
        }
    }
    Timer {
        id: startup
        interval: 8000
        onTriggered: feed.unavailable(i18n("No video arrived. Check the camera and try again."))
    }
    RowLayout {
        Layout.fillWidth: true
        IslandComboBox {
            id: picker
            popupBounds: feed
            objectName: "cameraDevicePicker"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            visible: count > 0
            enabled: count > 1
            Accessible.name: i18n("Camera")
            onActivated: index => {
                const device = feed.inputs[index]
                if (!device) return
                feed.selectedId = feed.key(device)
                feed.selectedName = device.description
                feed.remember()
                feed.start()
            }
        }
        Item { visible: !picker.visible; Layout.fillWidth: true }
        IslandButton {
            plain: true; text: feed.started ? i18n("Stop camera") : i18n("Back")
            icon.name: feed.started ? "media-playback-stop" : "go-previous"
            onClicked: feed.stopRequested()
        }
    }
    Rectangle {
        Layout.fillWidth: true
        Layout.fillHeight: true
        color: "#171719"; radius: 12
        clip: true
        Media.VideoOutput {
            id: video
            objectName: "cameraVideo"
            anchors.fill: parent
            fillMode: Media.VideoOutput.PreserveAspectFit
            mirrored: true
            visible: feed.started && !feed.software
        }
        Image {
            id: softwareImage
            anchors.fill: parent
            source: softwareCapture.item?.preview || ""
            cache: false
            mirror: true
            fillMode: Image.PreserveAspectFit
            visible: feed.software && feed.started
            onStatusChanged: if (visible && status === Image.Ready) { feed.gotFrame = true; startup.stop() }
        }
        Connections {
            target: video.videoSink
            enabled: feed.started && (feed.software || !feed.gotFrame)
            function onVideoFrameChanged() {
                if (feed.software) {
                    if (!nextImage.running) nextImage.start()
                } else if (video.sourceRect.width > 0) {
                    feed.gotFrame = true
                    startup.stop()
                }
            }
        }
        ColumnLayout {
            anchors.centerIn: parent
            width: Math.max(0, parent.width - 24)
            visible: !feed.started || !feed.gotFrame
            C.Label {
                Layout.fillWidth: true
                color: "white"
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                horizontalAlignment: Text.AlignHCenter
                text: !feed.inputs.length ? i18n("No camera connected.")
                    : feed.problem || (feed.started ? i18n("Starting camera…") : i18n("Camera stopped."))
            }
            IslandButton { caption: true;
                objectName: "retryCamera"
                Layout.alignment: Qt.AlignHCenter
                visible: !feed.started && picker.currentIndex >= 0
                text: i18n("Start camera")
                onClicked: { feed.remember(); feed.start() }
            }
        }
    }
}
