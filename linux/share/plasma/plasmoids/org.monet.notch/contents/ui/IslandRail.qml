import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kirigami as K
import org.kde.plasma.core as PlasmaCore

// Separate narrow surfaces keep the desktop between and below the controls clickable.
PlasmaCore.Dialog {
    id: rail
    required property var entries
    required property bool presented
    signal selected(string key)
    type: PlasmaCore.Dialog.Dock
    flags: Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus | Qt.WindowStaysOnTopHint
    location: PlasmaCore.Types.TopEdge
    backgroundHints: PlasmaCore.Dialog.NoBackground
    visible: presented && entries.length > 0 && !!visualParent
    mainItem: Column {
        id: column
        width: 33; height: implicitHeight; spacing: 4
        opacity: shown ? 1 : 0
        property bool shown: false
        Behavior on opacity { NumberAnimation { duration: K.Units.shortDuration; easing.type: Easing.OutCubic } }
        Connections { target: rail; function onVisibleChanged() { column.shown = rail.visible } }
        Repeater {
            model: rail.entries
            IslandButton {
                required property var modelData
                width: 33; height: 33
                base: "#141416"; icon.name: modelData.icon; text: modelData.label
                objectName: "island-rail-" + modelData.key
                onClicked: rail.selected(modelData.key)
            }
        }
    }
}
