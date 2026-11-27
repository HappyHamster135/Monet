// Loaded by the Settings page loader; shares its window context.
import QtCore
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Templates as T
import QtQuick.Window
import org.kde.kirigami as Kirigami
import "../games" as Shared
import "FocusNavigation.js" as FocusNavigation


ColumnLayout {
    spacing: 20
    SettingsControls.Rounded {
        id: banner
        Layout.fillWidth: true
        // Clear of the close button.
        Layout.topMargin: 22
        Layout.preferredHeight: Math.round(width * 360 / 1200)
        radius: 18
        Image {
            anchors.fill: parent
            source: sheet.art + "about.jpg"
            fillMode: Image.PreserveAspectCrop
            smooth: true
        }
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.4; color: "transparent" }
                GradientStop { position: 1; color: Qt.rgba(0.05, 0.03, 0.1, 0.45) }
            }
        }
        Column {
            anchors.left: parent.left
            anchors.bottom: parent.bottom
            anchors.leftMargin: 24
            anchors.bottomMargin: 18
            spacing: 4
            Text {
                horizontalAlignment: Text.AlignLeft
                text: "Monet"
                color: "#FFFFFF"
                font.family: "Fraunces 72pt SuperSoft"
                font.weight: Font.Light
                font.pixelSize: 48
                font.letterSpacing: -1.2
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                text: sheet.pc.monet ? i18n("%1 · Impression", sheet.monetVersion(sheet.pc.monet, sheet.pc.beta, sheet.pc.localBuild)) : i18n("Impression")
                color: "#E6FFFFFF"
                font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
            }
        }
    }
    SettingsControls.Card {
        tone: look
        Repeater {
            model: [
                [i18n("Graphics"), sheet.pc.graphics],
                [i18n("Processor"), sheet.pc.processor],
                [i18n("Memory"), sheet.pc.memory],
                [i18n("Storage"), sheet.pc.storage],
                [i18n("Windows"), sheet.pc.windows === "Ready" ? i18n("Ready for games") : (sheet.pc.windows ? i18n(sheet.pc.windows) : "")]
            ].filter(r => r[1])
            SettingsControls.SettingRow {
                tone: look
                divider: index > 0
                strong: false
                title: modelData[0]
                Text {
                    horizontalAlignment: Text.AlignLeft
                    width: Math.min(implicitWidth, 380)
                    text: modelData[1]
                    color: look.ink
                    font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
                    elide: Text.ElideRight
                }
            }
        }
    }
    // How long the last start took, and where the time went: to see what a change does.
    SettingsControls.Card {
        tone: look
        visible: sheet.startup.total !== undefined
        SettingsControls.SettingRow {
            tone: look
            divider: false
            strong: false
            title: i18n("Last start")
            detail: [
                sheet.startup.pc ? i18nc("how long the PC's own start took, in seconds", "The PC %1 s", sheet.secs(sheet.startup.pc)) : "",
                sheet.startup.monet ? i18nc("how long Monet took to start, in seconds", "Monet %1 s", sheet.secs(sheet.startup.monet)) : "",
                sheet.startup.desktop ? i18nc("from signing in until the desktop was there, in seconds", "Your desktop %1 s", sheet.secs(sheet.startup.desktop)) : ""
            ].filter(t => t !== "").join("  ·  ")
            Text {
                horizontalAlignment: Text.AlignLeft
                text: i18nc("a time in seconds", "%1 s", sheet.secs(sheet.startup.total || 0))
                color: look.ink
                font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
            }
        }
    }
    // Everything that helps find out why something went wrong, in one file to send.
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Save a report")
            detail: sheet.reportSaved !== "" ? i18n("In Documents, as %1.", sheet.reportSaved)
                : i18n("What helps find out why something went wrong, in one file in Documents. It stays on this PC until you send it to someone.")
            SettingsControls.Pill {
                tone: look
                text: sheet.reporting ? i18n("Saving…") : i18n("Save")
                enabledPill: !sheet.reporting
                onClicked: {
                    if (sheet.reporting)
                        return
                    sheet.reporting = true
                    sheet.ask("report", out => {
                        sheet.reporting = false
                        sheet.reportSaved = sheet.json(out, {}).saved || ""
                    })
                }
            }
        }
    }
    // For people from Linux: the system can't be changed (that keeps updates safe),
    // so command-line tools go in a container, which BoxBuddy makes (Distrobox's).
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Command-line tools")
            detail: i18n("Monet's system can't be changed, which keeps every update safe, so tools for the command line go in a container beside it, where you install what you like. BoxBuddy makes one in a few clicks.")
            SettingsControls.Pill {
                tone: look
                text: sheet.gettingTools ? i18n("Getting…") : i18n("Get BoxBuddy")
                enabledPill: !sheet.gettingTools
                onClicked: {
                    sheet.gettingTools = true
                    sheet.ask("get-tools", () => sheet.gettingTools = false)
                }
            }
        }
    }
}
