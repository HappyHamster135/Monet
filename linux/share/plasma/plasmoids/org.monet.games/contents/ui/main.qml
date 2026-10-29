/*
 * Games in the panel: the button opens Games, the app with every game you have
 * (monet-games), as Windows+G does. Opening it again brings that window forward.
 */
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    readonly property string helper: "@LIBEXECDIR@/monet-quick"

    Plasmoid.icon: "monet-windows"
    toolTipMainText: i18n("Games")
    toolTipSubText: i18n("Every game you have, in Monet and in Windows")
    preferredRepresentation: compactRepresentation
    activationTogglesExpanded: false

    P5Support.DataSource {
        id: runner
        engine: "executable"
        connectedSources: []
        onNewData: source => disconnectSource(source)
    }

    // Through its menu entry, as the menu starts apps (the helper takes the entry's name as hex).
    function open() {
        let out = ""
        for (const c of "monet-games.desktop")
            out += c.charCodeAt(0).toString(16).padStart(2, "0")
        runner.connectSource(helper + " launch " + out)
    }

    Plasmoid.onActivated: open()
    // Nothing to show but the button. Without a full view of its own, Plasma takes this item as
    // it and lifts it out of the bar to show the button, so the button never showed.
    fullRepresentation: Item {}

    compactRepresentation: MouseArea {
        // As wide as the bar is high, as Plasma's own icons in it are (with no size of its own,
        // the bar gave it none, and the button was gone).
        Layout.minimumWidth: Plasmoid.formFactor === PlasmaCore.Types.Vertical ? 0 : height
        Layout.minimumHeight: Plasmoid.formFactor === PlasmaCore.Types.Vertical ? width : 0
        hoverEnabled: true
        onClicked: root.open()
        Kirigami.Icon {
            anchors.fill: parent
            source: Plasmoid.icon
            active: parent.containsMouse
        }
        Accessible.role: Accessible.Button
        Accessible.name: i18n("Games")
        Accessible.onPressAction: root.open()
    }
}
