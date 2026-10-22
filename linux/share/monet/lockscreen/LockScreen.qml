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

    Loader {
        id: monet
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
