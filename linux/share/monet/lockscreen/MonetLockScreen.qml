/*
 * Monet's lock screen: the painting with its placard beside it, like a
 * museum after hours. A key or the mouse softens the painting and raises a
 * sheet of glass with your name, a well for the password and the sun to go
 * back in.
 *
 * Opened by LockScreen.qml from Plasma's desktop shell, so KDE's files there
 * (MediaControls.qml, LockOsd.qml, the PasswordSync singleton) are its
 * neighbours. Everything that unlocks (the authenticator, the timers, the
 * grace lock, the keyboard) works the way KDE's LockScreenUi.qml does.
 */
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Shapes

import org.kde.plasma.components as PlasmaComponents3
import org.kde.plasma.extras as PlasmaExtras
import org.kde.plasma.workspace.components as PW
import org.kde.plasma.private.keyboardindicator as KeyboardIndicator
import org.kde.plasma.private.sessions
import org.kde.kirigami as Kirigami
import org.kde.kscreenlocker as ScreenLocker
import org.kde.breeze.components

Item {
    id: monetLock
    focus: true

    // If we're using software rendering, there's no blur: a heavier wash instead.
    readonly property bool softwareRendering: GraphicsInfo.api === GraphicsInfo.Software
    readonly property real speed: Kirigami.Units.longDuration / 200
    // Mist or smoke, the way monet-light set the colors.
    readonly property bool smoke: Kirigami.Theme.backgroundColor.hslLightness < 0.5
    readonly property color ink: smoke ? "#EFECE6" : "#1C1B19"
    readonly property color dim: smoke ? "#B4AEA5" : "#6B665E"
    readonly property color glass: smoke ? Qt.rgba(0.141, 0.137, 0.129, 0.76) : Qt.rgba(0.969, 0.961, 0.945, 0.74)
    readonly property color hairline: smoke ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(0, 0, 0, 0.09)
    readonly property color sun: "#F2552C"
    readonly property color paper: "#FBF7EE"
    readonly property var settings: typeof config === "undefined" || !config
        ? ({ alwaysShowClock: true, hideClockWhenIdle: false, showMediaControls: true }) : config

    property date now: new Date()
    // Same hours as the wallpaper and the placard on the desktop.
    readonly property string light: {
        const h = now.getHours()
        return h >= 5 && h < 10 ? "dawn" : h >= 10 && h < 17 ? "midday" : h >= 17 && h < 21 ? "dusk" : "night"
    }
    readonly property string userName: String(typeof kscreenlocker_userName === "undefined" ? "" : kscreenlocker_userName)
    readonly property string userImage: String(typeof kscreenlocker_userImage === "undefined" ? "" : kscreenlocker_userImage)
    readonly property string firstName: userName.trim().split(" ")[0]
    readonly property string timeText: Qt.formatTime(now, Qt.locale().timeFormat(Locale.ShortFormat))

    function handleMessage(msg) {
        if (!msg) {
            return;
        }
        if (!root.notification) {
            root.notification += msg;
        } else if (root.notification.includes(msg)) {
            root.notificationRepeated();
        } else {
            root.notification += "\n" + msg
        }
    }

    Connections {
        target: authenticator
        function onFailed(kind) {
            if (kind != 0) { // if this is coming from the noninteractive authenticators
                return;
            }
            monetLock.handleMessage(i18ndc("plasma_shell_org.kde.plasma.desktop", "@info:status", "Unlocking failed"));
            graceLockTimer.restart();
            notificationRemoveTimer.restart();
            rejectPasswordAnimation.start();
        }

        function onSucceeded() {
            if (authenticator.hadPrompt) {
                Qt.quit();
            } else {
                // Nothing to type (no password on this account): one button to go back in.
                block.open = true;
                openButton.forceActiveFocus();
            }
        }

        function onInfoMessageChanged() {
            monetLock.handleMessage(authenticator.infoMessage);
        }

        function onErrorMessageChanged() {
            monetLock.handleMessage(authenticator.errorMessage);
        }

        function onPromptChanged(msg) {
            monetLock.handleMessage(authenticator.prompt);
        }

        function onPromptForSecretChanged(msg) {
            passwordBox.showPassword = false;
            passwordBox.forceActiveFocus();
        }
    }

    SessionManagement {
        id: sessionManagement
    }

    KeyboardIndicator.KeyState {
        id: capsLockState
        key: Qt.Key_CapsLock
    }

    Connections {
        target: sessionManagement
        function onAboutToSuspend() {
            root.clearPassword();
        }
    }

    RejectPasswordAnimation {
        id: rejectPasswordAnimation
        target: sheet
    }

    Timer {
        // The time, on the minute.
        interval: (60 - monetLock.now.getSeconds()) * 1000 + 50
        running: true
        repeat: true
        onTriggered: {
            monetLock.now = new Date()
            interval = (60 - monetLock.now.getSeconds()) * 1000 + 50
        }
    }

    MouseArea {
        id: lockScreenRoot

        property bool uiVisible: false
        property bool seenPositionChange: false
        property bool blockUI: containsMouse && (passwordBox.text.length > 0 || inputPanel.keyboardActive)

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: uiVisible ? Qt.ArrowCursor : Qt.BlankCursor
        drag.filterChildren: true
        onPressed: uiVisible = true;
        onPositionChanged: {
            uiVisible = seenPositionChange;
            seenPositionChange = true;
        }
        onUiVisibleChanged: {
            if (uiVisible) {
                Window.window.requestActivate();
            }

            if (blockUI) {
                fadeoutTimer.running = false;
            } else if (uiVisible) {
                fadeoutTimer.restart();
            }
            authenticator.startAuthenticating();
        }
        onBlockUIChanged: {
            if (blockUI) {
                fadeoutTimer.running = false;
                uiVisible = true;
            } else {
                fadeoutTimer.restart();
            }
        }
        onExited: {
            uiVisible = false;
        }
        Keys.onEscapePressed: {
            // If the escape key is pressed, kscreenlocker will turn off the screen.
            // We do not want to show the password prompt in this case.
            if (uiVisible) {
                uiVisible = false;
                if (inputPanel.keyboardActive) {
                    inputPanel.showHide();
                }
                root.clearPassword();
            }
        }
        Keys.onPressed: event => {
            uiVisible = true;
            event.accepted = false;
        }

        Timer {
            // MediaControls.qml stops this one by its id while you use it.
            id: fadeoutTimer
            interval: 10000
            onTriggered: {
                if (!lockScreenRoot.blockUI) {
                    passwordBox.showPassword = false;
                    lockScreenRoot.uiVisible = false;
                }
            }
        }
        Timer {
            id: notificationRemoveTimer
            interval: 3000
            onTriggered: root.notification = ""
        }
        Timer {
            id: graceLockTimer
            interval: 3000
            onTriggered: {
                root.clearPassword();
                authenticator.startAuthenticating();
            }
        }

        PropertyAnimation {
            id: launchAnimation
            target: lockScreenRoot
            property: "opacity"
            from: 0
            to: 1
            duration: Kirigami.Units.veryLongDuration * 2
        }

        Component.onCompleted: launchAnimation.start();

        // The painting (kscreenlocker puts it behind everything), softened
        // while the sheet is up, and washed in mist or smoke.
        MultiEffect {
            anchors.fill: parent
            source: typeof wallpaper === "undefined" ? null : wallpaper
            visible: !monetLock.softwareRendering && opacity > 0
            autoPaddingEnabled: false
            blurEnabled: true
            blurMax: 64
            blur: 1
            saturation: 0.2
            opacity: lockScreenRoot.uiVisible ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Math.round(380 * monetLock.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] } }
        }
        Rectangle {
            anchors.fill: parent
            readonly property color tone: monetLock.smoke ? "#14131A" : "#F3F1EC"
            color: Qt.rgba(tone.r, tone.g, tone.b, monetLock.softwareRendering ? 0.7 : (monetLock.smoke ? 0.3 : 0.22))
            opacity: lockScreenRoot.uiVisible ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Math.round(380 * monetLock.speed) } }
        }

        // At rest: the placard, as on the desktop, low on the left.
        ColumnLayout {
            id: placard
            readonly property bool ink: monetLock.light === "midday"  // the midday sky is bright
            readonly property color textColor: ink ? "#13202E" : "#FFFFFF"
            anchors.left: parent.left
            anchors.bottom: parent.bottom
            anchors.leftMargin: Kirigami.Units.gridUnit * 4
            anchors.bottomMargin: Kirigami.Units.gridUnit * 4
            spacing: 0
            visible: monetLock.settings.alwaysShowClock && !monetLock.settings.hideClockWhenIdle && opacity > 0
            opacity: lockScreenRoot.uiVisible ? 0 : 1
            Behavior on opacity { NumberAnimation { duration: Math.round(380 * monetLock.speed) } }
            layer.enabled: !monetLock.softwareRendering
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowColor: placard.ink ? "#B0FFFFFF" : "#9914102A"
                shadowBlur: 0.9
                shadowVerticalOffset: 2
            }

            Text {
                text: Qt.formatDate(monetLock.now, "dddd, d MMMM")
                color: placard.textColor
                opacity: 0.88
                font.family: "Inter"
                font.pixelSize: 17
                font.weight: Font.Medium
                font.letterSpacing: 0.2
            }

            Text {
                text: monetLock.timeText
                color: placard.textColor
                font.family: "Fraunces 72pt SuperSoft"
                font.weight: Font.Light
                font.pixelSize: 148
                font.letterSpacing: -5
                Layout.leftMargin: -6
                Layout.topMargin: -6
                Layout.bottomMargin: -8
            }

            RowLayout {
                spacing: 12
                opacity: 0.9

                Item {
                    implicitWidth: 26
                    implicitHeight: 14
                    Rectangle { x: 9; y: 0; width: 8; height: 8; radius: 4; color: monetLock.sun }
                    Rectangle { x: 3; y: 10; width: 20; height: 2.4; radius: 1.2; color: monetLock.sun; opacity: 0.8 }
                }

                Text {
                    text: i18nc("the wallpaper's name, after Monet's Impression, soleil levant", "Impression, %1", monetLock.light)
                    color: placard.textColor
                    font.family: "Fraunces 72pt SuperSoft"
                    font.italic: true
                    font.pixelSize: 22
                }
            }
        }

        QQC2.StackView {
            id: mainStack
            anchors {
                left: parent.left
                right: parent.right
            }
            height: lockScreenRoot.height
            focus: true // StackView is an implicit focus scope, so we need to give this focus so the item inside will have it

            // this isn't implicit, otherwise items still get processed for the scenegraph
            visible: opacity > 0
            opacity: lockScreenRoot.uiVisible ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Math.round(380 * monetLock.speed); easing.type: Easing.OutCubic } }

            initialItem: FocusScope {
                id: block
                focus: true
                enabled: !graceLockTimer.running

                // No password on this account: unlocked already, one button to go in.
                property bool open: false
                // Where the on-screen keyboard must not cover (VirtualKeyboardLoader).
                readonly property real visibleBoundary: rise.y + rise.height

                function startLogin() {
                    const password = passwordBox.text

                    // This is partly because it looks nicer, but more importantly it
                    // works round a Qt bug that can trigger if the app is closed with a
                    // TextField focused.
                    //
                    // See https://bugreports.qt.io/browse/QTBUG-55460
                    sunButton.forceActiveFocus();
                    authenticator.respond(password);
                }

                Item {
                    // The sheet rises into place each time it shows.
                    id: rise
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: Math.round((parent.height - height) / 2) + (lockScreenRoot.uiVisible ? 0 : Kirigami.Units.gridUnit * 1.5)
                    width: sheet.width
                    height: sheet.height
                    Behavior on y { NumberAnimation { duration: Math.round(380 * monetLock.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] } }

                    Rectangle {
                        id: sheet
                        readonly property int pad: Kirigami.Units.gridUnit * 2
                        width: Math.min(lockScreenRoot.width - Kirigami.Units.gridUnit * 2, Kirigami.Units.gridUnit * 23)
                        height: content.implicitHeight + pad * 2
                        radius: 22
                        color: monetLock.glass
                        border.width: 1
                        border.color: monetLock.hairline
                        layer.enabled: !monetLock.softwareRendering
                        layer.effect: MultiEffect {
                            shadowEnabled: true
                            shadowColor: monetLock.smoke ? "#99000000" : "#661C1B19"
                            shadowBlur: 1
                            shadowVerticalOffset: 10
                        }

                        ColumnLayout {
                            id: content
                            anchors.fill: parent
                            anchors.margins: sheet.pad
                            spacing: Kirigami.Units.smallSpacing * 2

                            // Your face, or your initial on a dab of lily.
                            Item {
                                id: avatar
                                Layout.alignment: Qt.AlignHCenter
                                implicitWidth: 88
                                implicitHeight: 88
                                readonly property bool hasFace: face.status === Image.Ready && !monetLock.softwareRendering

                                Rectangle {
                                    anchors.fill: parent
                                    radius: width / 2
                                    color: monetLock.paper
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
                                        text: (monetLock.firstName || "M").charAt(0).toUpperCase()
                                        color: monetLock.paper
                                        font.family: "Fraunces 72pt SuperSoft"
                                        font.pixelSize: 40
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
                                    source: monetLock.userImage !== ""
                                        ? "file://" + monetLock.userImage.split("/").map(encodeURIComponent).join("/") : ""
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
                                Layout.topMargin: Kirigami.Units.smallSpacing
                                horizontalAlignment: Text.AlignHCenter
                                text: monetLock.firstName ? i18nc("%1 is a first name", "Welcome back, %1.", monetLock.firstName) : i18n("Welcome back.")
                                color: monetLock.ink
                                elide: Text.ElideRight
                                font.family: "Fraunces 72pt SuperSoft"
                                font.italic: true
                                font.pixelSize: 26
                            }

                            Text {
                                Layout.fillWidth: true
                                visible: monetLock.settings.alwaysShowClock
                                horizontalAlignment: Text.AlignHCenter
                                text: monetLock.timeText + "  ·  " + Qt.formatDate(monetLock.now, "dddd, d MMMM")
                                color: monetLock.dim
                                font.family: "Inter"
                                font.pixelSize: 13
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                Layout.topMargin: Kirigami.Units.gridUnit
                                spacing: Kirigami.Units.smallSpacing * 2
                                visible: !block.open

                                PlasmaExtras.PasswordField {
                                    id: passwordBox
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 40
                                    font.pointSize: Kirigami.Theme.defaultFont.pointSize + 1
                                    text: PasswordSync.password
                                    placeholderText: i18ndc("plasma_shell_org.kde.plasma.desktop", "@info:placeholder in text field", "Password")
                                    focus: true
                                    enabled: !authenticator.graceLocked

                                    // In Qt this is implicitly active based on focus rather than visibility
                                    // in any other application having a focussed invisible object would be weird
                                    // but here we are using to wake out of screensaver mode
                                    // We need to explicitly disable cursor flashing to avoid unnecessary renders
                                    cursorVisible: visible

                                    onAccepted: {
                                        if (lockScreenRoot.uiVisible) {
                                            block.startLogin();
                                        }
                                    }

                                    Connections {
                                        target: root
                                        function onClearPassword() {
                                            passwordBox.forceActiveFocus()
                                            passwordBox.text = "";
                                            passwordBox.text = Qt.binding(() => PasswordSync.password);
                                        }
                                        function onNotificationRepeated() {
                                            bounce.start();
                                        }
                                    }
                                }
                                Binding {
                                    target: PasswordSync
                                    property: "password"
                                    value: passwordBox.text
                                }

                                // The sun: the one thing to do next.
                                QQC2.AbstractButton {
                                    id: sunButton
                                    Layout.preferredWidth: 40
                                    Layout.preferredHeight: 40
                                    focusPolicy: Qt.StrongFocus
                                    Accessible.name: i18ndc("plasma_shell_org.kde.plasma.desktop", "@action:button accessible only", "Unlock")
                                    onClicked: block.startLogin()
                                    Keys.onEnterPressed: clicked()
                                    Keys.onReturnPressed: clicked()
                                    scale: down ? 0.92 : hovered ? 1.06 : 1
                                    Behavior on scale { NumberAnimation { duration: Math.round(160 * monetLock.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }

                                    background: Rectangle {
                                        radius: height / 2
                                        color: sunButton.down ? "#D9431E" : monetLock.sun
                                        border.width: sunButton.visualFocus ? 2 : 0
                                        border.color: monetLock.ink
                                    }
                                    contentItem: Shape {
                                        preferredRendererType: Shape.CurveRenderer
                                        ShapePath {
                                            strokeColor: monetLock.paper
                                            strokeWidth: 2.4
                                            fillColor: "transparent"
                                            capStyle: ShapePath.RoundCap
                                            joinStyle: ShapePath.RoundJoin
                                            PathPolyline {
                                                path: LayoutMirroring.enabled
                                                    ? [Qt.point(26, 20), Qt.point(14, 20), Qt.point(19.5, 14.5), Qt.point(14, 20), Qt.point(19.5, 25.5)]
                                                    : [Qt.point(14, 20), Qt.point(26, 20), Qt.point(20.5, 14.5), Qt.point(26, 20), Qt.point(20.5, 25.5)]
                                            }
                                        }
                                    }
                                }
                            }

                            QQC2.AbstractButton {
                                id: openButton
                                Layout.alignment: Qt.AlignHCenter
                                Layout.topMargin: Kirigami.Units.gridUnit
                                visible: block.open
                                implicitWidth: openLabel.implicitWidth + 48
                                implicitHeight: 40
                                text: i18ndc("plasma_shell_org.kde.plasma.desktop", "@action:button no-password unlock", "Unlock")
                                onClicked: Qt.quit()
                                Keys.onEnterPressed: clicked()
                                Keys.onReturnPressed: clicked()
                                background: Rectangle {
                                    radius: height / 2
                                    color: openButton.down ? "#D9431E" : monetLock.sun
                                    border.width: openButton.visualFocus ? 2 : 0
                                    border.color: monetLock.ink
                                }
                                contentItem: Text {
                                    id: openLabel
                                    text: openButton.text
                                    color: monetLock.paper
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    font.family: "Inter"
                                    font.pixelSize: 15
                                    font.weight: Font.DemiBold
                                }
                            }

                            // Caps Lock, a wrong password, a message from the system.
                            Text {
                                id: message
                                Layout.fillWidth: true
                                Layout.minimumHeight: font.pixelSize * 1.4
                                horizontalAlignment: Text.AlignHCenter
                                wrapMode: Text.WordWrap
                                textFormat: Text.PlainText
                                color: monetLock.dim
                                font.family: "Inter"
                                font.italic: true
                                font.pixelSize: 13
                                text: {
                                    const parts = [];
                                    if (capsLockState.locked) {
                                        parts.push(i18ndc("plasma_shell_org.kde.plasma.desktop", "@info:status", "Caps Lock is on"));
                                    }
                                    if (root.notification) {
                                        parts.push(root.notification);
                                    }
                                    return parts.join(" • ");
                                }

                                SequentialAnimation {
                                    id: bounce
                                    NumberAnimation { target: message; property: "scale"; to: 1.08; duration: Math.round(160 * monetLock.speed); easing.type: Easing.OutQuad }
                                    NumberAnimation { target: message; property: "scale"; to: 1; duration: Math.round(200 * monetLock.speed); easing.type: Easing.InQuad }
                                }
                            }

                            // Fingerprint readers and smartcards work too.
                            Text {
                                readonly property int ways: authenticator.authenticatorTypes || 0
                                Layout.fillWidth: true
                                visible: (ways & (ScreenLocker.Authenticator.Fingerprint | ScreenLocker.Authenticator.Smartcard)) !== 0
                                horizontalAlignment: Text.AlignHCenter
                                wrapMode: Text.WordWrap
                                color: monetLock.dim
                                font.family: "Inter"
                                font.pixelSize: 12
                                text: (ways & ScreenLocker.Authenticator.Fingerprint)
                                    ? i18ndc("plasma_shell_org.kde.plasma.desktop", "@info:usagetip", "(or scan your fingerprint on the reader)")
                                    : i18ndc("plasma_shell_org.kde.plasma.desktop", "@info:usagetip", "(or scan your smartcard)")
                            }

                            Loader {
                                Layout.fillWidth: true
                                Layout.preferredHeight: item ? item.implicitHeight : 0
                                active: monetLock.settings.showMediaControls
                                source: "MediaControls.qml"
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.topMargin: Kirigami.Units.smallSpacing
                                implicitHeight: 1
                                color: monetLock.hairline
                                visible: actions.visibleChildren.length > 0
                            }

                            RowLayout {
                                id: actions
                                Layout.alignment: Qt.AlignHCenter
                                spacing: Kirigami.Units.smallSpacing

                                // KDE's labels mark a shortcut letter with "&"; these buttons show text as it is.
                                PlasmaComponents3.ToolButton {
                                    text: i18ndc("plasma_shell_org.kde.plasma.desktop", "@action:button", "Slee&p").replace("&", "")
                                    icon.name: "system-suspend"
                                    display: QQC2.AbstractButton.TextBesideIcon
                                    onClicked: sessionManagement.suspend()
                                    visible: sessionManagement.canSuspend
                                }
                                PlasmaComponents3.ToolButton {
                                    text: i18ndc("plasma_shell_org.kde.plasma.desktop", "@action:button", "&Hibernate").replace("&", "")
                                    icon.name: "system-suspend-hibernate"
                                    display: QQC2.AbstractButton.TextBesideIcon
                                    onClicked: sessionManagement.hibernate()
                                    visible: sessionManagement.canHibernate
                                }
                                PlasmaComponents3.ToolButton {
                                    text: i18ndc("plasma_shell_org.kde.plasma.desktop", "@action:button", "Switch &User").replace("&", "")
                                    icon.name: "system-switch-user"
                                    display: QQC2.AbstractButton.TextBesideIcon
                                    onClicked: sessionManagement.switchUser()
                                    visible: sessionManagement.canSwitchUser
                                }
                            }
                        }
                    }
                }

                Component.onCompleted: passwordBox.forceActiveFocus()
            }
        }

        VirtualKeyboardLoader {
            id: inputPanel

            z: 1

            screenRoot: lockScreenRoot
            mainStack: mainStack
            mainBlock: block
            passwordField: passwordBox
        }

        Loader {
            z: 2
            active: root.viewVisible
            source: "LockOsd.qml"
            anchors {
                horizontalCenter: parent.horizontalCenter
                bottom: parent.bottom
                bottomMargin: Kirigami.Units.gridUnit
            }
        }

        // The keyboard, its layout and the battery, along the foot.
        RowLayout {
            id: footer
            anchors {
                bottom: parent.bottom
                left: parent.left
                right: parent.right
                margins: Kirigami.Units.smallSpacing
            }
            spacing: Kirigami.Units.smallSpacing
            opacity: lockScreenRoot.uiVisible ? 1 : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: Math.round(380 * monetLock.speed) } }

            PlasmaComponents3.ToolButton {
                id: virtualKeyboardButton

                focusPolicy: Qt.TabFocus
                text: i18ndc("plasma_shell_org.kde.plasma.desktop", "Button to show/hide virtual keyboard", "Virtual Keyboard")
                icon.name: inputPanel.keyboardActive ? "input-keyboard-virtual-on" : "input-keyboard-virtual-off"
                onClicked: {
                    // Otherwise the password field loses focus and virtual keyboard
                    // keystrokes get eaten
                    passwordBox.forceActiveFocus();
                    inputPanel.showHide()
                }

                visible: inputPanel.status === Loader.Ready
                Layout.fillHeight: true
            }

            PlasmaComponents3.ToolButton {
                id: keyboardButton

                focusPolicy: Qt.TabFocus
                Accessible.description: i18ndc("plasma_shell_org.kde.plasma.desktop", "Button to change keyboard layout", "Switch layout")
                icon.name: "input-keyboard"

                PW.KeyboardLayoutSwitcher {
                    id: keyboardLayoutSwitcher

                    anchors.fill: parent
                    acceptedButtons: Qt.NoButton
                }

                text: keyboardLayoutSwitcher.layoutNames.longName
                onClicked: keyboardLayoutSwitcher.keyboardLayout.switchToNextLayout()

                visible: keyboardLayoutSwitcher.hasMultipleKeyboardLayouts
                Layout.fillHeight: true
            }

            Item {
                Layout.fillWidth: true
            }

            Battery {}
        }
    }
}
