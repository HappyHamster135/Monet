/*
 * What Plasma's desktop shows in edit mode: Monet's (MonetDesktopEditMode.qml),
 * or KDE's own (KdeDesktopEditMode.qml, KDE's file kept beside it) whenever
 * Monet's can't load. Desktop.qml reads centerX and centerY to place the
 * desktop it shrinks.
 */
import QtQuick

Item {
    id: editMode

    readonly property Item page: monet.item || kde.item
    property real centerX: root.width / 2
    property real centerY: root.height / 2

    Binding { target: containmentParent; property: "scaleFactor"; value: 1; restoreMode: Binding.RestoreBindingOrValue }

    Loader {
        id: monet
        anchors.fill: parent
    }

    Loader {
        id: kde
        anchors.fill: parent
    }

    Component.onCompleted: {
        monet.setSource(Qt.resolvedUrl("MonetDesktopEditMode.qml"))
        if (monet.status === Loader.Error) {
            kde.setSource(Qt.resolvedUrl("KdeDesktopEditMode.qml"))
        }
    }
}
