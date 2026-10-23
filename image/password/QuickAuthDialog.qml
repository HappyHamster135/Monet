/*
 * Monet's password prompt: when an app needs more rights, a sheet of paper
 * (or smoke) says what it wants in plain words and asks for the password,
 * with Cancel and the sun to allow it. A wrong password shakes the sheet.
 *
 * Built into KDE's polkit agent in place of its own page (image/password/
 * build.sh), so the agent's C++ still does the work. It reads and sets these
 * by name: mainText and the description* properties, identitiesModel,
 * identitiesCurrentIndex, selectedIdentity, password, inlineMessageType and
 * inlineMessageText; it listens for accept(), reject() and userSelected(), and
 * calls show(), hide(), request() and authenticationFailure().
 */
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Shapes
import QtQuick.Templates as T
import QtQuick.Window
import org.kde.kirigami as Kirigami
import org.kde.polkitkde 1.0

Window {
    id: root
    title: i18nd("monet", "Monet needs your password")
    color: Kirigami.Theme.backgroundColor
    flags: Qt.Dialog

    width: intendedWidth
    height: intendedHeight
    minimumWidth: intendedWidth
    maximumWidth: intendedWidth
    minimumHeight: intendedHeight
    maximumHeight: intendedHeight

    property alias password: passwordField.text
    property int inlineMessageType: 0
    property string inlineMessageText
    property alias identitiesModel: identitiesCombo.model
    property alias identitiesCurrentIndex: identitiesCombo.currentIndex
    property alias selectedIdentity: identitiesCombo.currentValue

    property bool waitingForAuthentication: false

    // Passed in by the agent.
    property string mainText
    property string subtitle
    property string descriptionString
    property string descriptionActionId
    property string descriptionVendorName
    property string descriptionVendorUrl

    signal accept()
    signal reject()
    signal userSelected()

    readonly property real speed: Kirigami.Units.longDuration / 200
    // Mist or smoke, the way monet-light set the colors.
    readonly property bool smoke: Kirigami.Theme.backgroundColor.hslLightness < 0.5
    readonly property color ink: smoke ? "#EFECE6" : "#1C1B19"
    readonly property color dim: smoke ? "#B4AEA5" : "#6B665E"
    readonly property color hairline: smoke ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(0, 0, 0, 0.09)
    readonly property color pebble: smoke ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0.11, 0.106, 0.098, 0.06)
    readonly property color well: smoke ? Qt.rgba(0, 0, 0, 0.22) : Qt.rgba(1, 1, 1, 0.75)
    readonly property color lily: smoke ? "#4DB4A0" : "#357F72"
    readonly property color sun: "#F2552C"
    readonly property color paper: "#FBF7EE"

    readonly property real intendedWidth: Kirigami.Units.gridUnit * 26
    readonly property real intendedHeight: column.implicitHeight + column.anchors.margins * 2
    onIntendedHeightChanged: {
        minimumHeight = intendedHeight
        height = intendedHeight
        maximumHeight = intendedHeight
    }

    onSelectedIdentityChanged: userSelected()

    onAccept: {
        waitingForAuthentication = true
        // Wait for the answer before taking more typing.
        if (passwordField.text !== "") {
            passwordField.enabled = false
        }
    }

    onActiveChanged: {
        if (active) {
            passwordField.forceActiveFocus()
        }
    }

    onVisibleChanged: {
        if (visible) {
            passwordField.forceActiveFocus()
        } else {
            // Closing the window is Cancel.
            root.reject()
        }
    }

    Shortcut {
        sequences: [StandardKey.Cancel]
        onActivated: root.reject()
    }

    function rejectPassword() {
        passwordField.clear()
        passwordField.enabled = true
        passwordField.forceActiveFocus()
        waitingForAuthentication = false
        shake.start()
    }

    function authenticationFailure() {
        inlineMessageType = 3
        inlineMessageText = i18nd("monet", "That password didn't work. Try again.")
        rejectPassword()
    }

    function request() {
        if (passwordField.text !== "" && waitingForAuthentication) {
            rejectPassword()
        }
    }

    // Who is asked: you, or another admin chosen from this list.
    QQC2.ComboBox {
        id: identitiesCombo
        visible: false
        textRole: "display"
        valueRole: "userRole"
        enabled: count > 0
        model: IdentitiesModel {}
    }

    ColumnLayout {
        id: column
        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: Kirigami.Units.gridUnit * 1.5
        spacing: Kirigami.Units.smallSpacing * 2
        transform: Translate { id: nudge }

        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.gridUnit

            // A key on a dab of lily.
            Rectangle {
                Layout.alignment: Qt.AlignTop
                implicitWidth: 52
                implicitHeight: 52
                radius: 26
                gradient: Gradient {
                    GradientStop { position: 0; color: "#4DB4A0" }
                    GradientStop { position: 1; color: "#245A50" }
                }
                Shape {
                    anchors.centerIn: parent
                    width: 28
                    height: 28
                    preferredRendererType: Shape.CurveRenderer
                    ShapePath {
                        strokeColor: root.paper
                        strokeWidth: 2.4
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        joinStyle: ShapePath.RoundJoin
                        PathAngleArc { centerX: 9; centerY: 14; radiusX: 6; radiusY: 6; startAngle: 0; sweepAngle: 360 }
                    }
                    ShapePath {
                        strokeColor: root.paper
                        strokeWidth: 2.4
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        joinStyle: ShapePath.RoundJoin
                        PathPolyline { path: [Qt.point(15, 14), Qt.point(26, 14), Qt.point(26, 18.5)] }
                    }
                    ShapePath {
                        strokeColor: root.paper
                        strokeWidth: 2.4
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        PathPolyline { path: [Qt.point(21.5, 14), Qt.point(21.5, 17.5)] }
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: i18nd("monet", "Allow this?")
                    color: root.ink
                    font.family: "Fraunces 72pt SuperSoft"
                    font.pixelSize: 26
                }

                // What the app wants, in its own words.
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: root.mainText
                    color: root.ink
                    opacity: 0.86
                    wrapMode: Text.Wrap
                    textFormat: Text.PlainText
                    font.family: "Inter"
                    font.pixelSize: 14
                    lineHeight: 1.15
                }

                RowLayout {
                    spacing: Kirigami.Units.smallSpacing
                    visible: identitiesCombo.count > 0
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        text: i18ndc("monet", "%1 is a person's name", "As %1", identitiesCombo.currentText)
                        color: root.dim
                        textFormat: Text.PlainText
                        font.family: "Inter"
                        font.pixelSize: 13
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        visible: switchButton.visible
                        text: "·"
                        color: root.dim
                        font.family: "Inter"
                        font.pixelSize: 13
                    }
                    QQC2.AbstractButton {
                        id: switchButton
                        visible: identitiesCombo.count > 1
                        text: i18nd("monet", "Someone else…")
                        implicitWidth: switchLabel.implicitWidth
                        implicitHeight: switchLabel.implicitHeight
                        onClicked: {
                            identitiesCombo.popup.parent = switchButton
                            identitiesCombo.popup.open()
                        }
                        contentItem: Text {
                            horizontalAlignment: Text.AlignLeft
                            id: switchLabel
                            text: switchButton.text
                            color: root.lily
                            font.family: "Inter"
                            font.pixelSize: 13
                            font.underline: switchButton.hovered || switchButton.visualFocus
                        }
                    }
                }
            }
        }

        // The well for the password, with a lily ring while you type.
        T.TextField {
            id: passwordField
            Layout.fillWidth: true
            Layout.topMargin: Kirigami.Units.smallSpacing * 2
            implicitHeight: 42
            verticalAlignment: TextInput.AlignVCenter
            echoMode: TextInput.Password
            passwordCharacter: "•"
            placeholderText: i18nd("monet", "Password")
            color: root.ink
            placeholderTextColor: root.dim
            selectionColor: root.lily
            font.family: "Inter"
            font.pixelSize: 15
            leftPadding: 16
            rightPadding: 16
            onAccepted: root.accept()
            onTextEdited: root.inlineMessageText = ""
            background: Rectangle {
                radius: height / 2
                color: root.well
                border.width: passwordField.activeFocus ? 2 : 1
                border.color: passwordField.activeFocus ? root.lily : root.hairline
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                anchors.fill: parent
                leftPadding: passwordField.leftPadding
                rightPadding: passwordField.rightPadding
                verticalAlignment: Text.AlignVCenter
                visible: passwordField.length === 0 && passwordField.preeditText === ""
                text: passwordField.placeholderText
                color: passwordField.placeholderTextColor
                elide: Text.ElideRight
                font: passwordField.font
            }
        }

        // A wrong password or a message from the system.
        Text {
            horizontalAlignment: Text.AlignLeft
            Layout.fillWidth: true
            Layout.minimumHeight: font.pixelSize * 1.4
            text: root.inlineMessageText
            color: root.inlineMessageType === 3 ? root.ink : root.dim
            wrapMode: Text.Wrap
            textFormat: Text.PlainText
            font.family: "Inter"
            font.italic: true
            font.pixelSize: 13
        }

        // What exactly is asked for, for those who want to know.
        Text {
            horizontalAlignment: Text.AlignLeft
            id: details
            Layout.fillWidth: true
            visible: false
            text: root.descriptionString + (root.descriptionActionId ? "\n" + root.descriptionActionId : "")
            color: root.dim
            wrapMode: Text.WrapAnywhere
            textFormat: Text.PlainText
            font.family: "Inter"
            font.pixelSize: 12
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: Kirigami.Units.smallSpacing
            spacing: Kirigami.Units.smallSpacing * 2

            QQC2.AbstractButton {
                id: detailsButton
                visible: root.descriptionString !== "" || root.descriptionActionId !== ""
                text: details.visible ? i18nd("monet", "Fewer details") : i18nd("monet", "Details")
                implicitWidth: detailsLabel.implicitWidth + 20
                implicitHeight: 36
                onClicked: details.visible = !details.visible
                background: Rectangle {
                    radius: height / 2
                    color: detailsButton.hovered || detailsButton.visualFocus ? root.pebble : "transparent"
                }
                contentItem: Text {
                    id: detailsLabel
                    text: detailsButton.text
                    color: root.dim
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.family: "Inter"
                    font.pixelSize: 13
                }
            }

            Item {
                Layout.fillWidth: true
            }

            Pill {
                text: i18nd("monet", "Cancel")
                ink: root.ink
                tint: root.pebble
                ring: root.lily
                speed: root.speed
                onClicked: root.reject()
            }
            Pill {
                text: i18nd("monet", "Allow")
                ink: root.paper
                tint: root.sun
                ring: root.ink
                speed: root.speed
                enabled: !root.waitingForAuthentication
                onClicked: root.accept()
            }
        }
    }

    // A wrong password shakes the sheet, like the lock screen.
    SequentialAnimation {
        id: shake
        loops: 1
        NumberAnimation { target: nudge; property: "x"; to: -10; duration: Math.round(60 * root.speed) }
        NumberAnimation { target: nudge; property: "x"; to: 8; duration: Math.round(70 * root.speed) }
        NumberAnimation { target: nudge; property: "x"; to: -5; duration: Math.round(70 * root.speed) }
        NumberAnimation { target: nudge; property: "x"; to: 0; duration: Math.round(80 * root.speed) }
    }

    // A pill: Cancel on a pebble, or the answer on the sun.
    component Pill: QQC2.AbstractButton {
        id: pill
        property color ink
        property color tint
        property color ring
        property real speed: 1
        implicitWidth: Math.max(label.implicitWidth + 40, 96)
        implicitHeight: 38
        activeFocusOnTab: true
        Accessible.name: text
        Keys.onEnterPressed: clicked()
        Keys.onReturnPressed: clicked()
        opacity: enabled ? 1 : 0.6
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
            font.pixelSize: 14
            font.weight: Font.DemiBold
        }
    }
}
