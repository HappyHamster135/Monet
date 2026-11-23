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
    function cancelConfirmation() {
        if (backRow.asking) {
            backRow.asking = false
            sheet.focusControl("rollbackPc")
        } else if (resetRow.asking) {
            resetRow.asking = false
            sheet.focusControl("resetPc")
        } else return false
        return true
    }
    spacing: 20
    SettingsControls.PageTitle {
        tone: look
        entry: sheet.entry("updates")
        art: sheet.art
        text: i18n("Updates")
        detail: sheet.pc.autoUpdates === false ? i18n("Only when you ask.")
            : i18n("Monet and your apps keep themselves up to date.")
    }
    SettingsControls.Card {
        tone: look
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 20
            spacing: 18
            Kirigami.Icon {
                Layout.preferredWidth: 56
                Layout.preferredHeight: 56
                source: "monet"
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3
                Text {
                    objectName: "updateTitle"
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: sheet.updateTitle()
                    color: look.ink
                    font.pixelSize: Math.max(17, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 1)
                    font.weight: Font.DemiBold
                    wrapMode: Text.Wrap
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: sheet.updateDetail()
                    color: sheet.updateState === "failed" ? "#E0603A" : look.dim
                    font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                    wrapMode: Text.Wrap
                }
                // Still working: there's no number to show, so it just moves.
                SettingsControls.Busy {
                    tone: look
                    active: sheet.pollingActive
                    Layout.fillWidth: true
                    Layout.topMargin: 6
                    visible: sheet.updateState === "checking" || sheet.updateState === "installing"
                    indeterminate: true
                }
            }
            SettingsControls.Pill {
                tone: look
                objectName: "updateAction"
                readonly property bool restartReady: sheet.updateRestartReady
                kind: sheet.updateState === "available" || restartReady ? "lily" : "plain"
                visible: sheet.updateState !== "done" || restartReady
                text: sheet.updateState === "checking" ? i18n("Checking…")
                    : sheet.updateState === "installing" ? i18n("Installing…")
                    : sheet.updateState === "available" ? i18n("Install")
                    : restartReady ? i18n("Restart now")
                    : sheet.updateState === "failed" ? i18n("Try again")
                    : i18n("Check for updates")
                enabledPill: sheet.updateState !== "checking" && sheet.updateState !== "installing"
                    && sheet.betaState !== "installing"
                onClicked: {
                    if (sheet.updateState === "available") {
                        sheet.installUpdates()
                    } else if (restartReady) {
                        sheet.ask("restart")
                    } else {
                        sheet.checkUpdates()
                    }
                }
            }
        }
    }
    SettingsControls.Card {
        visible: sheet.updateStaged && !sheet.updateRestartReady && !sheet.betaRestartReady
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Restart to finish")
            detail: i18n("The new Monet starts the next time you restart.")
            SettingsControls.Pill {
                tone: look
                objectName: "stagedUpdateRestart"
                kind: "lily"
                text: i18n("Restart now")
                enabledPill: sheet.updateState !== "installing" && sheet.betaState !== "installing"
                onClicked: sheet.ask("restart")
            }
        }
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            tappable: true
            title: i18n("Update automatically")
            detail: sheet.pc.autoUpdates === false
                ? i18n("Monet and your apps update only when you choose Check for updates")
                : i18n("Once a day, in the background: your apps right away, Monet at your next restart")
            onTapped: sheet.flipAutoUpdates()
            SettingsControls.Switch {
                tone: look
                active: sheet.pc.autoUpdates !== false
            }
        }
    }
    // Betas: new versions out for testing, shown only to whoever asks, installed only
    // from their own button. A PC on one moves to the release by itself once it's out.
    SettingsControls.Card {
        tone: look
        objectName: "betaCard"
        SettingsControls.SettingRow {
            tone: look
            objectName: "betaSwitch"
            divider: false
            tappable: true
            checkable: true
            checked: sheet.showBetas
            title: i18n("Show beta versions")
            detail: i18n("Try new versions before everyone else. They're not fully tested yet, and they install only when you choose.")
            onTapped: sheet.flipBetas()
            SettingsControls.Switch {
                tone: look
                active: sheet.showBetas
            }
        }
        SettingsControls.SettingRow {
            id: betaRow
            readonly property var beta: sheet.betaFound
            tone: look
            objectName: "betaRow"
            visible: sheet.showBetas && (sheet.betaChecked || sheet.betaState !== "")
            title: beta ? i18n("Monet %1", i18n("%1 beta %2", beta.version, beta.number)) : i18n("No newer beta right now")
            detail: sheet.betaState === "installing" ? i18n("Downloading and installing. You can keep using your PC.")
                : sheet.betaState === "done" ? i18n("The beta starts the next time you restart.")
                : sheet.betaState === "failed" ? (sheet.betaMessage || i18n("Monet couldn't finish the update. Try again."))
                : sheet.betaMessage !== "" ? sheet.betaMessage
                : beta ? i18n("Not fully tested yet. Once it's released, your PC moves to the release by itself.")
                : i18n("When there's one, it shows here.")
            Row {
                spacing: 8
                SettingsControls.Pill {
                    tone: look
                    objectName: "betaNotes"
                    visible: !!betaRow.beta
                    text: i18n("Release notes")
                    onClicked: Qt.openUrlExternally(betaRow.beta.notes)
                }
                SettingsControls.Pill {
                    tone: look
                    objectName: "betaInstall"
                    visible: !!betaRow.beta && sheet.betaState !== "done"
                    kind: "lily"
                    text: sheet.betaState === "installing" ? i18n("Installing…")
                        : sheet.betaState === "failed" ? i18n("Try again") : i18n("Install beta")
                    enabledPill: sheet.betaState !== "installing" && sheet.updateState !== "checking"
                        && sheet.updateState !== "installing"
                    onClicked: sheet.installBeta()
                }
                SettingsControls.Pill {
                    tone: look
                    objectName: "betaRestart"
                    visible: sheet.betaRestartReady
                    kind: "lily"
                    text: i18n("Restart now")
                    onClicked: sheet.ask("restart")
                }
            }
        }
    }
    SettingsControls.Card {
        tone: look
        objectName: "updateHistoryCard"
        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: 20
            spacing: 12
            RowLayout {
                objectName: "search-update-history"
                Layout.fillWidth: true
                Text {
                    Layout.fillWidth: true
                    text: i18n("Recent automatic updates")
                    color: look.ink
                    font.pixelSize: Math.max(17, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 1)
                    font.weight: Font.DemiBold
                    wrapMode: Text.Wrap
                }
                SettingsControls.Pill {
                    tone: look
                    objectName: "refreshUpdateHistoryButton"
                    text: sheet.updateHistoryBusy ? i18n("Loading…") : i18n("Refresh")
                    enabledPill: !sheet.updateHistoryBusy
                    onClicked: sheet.loadUpdateHistory()
                }
            }
            Text {
                Layout.fillWidth: true
                objectName: "updateHistoryDetail"
                text: sheet.updateHistoryDetail()
                color: look.dim
                font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                wrapMode: Text.Wrap
            }
            Repeater {
                model: sheet.updateHistory.items
                delegate: RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 12
                    Kirigami.Icon {
                        Layout.preferredWidth: 20
                        Layout.preferredHeight: 20
                        source: modelData.result === "failed" ? "dialog-warning"
                            : modelData.result === "skipped" ? "media-playback-pause" : "dialog-ok-apply"
                    }
                    Text {
                        Layout.fillWidth: true
                        text: modelData.result === "failed" ? i18n("Didn't finish")
                            : modelData.result === "skipped" ? i18n("Skipped") : i18n("Completed")
                        color: look.ink
                        font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                        wrapMode: Text.Wrap
                    }
                    Text {
                        objectName: "updateHistoryTime"
                        text: new Date(modelData.time).toLocaleString(Qt.locale(), Locale.ShortFormat)
                        color: look.dim
                        font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                    }
                }
            }
        }
    }
    // What came with this Monet, from its release notes (also offered once after an update).
    SettingsControls.Caption {
        tone: look
        visible: (sheet.whatsNew.items || []).length > 0
        text: i18n("New in Monet %1", sheet.whatsNew.version || "")
    }
    SettingsControls.Card {
        tone: look
        visible: (sheet.whatsNew.items || []).length > 0
        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: 20
            spacing: 14
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                visible: (sheet.whatsNew.headline || "") !== ""
                text: sheet.whatsNew.headline || ""
                color: look.ink
                font.family: "Fraunces 72pt SuperSoft"
                font.pixelSize: 24
                wrapMode: Text.Wrap
            }
            Repeater {
                model: sheet.whatsNew.items || []
                ColumnLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        text: parent.modelData.title
                        color: look.ink
                        font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
                        font.weight: Font.DemiBold
                        wrapMode: Text.Wrap
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        text: parent.modelData.text
                        color: look.dim
                        font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                        lineHeight: 1.25
                        wrapMode: Text.Wrap
                    }
                }
            }
        }
    }
    // An update that didn't start on this PC: Monet went back by itself (monet-boot).
    SettingsControls.Card {
        tone: look
        visible: sheet.wentBack.version !== undefined
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: sheet.wentBack.to ? i18n("Monet went back to %1", sheet.wentBack.to) : i18n("Monet went back")
            detail: sheet.wentBack.version
                ? i18n("Monet %1 didn't start properly on this PC, so it went back by itself. Your files are as they were, and the daily update waits for the next one.", sheet.wentBack.version)
                : i18n("The new Monet didn't start properly on this PC, so it went back by itself. Your files are as they were, and the daily update waits for the next one.")
        }
    }
    // The Monet from before the last update, kept for when one misbehaves (not the one that
    // just didn't start).
    SettingsControls.Card {
        tone: look
        visible: sheet.previous.date !== undefined
            && !(sheet.wentBack.version && sheet.wentBack.version === sheet.previous.version)
        SettingsControls.SettingRow {
            id: backRow
            property bool asking: false
            tone: look
            divider: false
            title: sheet.previous.pending === true ? i18n("%1 starts at your next restart", sheet.previousName())
                : i18n("Go back to %1", sheet.previousName())
            detail: sheet.previous.pending === true ? i18n("The one you're using now stays too, to come back to.")
                : backRow.asking ? i18n("It starts the next time you restart. Your files and apps stay as they are.")
                : sheet.previous.date ? i18n("From %1. If something stopped working after an update, the one before is still here.", sheet.previous.date)
                : i18n("If something stopped working after an update, the one before is still here.")
            Row {
                spacing: 8
                SettingsControls.Pill {
                    tone: look
                    visible: backRow.asking
                    text: i18n("Stay")
                    onClicked: backRow.asking = false
                }
                SettingsControls.Pill {
                    tone: look
                    visible: sheet.previous.pending !== true
                    text: backRow.asking ? i18n("Go back at restart") : i18n("Go back")
                    objectName: "rollbackPc"
                    onClicked: {
                        if (backRow.asking) {
                            backRow.asking = false
                            sheet.goBack()
                        } else {
                            backRow.asking = true
                        }
                    }
                }
                SettingsControls.Pill {
                    tone: look
                    visible: sheet.previous.pending === true
                    kind: "lily"
                    text: i18n("Restart now")
                    onClicked: sheet.ask("restart")
                }
            }
        }
    }
    // Reset this PC: Monet as it comes, with files, games and apps kept (monet-reset, at the
    // next restart, after an administrator's password).
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            id: resetRow
            property bool asking: false
            readonly property bool pending: sheet.resetState.pending === true
            tone: look
            divider: false
            title: pending ? i18n("Monet resets itself at your next restart") : i18n("Reset this PC")
            detail: pending ? i18n("Everyone's settings go back to how Monet comes. Files, games and apps stay.")
                : asking ? i18n("Monet's settings, the desktop's look and the changes made to the system go back to how Monet comes, for everyone. Files, games and apps stay, and so do accounts, Wi-Fi and printers. It happens at your next restart.")
                : i18n("For when something's wrong, and going back to the Monet from before didn't help.")
            Row {
                spacing: 8
                SettingsControls.Pill {
                    tone: look
                    visible: resetRow.asking && !resetRow.pending
                    text: i18n("Stay")
                    onClicked: resetRow.asking = false
                }
                SettingsControls.Pill {
                    tone: look
                    visible: !resetRow.pending
                    text: resetRow.asking ? i18n("Reset at restart") : i18n("Reset")
                    objectName: "resetPc"
                    onClicked: {
                        if (resetRow.asking) {
                            resetRow.asking = false
                            sheet.ask("reset on", out => sheet.resetState = sheet.json(out, sheet.resetState))
                        } else {
                            resetRow.asking = true
                        }
                    }
                }
                SettingsControls.Pill {
                    tone: look
                    visible: resetRow.pending
                    text: i18n("Don't reset")
                    onClicked: sheet.ask("reset off", out => sheet.resetState = sheet.json(out, sheet.resetState))
                }
                SettingsControls.Pill {
                    tone: look
                    visible: resetRow.pending
                    kind: "lily"
                    text: i18n("Restart now")
                    onClicked: sheet.ask("restart")
                }
            }
        }
    }
    // Firmware, only when there's some to install.
    SettingsControls.Card {
        tone: look
        visible: sheet.firmware.length > 0
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 20
            spacing: 18
            SettingsControls.Rounded {
                Layout.preferredWidth: 56
                Layout.preferredHeight: 56
                radius: 16
                Image {
                    anchors.fill: parent
                    source: sheet.art + "swatch-updates.png"
                    sourceSize: Qt.size(112, 112)
                    smooth: true
                }
                SettingsControls.Glyph {
                    anchors.centerIn: parent
                    width: 28
                    height: 28
                    // A chip on its pins.
                    path: "M7 7h10v10H7zM10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4"
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: sheet.firmwareTitle()
                    color: look.ink
                    font.pixelSize: Math.max(17, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 1)
                    font.weight: Font.DemiBold
                    wrapMode: Text.Wrap
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: sheet.firmwareDetail()
                    color: sheet.firmwareState === "failed" ? "#E0603A" : look.dim
                    font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                    wrapMode: Text.Wrap
                }
                SettingsControls.Busy {
                    tone: look
                    active: sheet.pollingActive
                    Layout.fillWidth: true
                    Layout.topMargin: 6
                    visible: sheet.firmwareState === "installing"
                    indeterminate: true
                }
            }
            SettingsControls.Pill {
                tone: look
                kind: sheet.firmwareState === "available" || (sheet.firmwareState === "done" && sheet.firmwareRestart) ? "lily" : "plain"
                visible: !(sheet.firmwareState === "done" && !sheet.firmwareRestart)
                text: sheet.firmwareState === "installing" ? i18n("Installing…")
                    : sheet.firmwareState === "done" ? i18n("Restart now")
                    : sheet.firmwareState === "failed" ? i18n("Try again")
                    : i18n("Install")
                enabledPill: sheet.firmwareState !== "installing" && sheet.firmware.some(f => !f.blocked)
                onClicked: sheet.firmwareState === "done" ? sheet.ask("restart") : sheet.installFirmware()
            }
        }
        Repeater {
            model: sheet.firmware
            SettingsControls.SettingRow {
                tone: look
                strong: false
                title: modelData.vendor && modelData.device.indexOf(modelData.vendor) < 0
                    ? modelData.vendor + " " + modelData.device : modelData.device
                detail: sheet.firmwareLine(modelData)
            }
        }
    }
    Text {
        horizontalAlignment: Text.AlignLeft
        Layout.fillWidth: true
        text: i18n("A new Monet starts the next time you restart, never while you work, and the one before stays in the start menu, just in case.")
        color: look.dim
        font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
        lineHeight: 1.3
        wrapMode: Text.Wrap
    }
}
