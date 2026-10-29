/*
 * SPDX-FileCopyrightText: 2026 Monet contributors
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * A Windows program opened in Files (an .exe or .msi): run it in Monet, through Proton as
 * Windows games run here, or open it in Windows, which gets it through the Games folder both
 * share. `monet-quick windows-program` rings Quick Settings' doorbell, and this sheet asks.
 * An app in Windows' Start menu, chosen in the app menu (`monet-quick windows-app`), is asked
 * about here too: it opens in Windows, where it is.
 */
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmaCore.Dialog {
    id: sheet

    property string helper
    property real speed: 1
    // The screen to open on, from the panel.
    property rect area: Qt.rect(0, 0, 1280, 800)
    // {path, name, size, installer, here, windows: "ok" | "closed" | "full" | "not-yours" | "no-windows"},
    // or a Windows app: {app, name, icon, here: false, windows: "ok"}
    property var info: ({})
    readonly property bool app: (info.app || "") !== ""
    property bool copying: false
    property string problem: ""
    readonly property bool canWindows: info.windows === "ok"

    title: app ? i18n("Windows app") : i18n("Windows program")
    location: PlasmaCore.Types.Floating
    hideOnWindowDeactivate: false
    visible: false

    function open() {
        problem = ""
        copying = false
        ask("program-info", out => {
            try {
                info = JSON.parse(out)
            } catch (e) {
                info = {}
            }
            if (!info.path && !info.app)
                return
            visible = true
            Qt.callLater(() => {
                x = Math.round(area.x + (area.width - mainItem.width) / 2)
                y = Math.round(area.y + (area.height - mainItem.height) / 2 - area.height * 0.06)
                raise()
                requestActivate()
                const first = info.here ? here : info.windows === "ok" ? windows : cancel
                first.forceActiveFocus()
            })
        })
    }

    function runHere() {
        ask("program-here", () => {})
        visible = false
    }

    function openInWindows() {
        copying = true
        problem = ""
        ask("program-windows", (out, code, err) => {
            copying = false
            // The PC restarts in Windows; anything else is said here.
            if (code !== 0)
                problem = (err || "").trim().split("\n")[0] || i18n("Monet couldn't switch to Windows.")
        })
    }

    property var waiting: ({})
    function ask(args, then) {
        const command = helper + " " + args
        waiting[command] = then
        asker.connectSource(command)
    }

    // A button: a pebble of the glass, or the sun for the one bright thing.
    component Pill: Rectangle {
        id: pill
        property var tone
        property string text
        property bool sun: false
        signal clicked()
        implicitWidth: label.implicitWidth + (sun ? 40 : 32)
        implicitHeight: sun ? 40 : 36
        radius: sun ? 20 : 12
        opacity: enabled ? 1 : 0.5
        color: sun ? (hover.hovered ? "#FF6A42" : "#F2552C") : hover.hovered ? tone.press : tone.wash2
        scale: tap.pressed ? 0.96 : hover.hovered && sun ? 1.04 : 1
        border.width: activeFocus ? 2 : 0
        border.color: sun ? "#FFFFFF" : tone.lily
        activeFocusOnTab: true
        Keys.onReturnPressed: if (enabled) pill.clicked()
        Keys.onEnterPressed: if (enabled) pill.clicked()
        Keys.onSpacePressed: if (enabled) pill.clicked()
        Behavior on scale { NumberAnimation { duration: Math.round(160 * pill.tone.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }
        Behavior on color { ColorAnimation { duration: Math.round(140 * pill.tone.speed) } }
        Text {
            id: label
            anchors.centerIn: parent
            horizontalAlignment: Text.AlignLeft
            text: pill.text
            color: pill.sun ? "#FFFFFF" : pill.tone.ink
            font.pixelSize: pill.sun ? 15 : 14
            font.weight: Font.DemiBold
        }
        HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
        TapHandler { id: tap; enabled: pill.enabled; onTapped: pill.clicked() }
        Accessible.role: Accessible.Button
        Accessible.name: text
        Accessible.onPressAction: if (enabled) pill.clicked()
    }

    mainItem: Item {
        id: frame
        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true
        width: Math.min(540, sheet.area.width - 32)
        // A plain column, each line its width: wrapped text says how tall it is (a layout's doesn't).
        height: column.height + 48

        Shortcut {
            sequences: ["Escape"]
            onActivated: sheet.visible = false
        }

        P5Support.DataSource {
            id: asker
            engine: "executable"
            connectedSources: []
            onNewData: (source, data) => {
                disconnectSource(source)
                const then = sheet.waiting[source]
                delete sheet.waiting[source]
                if (then)
                    then(data["stdout"] || "", data["exit code"], data["stderr"] || "")
            }
        }

        // Mist or smoke, as Monet Settings has them.
        QtObject {
            id: look
            readonly property bool dark: Kirigami.Theme.backgroundColor.hslLightness < 0.5
            readonly property color ink: dark ? "#F1EEE8" : "#1C1B19"
            readonly property color dim: dark ? Qt.rgba(0.945, 0.933, 0.91, 0.62) : Qt.rgba(0.11, 0.106, 0.098, 0.6)
            readonly property color wash2: dark ? Qt.rgba(1, 1, 1, 0.1) : Qt.rgba(0.11, 0.106, 0.098, 0.07)
            readonly property color press: dark ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(0.11, 0.106, 0.098, 0.11)
            readonly property color lily: dark ? "#4DB4A0" : "#357F72"
            readonly property real speed: sheet.speed
        }

        Column {
            id: column
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 24
            spacing: 14

            RowLayout {
                width: parent.width
                spacing: 14
                // The program, on a pebble.
                Rectangle {
                    Layout.preferredWidth: 52
                    Layout.preferredHeight: 52
                    Layout.alignment: Qt.AlignTop
                    radius: 16
                    color: look.wash2
                    // The app's own icon (framed as Monet frames apps' icons).
                    Kirigami.Icon {
                        anchors.centerIn: parent
                        width: 40
                        height: 40
                        visible: sheet.app
                        source: sheet.info.icon || ""
                    }
                    // A window with its title bar, in Monet's line.
                    Rectangle {
                        visible: !sheet.app
                        anchors.centerIn: parent
                        width: 26
                        height: 22
                        radius: 4
                        color: "transparent"
                        border.width: 2
                        border.color: look.ink
                        Rectangle {
                            y: 6
                            width: parent.width
                            height: 2
                            color: look.ink
                        }
                        Row {
                            x: 5
                            y: 2.5
                            spacing: 2.5
                            Repeater {
                                model: 2
                                Rectangle {
                                    width: 2.2
                                    height: 2.2
                                    radius: 1.1
                                    color: look.ink
                                }
                            }
                        }
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignLeft
                        text: sheet.app ? sheet.info.name || "" : sheet.info.installer ? i18n("A Windows installer") : i18n("A Windows program")
                        color: look.ink
                        font.family: "Fraunces 72pt SuperSoft"
                        font.pixelSize: 26
                        wrapMode: Text.Wrap
                    }
                    Text {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignLeft
                        text: sheet.app ? i18n("A Windows app") : sheet.info.name || ""
                        color: look.dim
                        font.pixelSize: 13
                        elide: Text.ElideMiddle
                        textFormat: Text.PlainText
                    }
                }
            }

            Text {
                width: parent.width
                horizontalAlignment: Text.AlignLeft
                wrapMode: Text.Wrap
                color: look.ink
                font.pixelSize: 14
                lineHeight: 1.15
                text: sheet.app ? i18n("It's in your Windows: your PC restarts in Windows and opens it there, so save your work first. Back to Monet brings you back.")
                    : (sheet.info.installer
                        ? i18n("Monet runs many Windows programs itself, the way it runs Windows games, and what this one installs shows up in your app menu.")
                        : i18n("Monet runs many Windows programs itself, the way it runs Windows games."))
                    + (sheet.canWindows ? " " + i18n("If it needs Windows, open it there: your PC restarts in Windows and opens it, so save your work first.") : "")
            }

            Text {
                width: parent.width
                visible: sheet.canWindows
                wrapMode: Text.Wrap
                color: look.dim
                font.pixelSize: 13
                text: i18n("Unsaved changes and private tabs aren't captured. Downloads stop during the restart; check Store's Downloads when you return.")
            }

            // Why Windows can't have it this time, or why it can't run here.
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignLeft
                wrapMode: Text.Wrap
                color: sheet.problem !== "" ? "#C2462A" : look.dim
                font.pixelSize: 13
                visible: text !== ""
                text: sheet.problem !== "" ? sheet.problem
                    : sheet.info.windows === "closed" ? i18n("Windows can't get it this time, because its drive isn't open to Monet. After your next trip to Windows, it can.")
                    : sheet.info.windows === "full" ? i18n("There isn't room for it on Windows' drive.")
                    : sheet.info.windows === "not-yours" ? i18n("Only the person who set up this PC can send programs to Windows.")
                    : sheet.info.here === false && !sheet.app ? i18n("Monet can't run Windows programs itself on this PC.")
                    : ""
            }

            RowLayout {
                width: parent.width
                spacing: 8
                Item { Layout.fillWidth: true }
                Pill {
                    id: cancel
                    tone: look
                    text: i18n("Cancel")
                    onClicked: sheet.visible = false
                }
                Pill {
                    id: windows
                    tone: look
                    sun: sheet.app
                    visible: sheet.info.windows !== "no-windows"
                    enabled: sheet.canWindows && !sheet.copying
                    text: sheet.copying ? (sheet.app ? i18n("Restarting…") : i18n("Copying…")) : i18n("Open in Windows")
                    onClicked: sheet.openInWindows()
                }
                Pill {
                    id: here
                    tone: look
                    sun: true
                    visible: sheet.info.here === true
                    enabled: !sheet.copying
                    text: i18n("Run in Monet")
                    onClicked: sheet.runHere()
                }
            }
        }
    }
}
