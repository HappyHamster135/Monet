/*
 * Monet's restart and shut-down screen: the desktop softens behind a sheet
 * of glass that asks one question. Asked to restart, shut down or sign out,
 * it counts down with the sun on the answer; asked from Ctrl+Alt+Del or the
 * power button, it offers all of them. Esc or a click outside cancels, and
 * going ahead lets the sun set first.
 *
 * KDE's logout greeter loads it from the global theme (logout/Logout.qml),
 * once per screen, with sdtype, ShutdownType, maysd, canLogout, spdMethods,
 * softwareUpdatePending and the reboot notes as context properties, and
 * listens for the signals below by name. If it can't load, KDE's own shows.
 */
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Effects
import QtQuick.Layouts

import org.kde.coreaddons as KCoreAddons
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.sessions
import "timer.js" as AutoTriggerTimer

Item {
    id: root
    width: typeof screenGeometry === "undefined" ? 1440 : screenGeometry.width
    height: typeof screenGeometry === "undefined" ? 900 : screenGeometry.height

    signal logoutRequested()
    signal haltRequested()
    signal haltUpdateRequested()
    signal suspendRequested(int spdMethod)
    signal rebootRequested()
    signal rebootRequested2(int opt)
    signal rebootUpdateRequested()
    signal cancelRequested()
    signal lockScreenRequested()
    signal cancelSoftwareUpdateRequested()

    // Without a GPU there's no blur behind: a heavier wash instead.
    readonly property bool softwareRendering: GraphicsInfo.api === GraphicsInfo.Software
    readonly property real speed: Kirigami.Units.longDuration / 200
    // Mist or smoke, the way monet-light set the colors.
    readonly property bool smoke: Kirigami.Theme.backgroundColor.hslLightness < 0.5
    readonly property color ink: smoke ? "#EFECE6" : "#1C1B19"
    readonly property color dim: smoke ? "#B4AEA5" : "#6B665E"
    readonly property color glass: smoke ? Qt.rgba(0.141, 0.137, 0.129, 0.78) : Qt.rgba(0.969, 0.961, 0.945, 0.76)
    readonly property color hairline: smoke ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(0, 0, 0, 0.09)
    readonly property color pebble: smoke ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0.11, 0.106, 0.098, 0.06)
    readonly property color lily: smoke ? "#4DB4A0" : "#357F72"
    readonly property color sun: "#F2552C"
    readonly property color paper: "#FBF7EE"

    // Asked for one thing (with a countdown), or for a choice.
    readonly property bool choosing: sdtype === ShutdownType.ShutdownTypeDefault
    readonly property bool restarting: sdtype === ShutdownType.ShutdownTypeReboot
    readonly property bool shuttingDown: sdtype === ShutdownType.ShutdownTypeHalt
    property int remaining: 30
    property bool counting: !choosing
    property bool leaving: false
    readonly property string firstName: (kuser.fullName || kuser.loginName || "").trim().split(" ")[0]

    function go() {
        if (restarting) {
            leave(() => softwareUpdatePending ? root.rebootUpdateRequested() : root.rebootRequested())
        } else if (shuttingDown) {
            leave(() => softwareUpdatePending ? root.haltUpdateRequested() : root.haltRequested())
        } else {
            leave(() => root.logoutRequested())
        }
    }

    // The sun sets, then the PC does what was asked. Sleep doesn't wait.
    function leave(action) {
        if (leaving) {
            return
        }
        leaving = true
        counting = false
        sunset.action = action
        sunset.start()
    }

    function stopCounting() {
        AutoTriggerTimer.cancelAutoTrigger()
    }

    KCoreAddons.KUser {
        id: kuser
    }

    // Anyone else signed in could lose what they haven't saved.
    SessionsModel {
        id: otherSessions
        includeUnusedSessions: false
        includeOwnSession: false
    }

    QQC2.Action {
        shortcut: "Escape"
        onTriggered: root.cancelRequested()
    }

    Timer {
        interval: 1000
        repeat: true
        running: root.counting
        onTriggered: {
            root.remaining -= 1
            if (root.remaining <= 0) {
                root.go()
            }
        }
        // A key on any screen stops the countdown on all of them.
        Component.onCompleted: AutoTriggerTimer.addCancelAutoTriggerCallback(() => { root.counting = false })
    }

    // The desktop, softened and washed in mist or smoke (KWin blurs behind this window).
    Rectangle {
        id: wash
        anchors.fill: parent
        readonly property color tone: root.smoke ? "#14131A" : "#F3F1EC"
        color: Qt.rgba(tone.r, tone.g, tone.b, root.softwareRendering ? 0.82 : (root.smoke ? 0.46 : 0.38))
        opacity: 0
        Component.onCompleted: opacity = 1
        Behavior on opacity { NumberAnimation { duration: Math.round(380 * root.speed) } }
    }

    MouseArea {
        anchors.fill: parent
        onClicked: root.cancelRequested()
    }

    Item {
        // The sheet rises into place.
        id: rise
        anchors.horizontalCenter: parent.horizontalCenter
        width: sheet.width
        height: sheet.height
        y: Math.round((parent.height - height) / 2) + Kirigami.Units.gridUnit * 1.5
        opacity: 0
        Component.onCompleted: {
            y = Qt.binding(() => Math.round((parent.height - height) / 2))
            opacity = 1
        }
        Behavior on y { NumberAnimation { duration: Math.round(380 * root.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] } }
        Behavior on opacity { NumberAnimation { duration: Math.round(380 * root.speed) } }

        Rectangle {
            id: sheet
            readonly property int pad: Kirigami.Units.gridUnit * 2
            width: Math.min(root.width - Kirigami.Units.gridUnit * 2,
                            Math.max(Kirigami.Units.gridUnit * 23, content.implicitWidth + pad * 2))
            height: content.implicitHeight + pad * 2
            radius: 22
            color: root.glass
            border.width: 1
            border.color: root.hairline
            layer.enabled: !root.softwareRendering
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowColor: root.smoke ? "#99000000" : "#661C1B19"
                shadowBlur: 1
                shadowVerticalOffset: 10
            }

            // Clicks on the sheet stay on it.
            MouseArea {
                anchors.fill: parent
            }

            ColumnLayout {
                id: content
                anchors.fill: parent
                anchors.margins: sheet.pad
                spacing: Kirigami.Units.smallSpacing * 2

                // Your face, or your initial on a dab of lily, as on the lock screen.
                Item {
                    id: avatar
                    visible: root.choosing
                    Layout.alignment: Qt.AlignHCenter
                    implicitWidth: 76
                    implicitHeight: 76
                    readonly property bool hasFace: face.status === Image.Ready && !root.softwareRendering

                    Rectangle {
                        anchors.fill: parent
                        radius: width / 2
                        color: root.paper
                        opacity: 0.85
                    }
                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 3
                        radius: width / 2
                        visible: !avatar.hasFace
                        gradient: Gradient {
                            GradientStop { position: 0; color: "#4DB4A0" }
                            GradientStop { position: 1; color: "#245A50" }
                        }
                        Text {
                            anchors.centerIn: parent
                            anchors.verticalCenterOffset: -2
                            text: (root.firstName || "M").charAt(0).toUpperCase()
                            color: root.paper
                            font.family: "Fraunces 72pt SuperSoft"
                            font.pixelSize: 34
                        }
                    }
                    Image {
                        id: face
                        anchors.fill: parent
                        anchors.margins: 3
                        visible: false
                        asynchronous: true
                        fillMode: Image.PreserveAspectCrop
                        sourceSize.width: width * 2
                        sourceSize.height: height * 2
                        source: kuser.faceIconUrl
                    }
                    Item {
                        id: faceMask
                        anchors.fill: face
                        visible: false
                        layer.enabled: true
                        Rectangle { anchors.fill: parent; radius: width / 2 }
                    }
                    MultiEffect {
                        anchors.fill: face
                        source: face
                        visible: avatar.hasFace
                        maskEnabled: true
                        maskSource: faceMask
                        maskThresholdMin: 0.5
                        maskSpreadAtMin: 1
                    }
                }

                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: root.choosing ? Kirigami.Units.smallSpacing : 0
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                    color: root.ink
                    font.family: "Fraunces 72pt SuperSoft"
                    font.italic: root.choosing
                    font.pixelSize: root.choosing ? 26 : 30
                    text: root.choosing ? (root.firstName ? i18nc("%1 is a first name", "See you soon, %1.", root.firstName) : i18n("See you soon."))
                        : root.restarting ? i18n("Restart now?")
                        : root.shuttingDown ? i18n("Shut down now?")
                        : i18n("Sign out now?")
                }

                Text {
                    Layout.fillWidth: true
                    Layout.maximumWidth: Kirigami.Units.gridUnit * 21
                    Layout.alignment: Qt.AlignHCenter
                    visible: !root.choosing
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                    color: root.dim
                    font.family: "Inter"
                    font.pixelSize: 14
                    lineHeight: 1.15
                    text: {
                        const save = i18n("Open apps close, so save your work first.")
                        if (!root.counting) {
                            return save
                        }
                        const left = root.restarting
                            ? (softwareUpdatePending ? i18np("Your PC installs its updates and restarts in 1 second.", "Your PC installs its updates and restarts in %1 seconds.", root.remaining)
                                                     : i18np("Your PC restarts in 1 second.", "Your PC restarts in %1 seconds.", root.remaining))
                            : root.shuttingDown
                            ? (softwareUpdatePending ? i18np("Your PC installs its updates and shuts down in 1 second.", "Your PC installs its updates and shuts down in %1 seconds.", root.remaining)
                                                     : i18np("Your PC shuts down in 1 second.", "Your PC shuts down in %1 seconds.", root.remaining))
                            : i18np("You'll be signed out in 1 second.", "You'll be signed out in %1 seconds.", root.remaining)
                        return left + "\n" + save
                    }
                }

                // What else happens: someone else signed in, or where the PC restarts to.
                Repeater {
                    model: [
                        otherSessions.count > 0 && (!root.choosing || maysd)
                            ? i18np("Someone else is signed in too. They lose anything they haven't saved.",
                                    "%1 other people are signed in too. They lose anything they haven't saved.", otherSessions.count) : "",
                        rebootToFirmwareSetup && (root.choosing || root.restarting)
                            ? (isUefi ? i18n("When it restarts, the PC opens its UEFI settings.") : i18n("When it restarts, the PC opens its firmware settings.")) : "",
                        rebootToBootLoaderMenu && (root.choosing || root.restarting) ? i18n("When it restarts, the PC opens its boot menu.") : "",
                        rebootToBootLoaderEntry !== "" && (root.choosing || root.restarting)
                            ? i18nc("%1 is what the PC starts next", "When it restarts, the PC starts %1.", rebootToBootLoaderEntry) : ""
                    ].filter(note => note !== "")
                    delegate: Text {
                        required property string modelData
                        Layout.fillWidth: true
                        Layout.maximumWidth: Kirigami.Units.gridUnit * 21
                        Layout.alignment: Qt.AlignHCenter
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        color: root.dim
                        font.family: "Inter"
                        font.italic: true
                        font.pixelSize: 13
                        text: modelData
                    }
                }

                // One question: Cancel, and the sun on the answer.
                RowLayout {
                    visible: !root.choosing
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: Kirigami.Units.gridUnit
                    spacing: Kirigami.Units.smallSpacing * 3

                    Pill {
                        id: cancelPill
                        text: i18n("Cancel")
                        ink: root.ink
                        tint: root.pebble
                        ring: root.lily
                        speed: root.speed
                        onClicked: root.cancelRequested()
                        Keys.onPressed: root.stopCounting()
                        KeyNavigation.right: goPill
                    }
                    Pill {
                        id: goPill
                        focus: !root.choosing
                        text: root.restarting ? (softwareUpdatePending ? i18n("Update and restart") : i18n("Restart"))
                            : root.shuttingDown ? (softwareUpdatePending ? i18n("Update and shut down") : i18n("Shut down"))
                            : i18n("Sign out")
                        ink: root.paper
                        tint: root.sun
                        ring: root.ink
                        speed: root.speed
                        onClicked: root.go()
                        Keys.onPressed: event => {
                            if (event.key !== Qt.Key_Return && event.key !== Qt.Key_Enter) {
                                root.stopCounting()
                            }
                        }
                        KeyNavigation.left: cancelPill
                    }
                }

                // Or the choices, each with its sign: the moon to sleep, the setting sun to shut down.
                RowLayout {
                    id: choices
                    visible: root.choosing
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: Kirigami.Units.gridUnit
                    spacing: Kirigami.Units.smallSpacing * 2

                    Choice {
                        id: sleepChoice
                        visible: spdMethods.SuspendState
                        sign: "system-suspend"
                        text: i18n("Sleep")
                        ink: root.ink
                        tint: root.pebble
                        ring: root.lily
                        speed: root.speed
                        onClicked: root.suspendRequested(2)
                    }
                    Choice {
                        visible: spdMethods.HibernateState
                        sign: "system-suspend-hibernate"
                        text: i18n("Hibernate")
                        ink: root.ink
                        tint: root.pebble
                        ring: root.lily
                        speed: root.speed
                        onClicked: root.suspendRequested(4)
                    }
                    Choice {
                        visible: maysd
                        sign: softwareUpdatePending ? "system-reboot-update" : "system-reboot"
                        text: softwareUpdatePending ? i18n("Update and restart") : i18n("Restart")
                        ink: root.ink
                        tint: root.pebble
                        ring: root.lily
                        speed: root.speed
                        onClicked: root.leave(() => softwareUpdatePending ? root.rebootUpdateRequested() : root.rebootRequested())
                    }
                    Choice {
                        id: shutDownChoice
                        visible: maysd
                        focus: root.choosing
                        sign: softwareUpdatePending ? "system-shutdown-update" : "system-shutdown"
                        text: softwareUpdatePending ? i18n("Update and shut down") : i18n("Shut down")
                        ink: root.ink
                        tint: root.pebble
                        ring: root.lily
                        speed: root.speed
                        onClicked: root.leave(() => softwareUpdatePending ? root.haltUpdateRequested() : root.haltRequested())
                    }
                    Choice {
                        visible: canLogout
                        sign: "system-log-out"
                        text: i18n("Sign out")
                        ink: root.ink
                        tint: root.pebble
                        ring: root.lily
                        speed: root.speed
                        onClicked: root.leave(() => root.logoutRequested())
                    }
                }

                QQC2.AbstractButton {
                    id: cancelChoice
                    visible: root.choosing
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: Kirigami.Units.smallSpacing
                    implicitWidth: cancelLabel.implicitWidth + 28
                    implicitHeight: 32
                    text: i18n("Cancel")
                    onClicked: root.cancelRequested()
                    Accessible.name: text
                    background: Rectangle {
                        radius: height / 2
                        color: cancelChoice.hovered || cancelChoice.visualFocus ? root.pebble : "transparent"
                        border.width: cancelChoice.visualFocus ? 2 : 0
                        border.color: root.lily
                    }
                    contentItem: Text {
                        id: cancelLabel
                        text: cancelChoice.text
                        color: root.dim
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.family: "Inter"
                        font.pixelSize: 14
                    }
                }
            }
        }
    }

    // Arrows move between the choices, as Tab does.
    Keys.onLeftPressed: event => {
        const item = Window.activeFocusItem ? Window.activeFocusItem.nextItemInFocusChain(false) : null
        if (item) {
            item.forceActiveFocus(Qt.BacktabFocusReason)
        }
        root.stopCounting()
    }
    Keys.onRightPressed: event => {
        const item = Window.activeFocusItem ? Window.activeFocusItem.nextItemInFocusChain(true) : null
        if (item) {
            item.forceActiveFocus(Qt.TabFocusReason)
        }
        root.stopCounting()
    }

    // The sun sets: the screen fades to night before the PC goes.
    Rectangle {
        id: night
        anchors.fill: parent
        color: "#05070E"
        opacity: 0
        visible: opacity > 0
    }
    SequentialAnimation {
        id: sunset
        property var action: null
        NumberAnimation {
            target: night
            property: "opacity"
            to: 1
            duration: Math.round(900 * root.speed)
            easing.type: Easing.Bezier
            easing.bezierCurve: [0.4, 0, 0.2, 1, 1, 1]
        }
        ScriptAction {
            script: sunset.action()
        }
    }

    // A pill: Cancel on a pebble of glass, or the answer on the sun.
    component Pill: QQC2.AbstractButton {
        id: pill
        property color ink
        property color tint
        property color ring
        property real speed: 1
        implicitWidth: Math.max(label.implicitWidth + 44, 112)
        implicitHeight: 42
        activeFocusOnTab: true
        Accessible.name: text
        Keys.onEnterPressed: clicked()
        Keys.onReturnPressed: clicked()
        scale: down ? 0.95 : hovered ? 1.04 : 1
        Behavior on scale { NumberAnimation { duration: Math.round(160 * pill.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }
        background: Rectangle {
            radius: height / 2
            color: pill.tint
            border.width: pill.visualFocus ? 2 : 0
            border.color: pill.ring
        }
        contentItem: Text {
            id: label
            text: pill.text
            color: pill.ink
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.family: "Inter"
            font.pixelSize: 15
            font.weight: Font.DemiBold
        }
    }

    // A choice: its sign on a round pebble of glass, its name below.
    component Choice: QQC2.AbstractButton {
        id: choice
        property string sign
        property color ink
        property color tint
        property color ring
        property real speed: 1
        implicitWidth: 92
        implicitHeight: 104
        activeFocusOnTab: true
        Accessible.name: text
        Keys.onEnterPressed: clicked()
        Keys.onReturnPressed: clicked()
        background: Item {}
        contentItem: ColumnLayout {
            spacing: 8
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                implicitWidth: 64
                implicitHeight: 64
                radius: 32
                color: choice.hovered || choice.visualFocus ? Qt.rgba(choice.tint.r, choice.tint.g, choice.tint.b, Math.min(1, choice.tint.a * 2.2)) : choice.tint
                border.width: choice.visualFocus ? 2 : 0
                border.color: choice.ring
                scale: choice.down ? 0.93 : choice.hovered ? 1.06 : 1
                Behavior on scale { NumberAnimation { duration: Math.round(160 * choice.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }
                Kirigami.Icon {
                    anchors.centerIn: parent
                    width: 30
                    height: 30
                    source: choice.sign
                    color: choice.ink
                }
            }
            Text {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                text: choice.text
                color: choice.ink
                font.family: "Inter"
                font.pixelSize: 13
            }
        }
    }
}
