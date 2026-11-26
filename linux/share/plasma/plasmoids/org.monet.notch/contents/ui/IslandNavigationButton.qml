import QtQuick
import org.kde.kirigami as K

IslandButton {
    id: button
    property bool showsSections: false
    property bool closes: false
    text: closes ? i18n("Close") : showsSections ? i18n("Sections") : i18n("Back")

    contentItem: Item {
        property real gridAmount: button.showsSections ? 1 : 0
        Behavior on gridAmount {
            enabled: button.visible && K.Units.longDuration > 1
            NumberAnimation { duration: K.Units.shortDuration; easing.type: Easing.InOutQuad }
        }
        Grid {
            anchors.centerIn: parent
            columns: 3; spacing: 2
            opacity: parent.gridAmount
            scale: 0.8 + 0.2 * opacity
            visible: opacity > 0
            Repeater {
                model: 9
                Rectangle {
                    width: 3; height: 3; radius: 1.5
                    color: button.tint
                    Accessible.ignored: true
                }
            }
        }
        K.Icon {
            anchors.centerIn: parent
            width: button.glyphSize; height: width
            opacity: 1 - parent.gridAmount
            scale: 0.8 + 0.2 * opacity
            visible: opacity > 0
            source: button.closes ? "window-close" : "go-previous"
            isMask: true; color: button.tint
            Accessible.ignored: true
        }
    }
}
