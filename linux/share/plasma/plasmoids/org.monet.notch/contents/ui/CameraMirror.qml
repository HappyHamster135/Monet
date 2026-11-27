import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.ki18n as I18n

ColumnLayout {
    id: mirror
    readonly property bool menuOpen: !!feed.item?.menuOpen
    objectName: "cameraMirror"
    property bool presented: true
    property bool startOnOpen: false
    property var session: null
    readonly property bool available: presented && !!session?.lockKnown && !session.locked && session.active
    Component.onCompleted: {
        // The Home Bar supplies its existing session observer. A floating mirror
        // uses the same native monitor when it is installed on this desktop.
        if (!session) {
            try {
                session = Qt.createQmlObject('import org.monet.activity 1.0; Activity {}', mirror)
                session.enabled = Qt.binding(() => mirror.presented)
                session.outputName = Qt.binding(() => mirror.Screen.name)
            } catch (error) {
                session = portableLock.createObject(mirror)
            }
        }
        if (session.lockKnown && session.locked) startOnOpen = false
    }
    Component { id: portableLock; CameraLock {} }
    readonly property bool locked: !!session?.lockKnown && session.locked
    onLockedChanged: if (locked) startOnOpen = false
    property bool requested: false
    onPresentedChanged: if (!presented) { requested = false; startOnOpen = false }
    onAvailableChanged: {
        if (!available) requested = false
        else if (startOnOpen) { startOnOpen = false; requested = true }
    }
    function i18n(message) { return words.i18n(message) }
    I18n.KLocalizedQmlContext { id: words; translationDomain: "monet" }

    Loader {
        id: feed
        objectName: "cameraFeedLoader"
        active: mirror.requested && mirror.available
        source: "CameraFeed.qml"
        Layout.fillHeight: true
        Layout.fillWidth: true
        visible: status === Loader.Ready
        Connections {
            target: feed.item
            function onStopRequested() { mirror.requested = false }
        }
    }
    IslandEmpty {
        Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 0
        visible: !feed.visible
        symbol: "camera-web"; tint: "#9fc9ed"
        detail: i18n("A quick mirror, right in your notch.")
        title: feed.status === Loader.Error ? i18n("The camera preview could not open.")
                                           : i18n("The camera is off.")
    }
    IslandButton {
        objectName: "startCamera"
        caption: true; prominent: true
        Layout.alignment: Qt.AlignHCenter
        visible: !feed.visible
        enabled: mirror.available && feed.status !== Loader.Loading
        text: i18n("Start camera")
        icon.name: "camera-web"
        onClicked: {
            if (feed.status === Loader.Error) {
                feed.source = ""
                feed.source = "CameraFeed.qml"
            }
            mirror.requested = true
        }
    }
}
