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
    id: windowsColumn
    function cancelConfirmation() {
        if (sheet.asking === null) return false
        sheet.asking = null
        sheet.focusControl("windowsSwitch")
        return true
    }
    readonly property string setupState: sheet.pc.windows === "Ready" ? ""
        : sheet.windowsSetup.interrupted ? "interrupted" : (sheet.windowsSetup.status ?? sheet.pc.setup ?? "")
    readonly property bool setupActive: sheet.windowsSetupStarting || sheet.windowsSetup.active === true || setupState === "preparing"
    readonly property bool needsSetup: ["waiting", "preparing", "download-failed", "failed", "no-space", "interrupted"].includes(setupState)
    readonly property bool noWindows: sheet.pc.windows === "Not found" && setupState === ""
    readonly property string setupIso: String(sheet.windowsIso) || (sheet.windowsSetup.iso || "")
    readonly property string isoName: decodeURIComponent(setupIso.split("/").pop())
    spacing: 20
    FileDialog {
        id: windowsIsoPicker
        title: i18n("Choose a Windows 11 ISO")
        nameFilters: [i18n("Disk images") + " (*.iso *.ISO)"]
        onAccepted: {
            sheet.windowsIso = selectedFile
            sheet.windowsSetupProblem = ""
        }
    }
    SettingsControls.PageTitle {
        tone: look
        entry: sheet.entry("windows")
        art: sheet.art
        text: i18n("Play on Windows")
        detail: i18n("Games that need Windows, a restart away.")
    }
    SettingsControls.Card {
        tone: look
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 18
            spacing: 18
            Kirigami.Icon {
                Layout.preferredWidth: 56
                Layout.preferredHeight: 56
                source: "monet-windows"
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: sheet.switching ? i18n("Restarting in Windows…")
                        : sheet.switchProblem !== "" ? i18n("Couldn't open Windows")
                        : sheet.asking && sheet.asking.id ? i18n("Play %1?", sheet.asking.name)
                        : sheet.asking && sheet.asking.task === "launchers" ? i18n("Sign in to your game launchers?")
                        : sheet.asking && sheet.asking.task === "update" ? i18n("Update Windows games?")
                        : sheet.asking ? i18n("Restart in Windows?")
                        : windowsColumn.setupState === "pending" ? i18n("Windows is ready to install")
                        : windowsColumn.setupActive ? i18n("Getting Windows ready")
                        : windowsColumn.setupState === "interrupted" ? i18n("Windows setup did not finish")
                        : windowsColumn.setupState === "failed" ? i18n("Windows setup stopped")
                        : windowsColumn.setupState === "no-space" ? i18n("Windows needs more disk space")
                        : windowsColumn.needsSetup && windowsColumn.setupIso !== "" ? i18n("Windows ISO ready to use")
                        : windowsColumn.setupState === "download-failed" ? (sheet.windowsSetup.mediaError
                            ? i18n("Windows couldn't read that ISO") : i18n("Windows download didn't finish"))
                        : windowsColumn.needsSetup ? i18n("Set up Windows")
                        : (sheet.pc.notice || "") !== "" ? i18n("The last trip didn't reach Windows")
                        : windowsColumn.noWindows ? i18n("No Windows on this PC")
                        : sheet.pc.windows === "Ready" ? i18n("Windows is ready")
                        : (sheet.pc.windows || "") === "" ? i18n("Windows")
                        : i18n("Windows isn't ready")
                    color: look.ink
                    font.pixelSize: Math.max(17, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 1)
                    font.weight: Font.DemiBold
                    wrapMode: Text.Wrap
                }
                Text {
                    objectName: "windowsSetupDetail"
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: sheet.switching ? i18n("Your PC restarts in a moment.")
                        : sheet.switchProblem !== "" ? sheet.switchProblem
                        : windowsColumn.setupState === "pending" ? i18n("Restart to install it. It takes about 10 minutes, then you're back in Monet.")
                            + (typeof sheet.info.battery === "number" && !sheet.info.plugged ? " " + i18n("Plug in the charger first.") : "")
                        : windowsColumn.setupActive ? i18n("You can keep using Monet while Windows is prepared. Monet asks before restarting.")
                        : windowsColumn.setupState === "interrupted" ? i18n("This PC returned to Monet before Windows setup finished. Try again to resume the prepared installation.")
                        : windowsColumn.setupState === "failed" ? (sheet.windowsSetup.message
                            || i18n("Open Check Monet below for details about the failure."))
                        : windowsColumn.setupState === "no-space" ? i18n("Check that your disk has room reserved for Windows and enough free space in Monet to download it.")
                        : windowsColumn.needsSetup && windowsColumn.setupIso !== "" ? i18n("Monet will prepare Windows in the reserved space and ask before restarting.")
                        : windowsColumn.setupState === "download-failed" ? (sheet.windowsSetup.message
                            || i18n("Try the download again or choose a Windows 11 x64 ISO from any folder or connected drive."))
                        : windowsColumn.needsSetup ? i18n("Download Windows 11 from Microsoft for games that need it. Monet asks before restarting.")
                        : !sheet.asking && (sheet.pc.notice || "") !== "" ? i18n(sheet.pc.notice)
                        : sheet.asking && sheet.asking.id ? i18n("Your PC restarts in Windows and opens the game. When you quit, you're back here. Save your work first.")
                        : sheet.asking && sheet.asking.task === "launchers" ? i18n("Your PC restarts in Windows with your game launchers ready. Sign in to each once, then choose Back to Monet. Save your work first.")
                        : sheet.asking && sheet.asking.task === "update" ? i18n("Your PC restarts in Windows, updates it and your games, and switches off when they're done, within an hour and a half. Save your work first.")
                            + (typeof sheet.info.battery === "number" && !sheet.info.plugged ? " " + i18n("Plug in the charger first.") : "")
                        : sheet.asking ? i18n("Your PC restarts in Windows. Open apps close, so save your work first.")
                        : windowsColumn.noWindows ? i18n("Games that need Windows for their anti-cheat can't start on this PC. Everything else plays here, in Monet.")
                        : sheet.pc.windows === "Ready" || (sheet.pc.windows || "") === "" ? i18n("Games that need Windows start there, and you come back here when you quit.")
                        : i18n("Windows: %1. Check Monet below to see what's missing.", i18n(sheet.pc.windows))
                    color: look.dim
                    font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                    wrapMode: Text.Wrap
                }
                Text {
                    Layout.fillWidth: true
                    visible: sheet.asking !== null && !sheet.switching
                    text: i18n("Unsaved changes and private tabs aren't captured. Downloads stop during the restart; check Store's Downloads when you return.")
                    color: look.dim
                    font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                    wrapMode: Text.Wrap
                }
            }
            SettingsControls.Pill {
                tone: look
                visible: sheet.asking !== null
                text: i18n("Cancel")
                onClicked: sheet.asking = null
            }
            SettingsControls.Pill {
                tone: look
                kind: "sun"
                objectName: "windowsSwitch"
                visible: !sheet.switching && !windowsColumn.setupActive && !windowsColumn.needsSetup && !windowsColumn.noWindows
                text: sheet.asking && sheet.asking.id ? i18n("Restart & Play")
                    : sheet.asking ? i18n("Restart")
                    : windowsColumn.setupState === "pending" ? i18n("Restart and install")
                    : i18n("Restart in Windows")
                onClicked: {
                    if (windowsColumn.setupState === "pending" && !sheet.asking) {
                        sheet.ask("restart")
                    } else if (sheet.asking) {
                        sheet.restart()
                    } else {
                        sheet.switchProblem = ""
                        sheet.asking = ({})
                    }
                }
            }
        }
    }
    SettingsControls.Card {
        tone: look
        visible: windowsColumn.needsSetup
        SettingsControls.SettingRow {
            tone: look
            visible: windowsColumn.setupActive || sheet.windowsSetupProblem !== ""
                || windowsColumn.setupState === "interrupted" || windowsColumn.setupIso === ""
            title: i18n("Windows setup")
            detail: sheet.windowsSetupProblem !== "" ? sheet.windowsSetupProblem
                : windowsColumn.setupState === "preparing" ? (sheet.windowsSetup.message
                    || i18n("Setup progress: %1%", sheet.windowsSetup.percent ?? 0))
                : ""
            SettingsControls.Pill {
                objectName: "startWindowsSetup"
                tone: look
                kind: "sun"
                visible: windowsColumn.setupActive || windowsColumn.setupState === "interrupted" || windowsColumn.setupIso === ""
                enabledPill: !windowsColumn.setupActive
                text: windowsColumn.setupActive ? i18n("Setting up…")
                    : windowsColumn.setupState === "interrupted" ? i18n("Try setup again")
                    : windowsColumn.setupState === "download-failed" ? i18n("Retry download")
                    : i18n("Set up Windows…")
                onClicked: sheet.startWindowsSetup("", ["interrupted", "download-failed"].includes(windowsColumn.setupState))
            }
        }
        SettingsControls.SettingRow {
            visible: !windowsColumn.setupActive && windowsColumn.setupState !== "interrupted"
            tone: look
            title: i18n("Windows 11 ISO")
            detail: windowsColumn.isoName
            SettingsControls.Pill {
                objectName: "chooseWindowsIso"
                tone: look
                kind: windowsColumn.setupState === "download-failed" && windowsColumn.isoName === "" ? "sun" : "plain"
                text: windowsColumn.isoName === "" ? i18n("Choose ISO…") : i18n("Change ISO…")
                onClicked: windowsIsoPicker.open()
            }
        }
        SettingsControls.SettingRow {
            visible: !windowsColumn.setupActive && windowsColumn.setupState !== "interrupted" && windowsColumn.isoName !== ""
            tone: look
            title: i18n("Prepare Windows")
            detail: i18n("Administrator access is required to prepare the reserved space.")
            SettingsControls.Pill {
                objectName: "prepareWindowsIso"
                tone: look
                kind: "sun"
                text: i18n("Set up Windows…")
                onClicked: sheet.startWindowsSetup(windowsColumn.setupIso)
            }
        }
        SettingsControls.SettingRow {
            visible: !windowsColumn.setupActive && windowsColumn.setupState !== "interrupted" && windowsColumn.setupIso === ""
            tone: look
            divider: false
            title: i18n("Need an ISO?")
            SettingsControls.Pill {
                objectName: "windowsIsoPage"
                tone: look
                text: i18n("Open Microsoft’s download page")
                onClicked: sheet.ask("windows-setup-download-page", (out, code) => {
                    if (code !== 0) sheet.windowsSetupProblem = i18n("Monet couldn't open Microsoft’s download page.")
                })
            }
        }
    }
    GridLayout {
        Layout.fillWidth: true
        visible: sheet.games.length > 0 && !windowsColumn.noWindows && !windowsColumn.needsSetup
        columns: 4
        columnSpacing: 12
        rowSpacing: 12
        Repeater {
            model: sheet.games.slice(0, 8)
            SettingsControls.Cover {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                Layout.preferredHeight: implicitHeight
                name: modelData.name
                artwork: modelData.art
                glaze: sheet.glaze(modelData.name)
                // Plays in Monet too: no restart needed.
                here: modelData.here === true
                onPicked: {
                    sheet.switchProblem = ""
                    sheet.asking = modelData
                }
            }
        }
    }
    Text {
        horizontalAlignment: Text.AlignLeft
        Layout.fillWidth: true
        visible: sheet.games.length === 0 && !windowsColumn.noWindows && !windowsColumn.needsSetup
        text: i18n("Your Windows games show up here once Windows has started with Monet Bridge.")
        color: look.dim
        font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
        wrapMode: Text.Wrap
    }
    // Trips that make the next ones smoother: signed in everywhere, everything up to date.
    SettingsControls.Card {
        tone: look
        visible: (sheet.games.length > 0 || sheet.pc.windows === "Ready") && !windowsColumn.noWindows && !windowsColumn.needsSetup
        SettingsControls.SettingRow {
            tone: look
            title: i18n("Game launchers")
            detail: i18n("Sign in once to Steam, Riot, Battle.net and the rest in Windows, and the games you play from here start without asking. If you use Discord here, it comes along, so a call carries on in Windows.")
            SettingsControls.Pill {
                tone: look
                text: i18n("Sign in…")
                enabledPill: !sheet.switching
                onClicked: {
                    sheet.switchProblem = ""
                    sheet.asking = { task: "launchers" }
                }
            }
        }
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Update Windows games")
            detail: (sheet.gamesUpdated > 0
                     ? i18n("Last done %1.", Qt.formatDate(new Date(sheet.gamesUpdated * 1000), Locale.ShortFormat)) + " " : "")
                + i18n("Windows updates itself and your games, then switches the PC off. Good before you go to bed.")
            SettingsControls.Pill {
                tone: look
                text: i18n("Update & switch off")
                enabledPill: !sheet.switching
                onClicked: {
                    sheet.switchProblem = ""
                    sheet.asking = { task: "update" }
                }
            }
        }
    }
    Loader {
        Layout.fillWidth: true
        sourceComponent: returnSummary
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Check Monet")
            detail: i18n("See that Windows, Secure Boot and switching are all set up")
            SettingsControls.Pill {
                tone: look
                text: sheet.checkingDoctor ? i18n("Checking…") : i18n("Check")
                enabledPill: !sheet.checkingDoctor
                onClicked: sheet.checkMonet()
            }
        }
        Text {
            horizontalAlignment: Text.AlignLeft
            Layout.fillWidth: true
            Layout.leftMargin: 18
            Layout.rightMargin: 18
            Layout.bottomMargin: 16
            visible: sheet.doctorReport !== ""
            textFormat: Text.StyledText
            text: sheet.report(sheet.doctorReport)
            color: look.ink
            font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
            lineHeight: 1.35
            wrapMode: Text.Wrap
        }
    }
    // Ready when you come back: off until it's chosen, as it signs in without asking first.
    SettingsControls.Card {
        tone: look
        visible: !windowsColumn.noWindows
        SettingsControls.SettingRow {
            tone: look
            divider: false
            tappable: true
            title: i18n("Ready when you come back")
            detail: i18n("After Windows, Monet starts your desktop behind the lock screen, so it's there as soon as you type your password.")
            onTapped: {
                const on = sheet.ready.on !== true
                sheet.ready = sheet.changed(sheet.ready, ["on"], on)
                sheet.ask(on ? "ready-on" : "ready-off", out => sheet.ready = sheet.json(out, sheet.ready))
            }
            SettingsControls.Switch {
                tone: look
                active: sheet.ready.on === true
            }
        }
        // The apps that were open before the trip start again (monet-quick remembers them),
        // as after a restart: the same switch as Power & Sleep's.
        SettingsControls.SettingRow {
            tone: look
            tappable: true
            checkable: true
            checked: sheet.ready.apps !== false
            title: i18n("Reopen your work")
            detail: i18n("After Windows or a restart, your apps come back where they were, with saved documents and Files tabs. Zen follows its tab-restore preference. Unsaved changes and private tabs aren't kept.")
            onTapped: sheet.setReopenWork(sheet.ready.apps === false)
            SettingsControls.Switch {
                tone: look
                active: sheet.ready.apps !== false
            }
        }
    }
}
