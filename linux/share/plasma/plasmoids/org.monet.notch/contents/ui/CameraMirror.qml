import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.ki18n as I18n
import org.monet.activity 1.0 as Monet

ColumnLayout {
    id: mirror
    objectName: "cameraMirror"
    property bool presented: true
    property bool startOnOpen: false
    readonly property bool available: presented && session.lockKnown && !session.locked && session.active
    Monet.Activity {
        id: session
        enabled: mirror.presented
        outputName: mirror.Screen.name
        onContextChanged: if (lockKnown && locked) mirror.startOnOpen = false
    }
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
    Item { Layout.fillHeight: true; visible: !feed.visible }
    C.Label {
        Layout.fillWidth: true
        visible: !feed.visible
        text: feed.status === Loader.Error ? i18n("The camera preview could not open.")
                                           : i18n("The camera is off.")
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.Wrap
    }
    C.Button {
        objectName: "startCamera"
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
    Item { Layout.fillHeight: true; visible: !feed.visible }
}
