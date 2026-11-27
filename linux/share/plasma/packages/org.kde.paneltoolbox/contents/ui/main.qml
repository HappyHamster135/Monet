import QtQuick
import org.kde.plasma.plasmoid

// Layout controls live in the editor. Keep the live bar's dimensions intact
// instead of reserving space for a second settings button at its trailing edge.
Item {
    width: 0
    height: 0
    visible: false

    Connections {
        target: Plasmoid
        function onUserConfiguringChanged() {
            if (Plasmoid.userConfiguring) Plasmoid.containment.corona.editMode = true
        }
    }
}
