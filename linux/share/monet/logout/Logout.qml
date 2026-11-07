// SPDX-License-Identifier: GPL-3.0-or-later
// Plasma owns the session, updates and power policy. This page emits its signals.
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Window
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.sessions
import "timer.js" as AutoTriggerTimer

FocusScope {
    id: root
    objectName: "MonetPowerScreen"
    focus: true
    width: typeof screenGeometry === "undefined" ? 1440 : screenGeometry.width
    height: typeof screenGeometry === "undefined" ? 900 : screenGeometry.height
    LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
    LayoutMirroring.childrenInherit: true

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
    signal showApplicationsRequested()

    readonly property bool softwareRendering: GraphicsInfo.api === GraphicsInfo.Software
    readonly property bool smoke: Kirigami.Theme.backgroundColor.hslLightness < 0.5
    readonly property real speed: Kirigami.Units.longDuration / 200
    property real fontScale: Math.max(1, Kirigami.Theme.defaultFont.pointSize / 11)
    readonly property color ink: smoke ? "#EFECE6" : "#1C1B19"
    readonly property color dim: smoke ? "#B4AEA5" : "#6B665E"
    readonly property color paper: "#FBF7EE"
    readonly property color panel: smoke ? "#292824" : "#F7F5EF"
    readonly property color hairline: smoke ? "#49473F" : "#DFDBD1"
    readonly property color pebble: smoke ? "#33322D" : "#EFEBE2"
    readonly property color lily: smoke ? "#73C7B3" : "#357F72"
    readonly property color sun: "#F2552C"
    readonly property bool compact: height < 640 || width < 520
    readonly property bool choosing: sdtype === ShutdownType.ShutdownTypeDefault
    readonly property bool restarting: sdtype === ShutdownType.ShutdownTypeReboot
    readonly property bool shuttingDown: sdtype === ShutdownType.ShutdownTypeHalt
    readonly property bool permitted: restarting || shuttingDown ? maysd : canLogout
    property int remaining: 30
    property bool counting: !choosing && permitted
    property bool leaving: false
    property string transitionMessage: ""
    property var countdownCallback: null
    property bool offerApplicationReview: false
    Timer { interval: 4000; running: root.leaving; onTriggered: root.offerApplicationReview = true }

    function stopCounting() { AutoTriggerTimer.cancelAutoTrigger() }

    function showLeaving(message) {
        leaving = true
        transitionMessage = message || i18nd("monet", "Signing out…")
        night.opacity = 1
    }

    function leave(action, message) {
        if (leaving || !AutoTriggerTimer.beginAction(countdownCallback)) return
        leaving = true
        transitionMessage = message || (restarting ? i18nd("monet", "Restarting…") : shuttingDown ? i18nd("monet", "Shutting down…") : i18nd("monet", "Signing out…"))
        sunset.action = action
        sunset.start()
    }

    function go() {
        if (!permitted) return
        if (restarting) leave(() => softwareUpdatePending ? root.rebootUpdateRequested() : root.rebootRequested())
        else if (shuttingDown) leave(() => softwareUpdatePending ? root.haltUpdateRequested() : root.haltRequested())
        else leave(() => root.logoutRequested())
    }

    function goWithoutUpdates() {
        if (!maysd) return
        leave(() => restarting ? root.rebootRequested() : root.haltRequested())
    }

    function reveal(item) {
        if (!item || !item.visible || !item.enabled) return
        let ancestor = item
        while (ancestor && ancestor !== scrollBody) ancestor = ancestor.parent
        if (!ancestor) return
        const point = item.mapToItem(scrollBody, 0, 0)
        const margin = 8
        let position = scroller.contentY
        if (point.y < position + margin) position = point.y - margin
        else if (point.y + item.height > position + scroller.height - margin)
            position = point.y + item.height - scroller.height + margin
        scroller.contentY = Math.max(0, Math.min(Math.max(0, scroller.contentHeight - scroller.height), position))
    }

    function buttons() {
        return [sleepChoice, hibernateChoice, restartChoice, plainRestartChoice,
                shutDownChoice, plainShutDownChoice, logoutChoice,
                goPill, plainGo, cancelChoice].filter(item => item.visible && item.enabled)
    }

    function handleKey(event, item) {
        stopCounting()
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            if (item.enabled) item.clicked()
            event.accepted = true
        } else if ([Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down].includes(event.key)) {
            const order = buttons()
            if (!order.length) return
            let step = event.key === Qt.Key_Up || event.key === Qt.Key_Left ? -1 : 1
            if ((event.key === Qt.Key_Left || event.key === Qt.Key_Right) && root.LayoutMirroring.enabled) step *= -1
            if (choosing && (event.key === Qt.Key_Up || event.key === Qt.Key_Down)) step *= choices.columns
            const index = Math.max(0, order.indexOf(item))
            order[(index + step + order.length) % order.length].forceActiveFocus(Qt.TabFocusReason)
            event.accepted = true
        } else event.accepted = false
    }

    Component.onCompleted: {
        countdownCallback = () => { root.counting = false }
        AutoTriggerTimer.addCancelAutoTriggerCallback(countdownCallback)
        Qt.callLater(() => {
            const preferred = choosing ? shutDownChoice : goPill
            if (preferred.visible && preferred.enabled) preferred.forceActiveFocus(Qt.TabFocusReason)
            else cancelChoice.forceActiveFocus(Qt.TabFocusReason)
        })
    }
    Component.onDestruction: AutoTriggerTimer.removeCancelAutoTriggerCallback(countdownCallback)

    SessionsModel {
        id: otherSessions
        includeUnusedSessions: false
        includeOwnSession: false
    }
    QQC2.Action {
        shortcut: "Escape"
        onTriggered: if (!root.leaving) { root.stopCounting(); root.cancelRequested() }
    }
    Keys.onPressed: event => { root.stopCounting(); event.accepted = false }
    Timer {
        interval: 1000
        repeat: true
        running: root.counting && !root.leaving
        onTriggered: if (--root.remaining <= 0) root.go()
    }

    Rectangle {
        anchors.fill: parent
        color: root.smoke ? "#151511" : "#E9E5DA"
        opacity: root.softwareRendering ? 0.94 : 0.70
    }
    MouseArea {
        anchors.fill: parent
        enabled: !root.leaving
        onClicked: { root.stopCounting(); root.cancelRequested() }
    }

    Rectangle {
        id: sheet
        objectName: "powerSheet"
        readonly property int pad: root.compact ? 22 : 34
        anchors.centerIn: parent
        width: Math.max(1, Math.min(680, root.width - (root.width < 480 ? 24 : 64)))
        height: Math.max(1, Math.min(root.height - 32, scrollBody.implicitHeight + footer.implicitHeight + pad * 2 + 20))
        radius: 24
        color: root.panel
        border.width: 1
        border.color: root.hairline
        enabled: !root.leaving
        layer.enabled: !root.softwareRendering
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: root.smoke ? "#80000000" : "#331C1B19"
            shadowBlur: 1
            shadowVerticalOffset: 12
        }
        MouseArea { anchors.fill: parent }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: sheet.pad
            spacing: 20
            QQC2.ScrollView {
                id: scrollView
                objectName: "powerScroll"
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: availableWidth
                // Keep the bar out of the cards' hover targets, including
                // when all content fits and Qt's transient bar is hidden.
                readonly property bool overflowing: scroller.contentHeight > scroller.height + 1
                rightPadding: overflowing ? Math.max(12, effectiveScrollBarWidth) + 6 : 0
                clip: true
                QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
                QQC2.ScrollBar.vertical.policy: overflowing ? QQC2.ScrollBar.AlwaysOn : QQC2.ScrollBar.AlwaysOff
                Flickable {
                    id: scroller
                    objectName: "powerFlickable"
                    contentWidth: width
                    contentHeight: scrollBody.implicitHeight
                    boundsBehavior: Flickable.StopAtBounds
                    flickableDirection: Flickable.VerticalFlick
                    clip: true
                    ColumnLayout {
                        id: scrollBody
                        width: scroller.width
                        spacing: root.compact ? 18 : 24
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            Rectangle { implicitWidth: 12; implicitHeight: 12; radius: 6; color: root.sun }
                            Text {
                                text: "Monet"
                                color: root.dim
                                font.family: "Inter"
                                font.pixelSize: 13 * root.fontScale
                                font.weight: Font.Medium
                                font.letterSpacing: 1.5
                            }
                            Item { Layout.fillWidth: true }
                            PowerMark {
                                visible: !root.choosing
                                kind: root.restarting ? "restart" : root.shuttingDown ? "shutdown" : "logout"
                                ink: root.sun
                                Layout.preferredWidth: 28
                                Layout.preferredHeight: 28
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 12
                            Text {
                                objectName: "powerHeading"
                                Layout.fillWidth: true
                                text: root.choosing ? i18nd("monet", "See you soon.")
                                    : root.restarting ? i18nd("monet", "Restart now?")
                                    : root.shuttingDown ? i18nd("monet", "Shut down now?") : i18nd("monet", "Sign out now?")
                                textFormat: Text.PlainText
                                wrapMode: Text.Wrap
                                color: root.ink
                                font.family: "Fraunces 72pt SuperSoft"
                                font.pixelSize: (root.compact ? 32 : 42) * root.fontScale
                                font.weight: Font.Light
                                font.italic: root.choosing
                            }
                            Text {
                                visible: root.choosing
                                Layout.fillWidth: true
                                text: i18nd("monet", "Power & Sleep")
                                color: root.dim
                                font.family: "Inter"
                                font.pixelSize: 14 * root.fontScale
                            }
                            Text {
                                objectName: "powerExplanation"
                                visible: !root.choosing
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                textFormat: Text.PlainText
                                color: root.dim
                                font.family: "Inter"
                                font.pixelSize: 14 * root.fontScale
                                lineHeight: 1.3
                                text: {
                                    const save = i18nd("monet", "Open apps close, so save your work first.")
                                    if (!root.counting) return save
                                    const left = root.restarting
                                        ? (softwareUpdatePending ? i18ndp("monet", "Your PC installs its updates and restarts in 1 second.", "Your PC installs its updates and restarts in %1 seconds.", root.remaining)
                                                                 : i18ndp("monet", "Your PC restarts in 1 second.", "Your PC restarts in %1 seconds.", root.remaining))
                                        : root.shuttingDown
                                        ? (softwareUpdatePending ? i18ndp("monet", "Your PC installs its updates and shuts down in 1 second.", "Your PC installs its updates and shuts down in %1 seconds.", root.remaining)
                                                                 : i18ndp("monet", "Your PC shuts down in 1 second.", "Your PC shuts down in %1 seconds.", root.remaining))
                                        : i18ndp("monet", "You'll be signed out in 1 second.", "You'll be signed out in %1 seconds.", root.remaining)
                                    return left + "\n" + save
                                }
                            }
                        }

                        Repeater {
                            model: [
                                otherSessions.count > 0 && (root.choosing || root.restarting || root.shuttingDown)
                                    ? i18ndp("monet", "Someone else is signed in too. They lose anything they haven't saved.", "%1 other people are signed in too. They lose anything they haven't saved.", otherSessions.count) : "",
                                rebootToFirmwareSetup && (root.choosing || root.restarting)
                                    ? (isUefi ? i18nd("monet", "When it restarts, the PC opens its setup screen (BIOS).") : i18nd("monet", "When it restarts, the PC opens its firmware settings.")) : "",
                                rebootToBootLoaderMenu && (root.choosing || root.restarting) ? i18nd("monet", "When it restarts, the PC opens its boot menu.") : "",
                                rebootToBootLoaderEntry !== "" && (root.choosing || root.restarting)
                                    ? i18ndc("monet", "%1 is what the PC starts next", "When it restarts, the PC starts %1.", rebootToBootLoaderEntry) : ""
                            ].filter(note => note !== "")
                            delegate: Text {
                                required property string modelData
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                textFormat: Text.PlainText
                                text: modelData
                                color: root.dim
                                font.family: "Inter"
                                font.pixelSize: 13 * root.fontScale
                                lineHeight: 1.25
                            }
                        }

                        GridLayout {
                            id: choices
                            objectName: "powerChoices"
                            visible: root.choosing
                            Layout.fillWidth: true
                            columns: width >= 440 ? 2 : 1
                            columnSpacing: 12
                            rowSpacing: 12
                            PowerCard {
                                powerPage: root
                                id: sleepChoice
                                objectName: "sleepChoice"
                                visible: spdMethods.SuspendState
                                text: i18nd("monet", "Sleep")
                                symbol: "sleep"
                                onClicked: root.suspendRequested(2)
                            }
                            PowerCard {
                                powerPage: root
                                id: hibernateChoice
                                objectName: "hibernateChoice"
                                visible: spdMethods.HibernateState
                                text: i18nd("monet", "Hibernate")
                                symbol: "hibernate"
                                onClicked: root.suspendRequested(4)
                            }
                            PowerCard {
                                powerPage: root
                                id: restartChoice
                                objectName: "restartChoice"
                                visible: maysd
                                text: softwareUpdatePending ? i18nd("monet", "Update and restart") : i18nd("monet", "Restart")
                                symbol: "restart"
                                onClicked: root.leave(() => softwareUpdatePending ? root.rebootUpdateRequested() : root.rebootRequested(), i18nd("monet", "Restarting…"))
                            }
                            PowerCard {
                                powerPage: root
                                id: plainRestartChoice
                                objectName: "plainRestartChoice"
                                visible: maysd && softwareUpdatePending
                                text: i18nd("monet", "Restart")
                                symbol: "restart"
                                onClicked: root.leave(() => root.rebootRequested(), i18nd("monet", "Restarting…"))
                            }
                            PowerCard {
                                powerPage: root
                                id: shutDownChoice
                                objectName: "shutDownChoice"
                                visible: maysd
                                text: softwareUpdatePending ? i18nd("monet", "Update and shut down") : i18nd("monet", "Shut down")
                                symbol: "shutdown"
                                warm: true
                                onClicked: root.leave(() => softwareUpdatePending ? root.haltUpdateRequested() : root.haltRequested(), i18nd("monet", "Shutting down…"))
                            }
                            PowerCard {
                                powerPage: root
                                id: plainShutDownChoice
                                objectName: "plainShutDownChoice"
                                visible: maysd && softwareUpdatePending
                                text: i18nd("monet", "Shut down")
                                symbol: "shutdown"
                                warm: true
                                onClicked: root.leave(() => root.haltRequested(), i18nd("monet", "Shutting down…"))
                            }
                            PowerCard {
                                powerPage: root
                                id: logoutChoice
                                objectName: "logoutChoice"
                                visible: canLogout
                                text: i18nd("monet", "Sign out")
                                symbol: "logout"
                                onClicked: root.leave(() => root.logoutRequested())
                            }
                        }

                        ColumnLayout {
                            visible: !root.choosing
                            Layout.fillWidth: true
                            spacing: 10
                            ActionPill {
                                powerPage: root
                                id: goPill
                                objectName: "goPill"
                                visible: root.permitted
                                primary: true
                                text: root.restarting ? (softwareUpdatePending ? i18nd("monet", "Update and restart") : i18nd("monet", "Restart"))
                                    : root.shuttingDown ? (softwareUpdatePending ? i18nd("monet", "Update and shut down") : i18nd("monet", "Shut down")) : i18nd("monet", "Sign out")
                                onClicked: root.go()
                            }
                            ActionPill {
                                powerPage: root
                                id: plainGo
                                objectName: "plainGo"
                                visible: maysd && softwareUpdatePending && (root.restarting || root.shuttingDown)
                                text: root.restarting ? i18nd("monet", "Restart") : i18nd("monet", "Shut down")
                                onClicked: root.goWithoutUpdates()
                            }
                        }
                    }
                }
            }
            ColumnLayout {
                id: footer
                Layout.fillWidth: true
                spacing: 16
                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: root.hairline }
                ActionPill {
                    powerPage: root
                    id: cancelChoice
                    objectName: "cancelChoice"
                    text: i18nd("monet", "Cancel")
                    shortcutHint: "Esc"
                    onClicked: { root.stopCounting(); root.cancelRequested() }
                }
            }
        }
    }

    Rectangle {
        id: night
        objectName: "monetSessionTransition"
        anchors.fill: parent
        color: root.smoke ? "#242321" : "#F3F1EC"
        opacity: 0
        visible: opacity > 0
        Column {
            anchors.centerIn: parent
            width: Math.min(parent.width - 48, 540)
            spacing: 22
            Image {
                anchors.horizontalCenter: parent.horizontalCenter
                source: Qt.resolvedUrl("monet.svg")
                width: 72; height: 72
                fillMode: Image.PreserveAspectFit
                smooth: true
            }
            Text {
                width: parent.width; text: "Monet"
                horizontalAlignment: Text.AlignHCenter
                color: root.ink; font.family: "Fraunces 72pt SuperSoft"; font.pixelSize: 44
            }
            Text {
                width: parent.width; text: root.transitionMessage
                horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
                color: root.dim; font.family: "Inter"; font.pixelSize: 17
            }
            QQC2.BusyIndicator {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 32; height: 32
                running: root.leaving && root.speed > 0
                visible: root.speed > 0
                palette.dark: root.lily
            }
            ActionPill {
                powerPage: root
                objectName: "showApplications"
                anchors.horizontalCenter: parent.horizontalCenter
                width: Math.min(parent.width, 260)
                visible: root.offerApplicationReview
                text: i18nd("monet", "Show applications")
                onClicked: root.showApplicationsRequested()
            }
        }
    }
    SequentialAnimation {
        id: sunset
        property var action: null
        NumberAnimation { target: night; property: "opacity"; to: 1; duration: Math.round(240 * root.speed); easing.type: Easing.OutCubic }
        ScriptAction { script: if (sunset.action) sunset.action() }
    }

    component PowerCard: QQC2.AbstractButton {
        id: card
        required property var powerPage
        property string symbol
        property bool warm: false
        readonly property color accent: warm ? powerPage.sun : powerPage.lily
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        implicitWidth: 240
        implicitHeight: Math.max(82, cardLabel.implicitHeight + 30)
        leftPadding: 16
        rightPadding: 16
        topPadding: 15
        bottomPadding: 15
        activeFocusOnTab: true
        hoverEnabled: true
        Accessible.name: text
        onActiveFocusChanged: if (activeFocus) Qt.callLater(() => powerPage.reveal(card))
        Keys.onPressed: event => powerPage.handleKey(event, card)
        background: Rectangle {
            radius: 16
            color: card.down ? Qt.tint(powerPage.pebble, Qt.rgba(card.accent.r, card.accent.g, card.accent.b, 0.18))
                : card.hovered || card.visualFocus ? Qt.tint(powerPage.pebble, Qt.rgba(card.accent.r, card.accent.g, card.accent.b, powerPage.smoke ? 0.13 : 0.08)) : powerPage.pebble
            border.width: card.visualFocus ? 2 : 1
            border.color: card.visualFocus ? card.accent : card.hovered ? Qt.rgba(card.accent.r, card.accent.g, card.accent.b, 0.5) : powerPage.hairline
        }
        contentItem: RowLayout {
            spacing: 14
            Rectangle {
                implicitWidth: 44
                implicitHeight: 44
                radius: 13
                color: Qt.rgba(card.accent.r, card.accent.g, card.accent.b, powerPage.smoke ? 0.12 : 0.10)
                PowerMark { anchors.centerIn: parent; width: 26; height: 26; kind: card.symbol; ink: card.accent }
            }
            Text {
                id: cardLabel
                Layout.fillWidth: true
                text: card.text
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                color: powerPage.ink
                font.family: "Inter"
                font.pixelSize: 15 * powerPage.fontScale
                font.weight: Font.Medium
            }
            PowerMark {
                Layout.preferredWidth: 16
                Layout.preferredHeight: 16
                kind: "arrow"
                ink: card.hovered || card.visualFocus ? card.accent : powerPage.dim
                rotation: powerPage.LayoutMirroring.enabled ? 180 : 0
            }
        }
    }

    component ActionPill: QQC2.AbstractButton {
        id: pill
        required property var powerPage
        property bool primary: false
        property string shortcutHint: ""
        Layout.fillWidth: true
        implicitHeight: Math.max(46, pillLabel.implicitHeight + 24)
        leftPadding: 18
        rightPadding: 18
        activeFocusOnTab: true
        hoverEnabled: true
        Accessible.name: text
        onActiveFocusChanged: if (activeFocus) Qt.callLater(() => powerPage.reveal(pill))
        Keys.onPressed: event => powerPage.handleKey(event, pill)
        background: Rectangle {
            radius: 13
            color: pill.primary ? powerPage.sun : pill.hovered || pill.down ? powerPage.pebble : "transparent"
            opacity: pill.down ? 0.85 : 1
            border.width: pill.visualFocus ? 2 : pill.primary ? 0 : 1
            border.color: pill.visualFocus ? powerPage.lily : powerPage.hairline
        }
        contentItem: RowLayout {
            Text {
                id: pillLabel
                Layout.fillWidth: true
                text: pill.text
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                horizontalAlignment: pill.shortcutHint ? Text.AlignLeft : Text.AlignHCenter
                color: pill.primary ? powerPage.paper : powerPage.ink
                font.family: "Inter"
                font.pixelSize: 14 * powerPage.fontScale
                font.weight: Font.Medium
            }
            Text {
                visible: pill.shortcutHint !== ""
                text: pill.shortcutHint
                color: powerPage.dim
                font.family: "Inter"
                font.pixelSize: 12 * powerPage.fontScale
            }
        }
    }
}
