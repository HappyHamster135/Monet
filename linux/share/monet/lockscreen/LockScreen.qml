/*
 * Plasma's lock screen, Monet's way. Plasma reads its lock screen from the
 * desktop shell (plasma/shells/org.kde.plasma.desktop/contents/lockscreen),
 * not from the global theme, so install.sh puts this file there in place of
 * KDE's LockScreen.qml, with MonetLockScreen.qml beside it.
 *
 * It opens Monet's lock screen, and KDE's own (LockScreenUi.qml, left as it
 * is) if Monet's can't load, so the screen can always be unlocked. The
 * properties and signals are the ones kscreenlocker and KDE's lock screen use.
 */
import QtQuick
import QtCore

Item {
    id: root
    property bool debug: false
    property string notification
    signal clearPassword()
    signal notificationRepeated()

    // These are magical properties that kscreenlocker looks for
    property bool viewVisible: false

    LayoutMirroring.enabled: Application.layoutDirection === Qt.RightToLeft
    LayoutMirroring.childrenInherit: true

    implicitWidth: 800
    implicitHeight: 600

    // Only an explicit cleaning request defers construction of the password UI.
    // Every screen reads the same deadline. An ordinary lock starts immediately.
    property bool checkedRequest: false
    property double cleaningUntil: 0
    Settings {
        id: request
        location: StandardPaths.writableLocation(StandardPaths.RuntimeLocation) + "/monet-cleaning.ini"
        category: "Cleaning"
    }
    Component.onCompleted: {
        const deadline = Number(request.value("deadline", 0))
        const remaining = deadline - Date.now()
        if (remaining > 0 && remaining <= 120000) cleaningUntil = deadline
        checkedRequest = true
    }
    function finishCleaning() {
        request.sync()
        if (cleaningUntil && Number(request.value("deadline", 0)) === cleaningUntil) {
            request.setValue("deadline", 0)
            request.sync()
        }
        cleaningUntil = 0
    }
    Loader {
        anchors.fill: parent
        active: root.cleaningUntil > 0
        focus: active
        source: "CleaningScreen.qml"
        onStatusChanged: if (status === Loader.Error) root.finishCleaning()
    }
    Loader {
        id: monet
        active: root.checkedRequest && !root.cleaningUntil
        anchors.fill: parent
        focus: status === Loader.Ready
        source: "MonetLockScreen.qml"
    }

    Loader {
        id: kde
        anchors.fill: parent
        focus: active
        active: monet.status === Loader.Error
        source: "LockScreenUi.qml"
    }
}
