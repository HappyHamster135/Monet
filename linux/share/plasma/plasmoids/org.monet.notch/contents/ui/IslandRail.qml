import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kirigami as K
import org.kde.plasma.core as PlasmaCore

// Separate narrow surfaces keep the desktop between and below the controls clickable.
PlasmaCore.Dialog {
    id: rail
    required property var entries
    required property real reveal
    required property bool presented
    signal selected(string key)
    signal previewRequested(string key)
    type: PlasmaCore.Dialog.Dock
    flags: Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus | Qt.WindowStaysOnTopHint
    location: PlasmaCore.Types.TopEdge
    backgroundHints: PlasmaCore.Dialog.NoBackground
    visible: presented && entries.length > 0 && !!visualParent
    mainItem: Column {
        id: column
        width: 33; height: implicitHeight; spacing: 4
        opacity: Math.max(0, (rail.reveal - 0.54) / 0.46)
        enabled: opacity > 0.5
        transform: Translate { y: -5 * (1 - column.opacity) }
        Repeater {
            model: rail.entries
            IslandButton {
                required property var modelData
                enabled: modelData.enabled !== false
                opacity: enabled ? 1 : 0.4
                width: 33; height: 33
                base: "#141416"; icon.name: modelData.icon; text: modelData.label
                objectName: "island-rail-" + modelData.key
                onHoveredChanged: if (hovered && enabled) rail.previewRequested(modelData.key)
                onClicked: rail.selected(modelData.key)
            }
        }
    }
}
