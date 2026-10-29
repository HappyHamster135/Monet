/*
 * The widget gallery Plasma's desktop opens from "Add Widgets…": Monet's
 * (MonetWidgetExplorer.qml), or KDE's own (KdeWidgetExplorer.qml, KDE's file
 * kept beside it) whenever Monet's can't load.
 *
 * Desktop.qml loads this with containment and sidePanel set, keeps it while
 * preventWindowHide is true, lets clicks through while outputOnly is true,
 * follows its opacity, and closes it on closed().
 */
import QtQuick
import org.kde.plasma.core as PlasmaCore

Item {
    id: gallery

    property QtObject containment
    property PlasmaCore.Dialog sidePanel
    readonly property Item page: monet.item || kde.item
    readonly property bool preventWindowHide: page ? page.preventWindowHide : false
    readonly property bool outputOnly: page ? page.outputOnly : false

    signal closed()

    width: page ? page.width : 0
    height: 800
    opacity: page ? page.opacity : 1

    Loader {
        id: monet
        height: parent.height
        focus: true
        onLoaded: item.closed.connect(gallery.closed)
    }

    Loader {
        id: kde
        height: parent.height
        focus: true
        onLoaded: item.closed.connect(gallery.closed)
    }

    Component.onCompleted: {
        // D-Bus (Settings) has no sender; use this screen's desktop in that case.
        const pieces = { containment: gallery.containment || root.containment.plasmoid, sidePanel: gallery.sidePanel }
        monet.setSource(Qt.resolvedUrl("MonetWidgetExplorer.qml"), pieces)
        if (monet.status === Loader.Error) {
            kde.setSource(Qt.resolvedUrl("KdeWidgetExplorer.qml"), pieces)
        }
    }
}
