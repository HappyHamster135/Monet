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
    readonly property var pads: sheet.gameInfo.controllers || []
    readonly property var libraries: sheet.gameInfo.libraries || []
    id: gamesColumn
    spacing: 20
    SettingsControls.PageTitle {
        tone: look
        entry: sheet.entry("games")
        art: sheet.art
        text: i18n("Games & Controllers")
        detail: gamesColumn.pads.length > 0
            ? i18np("%1 controller connected", "%1 controllers connected", gamesColumn.pads.length)
            : i18n("Your controllers, and where your games are kept.")
    }
    SettingsControls.Caption {
        tone: look
        visible: (sheet.gameInfo.functionKeys || {}).supported === true
        text: i18n("Keyboard")
    }
    SettingsControls.Card {
        tone: look
        visible: (sheet.gameInfo.functionKeys || {}).supported === true
        SettingsControls.SettingRow {
            objectName: "gameFunctionKeysSetting"
            tone: look
            divider: false
            title: i18n("F1–F12 while playing")
            detail: (sheet.gameInfo.functionKeys || {}).ready === true
                ? i18n("Use the function keys in games. Hold Fn for volume, brightness and the other top-row controls. Switching to another app restores your usual keys. Keep Fn Lock off.")
                : i18n("The laptop keyboard helper needs to be installed before this can be used.")
            tappable: (sheet.gameInfo.functionKeys || {}).ready === true
            onTapped: sheet.ask("game-function-keys " + (sheet.gameInfo.functionKeys.enabled ? "off" : "on"),
                               out => sheet.gameInfo = sheet.json(out, sheet.gameInfo))
            SettingsControls.Switch {
                tone: look
                active: (sheet.gameInfo.functionKeys || {}).ready === true && (sheet.gameInfo.functionKeys || {}).enabled === true
            }
        }
    }
    SettingsControls.Caption {
        tone: look
        text: i18n("Controllers")
    }
    SettingsControls.Card {
        tone: look
        Repeater {
            model: gamesColumn.pads
            SettingsControls.SettingRow {
                required property var modelData
                required property int index
                tone: look
                divider: index > 0
                title: modelData.name
                detail: modelData.battery === null ? (modelData.wireless ? i18n("Connected") : i18nc("a controller, connected by its cable", "Plugged in"))
                    : modelData.charging ? i18n("%1% · charging", modelData.battery)
                    : i18n("%1% battery", modelData.battery)
            }
        }
        SettingsControls.SettingRow {
            tone: look
            divider: gamesColumn.pads.length > 0
            title: gamesColumn.pads.length > 0 ? i18n("Another controller") : i18n("No controller connected")
            detail: i18n("Plug one in, or pair one over Bluetooth")
            Row {
                spacing: 8
                SettingsControls.Pill {
                    tone: look
                    visible: sheet.gameInfo.pair === true
                    text: i18n("Pair…")
                    onClicked: sheet.ask("pair-controller")
                }
                SettingsControls.Pill {
                    tone: look
                    text: i18n("Test buttons…")
                    onClicked: sheet.ask("kde gamecontroller")
                }
            }
        }
    }
    SettingsControls.Caption {
        tone: look
        visible: typeof sheet.gameInfo.overlay === "boolean"
        text: i18n("While you play")
    }
    SettingsControls.Card {
        tone: look
        visible: typeof sheet.gameInfo.overlay === "boolean" || typeof sheet.gameInfo.replay === "boolean"
        SettingsControls.SettingRow {
            tone: look
            divider: false
            visible: typeof sheet.gameInfo.overlay === "boolean"
            tappable: true
            title: i18n("Performance overlay")
            detail: i18n("Frames per second and what the PC is doing, over every game, from your next sign-in. Right Shift+F12 hides it while you play.")
            onTapped: sheet.overlay(sheet.gameInfo.overlay !== true)
            SettingsControls.Switch {
                tone: look
                active: sheet.gameInfo.overlay === true
            }
        }
        // As Xbox Game Bar has it: the last 30 seconds, kept to save.
        SettingsControls.SettingRow {
            tone: look
            divider: typeof sheet.gameInfo.overlay === "boolean"
            visible: typeof sheet.gameInfo.replay === "boolean"
            tappable: !sheet.replaying
            title: i18n("Save the last 30 seconds")
            detail: sheet.replaying ? i18n("Getting it ready…")
                : sheet.replayFailed ? i18n("It couldn't be installed. Check the internet connection, then try again.")
                : i18n("Windows key + Alt + G keeps the last 30 seconds on screen in Videos. The first time, choose the screen to record.")
            onTapped: sheet.replay(sheet.gameInfo.replay !== true)
            SettingsControls.Switch {
                tone: look
                active: sheet.gameInfo.replay === true
            }
        }
    }
    // Windows' Games folder: one copy of a game that Steam plays on both sides
    // (monet-windows-drive opens it when Windows' drive is safe to write).
    SettingsControls.Caption {
        tone: look
        visible: sharedCard.visible
        text: i18n("Shared with Windows")
    }
    SettingsControls.Card {
        id: sharedCard
        objectName: "search-shared"
        tone: look
        readonly property var s: sheet.gameInfo.shared || {}
        visible: ["open", "asleep", "unclean", "bitlocker", "failed", "unknown"].indexOf(s.state) !== -1
                 || (s.state === "no-bridge" && s.unlocked === true)
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: sharedCard.s.state === "open" && sharedCard.s.steam ? i18n("Windows games")
                : i18n("Install each game once")
            detail: sharedCard.s.state === "asleep" ? i18n("Windows didn't shut down fully, so its drive isn't open to Monet this time. It is again after your next trip to Windows.")
                : sharedCard.s.state === "unclean" ? i18n("Windows wants to check its drive first. It does that by itself the next time it starts.")
                : sharedCard.s.state === "bitlocker" && sharedCard.s.handover === true
                    ? i18n("Windows' drive is encrypted with BitLocker. Start Windows once, and Monet Bridge hands its recovery key over: Monet opens it by itself from then on. Or type the key here.")
                : sharedCard.s.state === "bitlocker" ? i18n("Windows' drive is encrypted with BitLocker. Type its recovery key once, and Monet opens it at every start, for games, files and Wi-Fi in both.")
                : sharedCard.s.state === "no-bridge" ? i18n("Windows' drive is open. Monet Bridge installs itself the next time Windows starts, and from then on games, files and Wi-Fi work in both.")
                : sharedCard.s.state !== "open" ? i18n("Windows' drive couldn't be opened this time.")
                : sharedCard.s.steam ? sheet.library(sharedCard.s) + ". " + i18n("Steam here and Steam in Windows both play from it. When you install a game, choose Windows games, and it's ready on both.")
                : sharedCard.s.mine ? i18n("Steam here can keep games in Windows' Games folder, where Windows plays them too. Steam closes for a moment to add it.")
                : i18n("Steam keeps games for both in Windows' Games folder for the person who set up this PC.")
            SettingsControls.Pill {
                tone: look
                visible: sharedCard.s.state === "open" && sharedCard.s.mine === true && sharedCard.s.steam !== true
                text: sheet.sharing ? i18n("Adding…") : i18n("Add to Steam")
                enabledPill: !sheet.sharing
                onClicked: {
                    sheet.sharing = true
                    sheet.ask("steam-share now", out => {
                        sheet.sharing = false
                        sheet.gameInfo = sheet.changed(sheet.gameInfo, ["shared"], sheet.json(out, sharedCard.s))
                    })
                }
            }
            SettingsControls.Pill {
                tone: look
                visible: sharedCard.s.state === "open" && sharedCard.s.steam === true
                text: i18n("Show")
                onClicked: Qt.openUrlExternally("file://" + encodeURI(sharedCard.s.path + "/steamapps/common"))
            }
        }
        // BitLocker: its recovery key, typed once; monet-windows-drive opens the drive with it at
        // every start, the key sealed by the PC's security chip.
        ColumnLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 18
            Layout.rightMargin: 18
            Layout.bottomMargin: 16
            visible: sharedCard.s.state === "bitlocker"
            spacing: 8
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                SettingsControls.Field {
                    id: recoveryKey
                    tone: look
                    hint: i18n("Recovery key, 48 digits")
                    onAccepted: sheet.unlockWindows(text)
                }
                SettingsControls.Pill {
                    tone: look
                    kind: "lily"
                    text: sheet.unlocking ? i18n("Unlocking…") : i18n("Unlock")
                    enabledPill: !sheet.unlocking && recoveryKey.text.trim() !== ""
                    onClicked: sheet.unlockWindows(recoveryKey.text)
                }
            }
            Text {
                Layout.fillWidth: true
                text: sheet.unlockProblem !== "" ? sheet.unlockProblem
                    : i18n("It's in your Microsoft account, or in Windows: search for Manage BitLocker, then Back up your recovery key.")
                color: sheet.unlockProblem !== "" ? "#E0603A" : look.dim
                font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                wrapMode: Text.Wrap
            }
            SettingsControls.Pill {
                tone: look
                text: i18n("Find my key")
                onClicked: Qt.openUrlExternally("https://aka.ms/myrecoverykey")
            }
        }
        // Heroic's games go there too: Epic's launcher in Windows takes them over, GOG's start by themselves.
        SettingsControls.SettingRow {
            tone: look
            visible: sharedCard.s.state === "open" && sharedCard.s.heroic === true
            title: i18n("Epic and GOG games")
            detail: i18n("In Heroic, choose Windows games as the folder when you install one, and Windows plays it too: Epic's launcher there takes it over, and GOG's games start by themselves.")
        }
        // No Heroic yet: one tap gets it from Flathub, and opens it to sign in.
        SettingsControls.SettingRow {
            tone: look
            visible: sharedCard.s.state === "open" && sharedCard.s.heroic === false
            title: i18n("Epic and GOG games")
            detail: i18n("Get Heroic for your Epic and GOG games. One you install in Windows games plays in Windows too.")
            SettingsControls.Pill {
                tone: look
                text: sheet.gettingHeroic ? i18n("Getting Heroic…") : i18n("Get Heroic")
                enabledPill: !sheet.gettingHeroic
                onClicked: {
                    sheet.gettingHeroic = true
                    sheet.ask("get-heroic", out => {
                        sheet.gettingHeroic = false
                        sheet.gameInfo = sheet.changed(sheet.gameInfo, ["shared"], sheet.json(out, sharedCard.s))
                    })
                }
            }
        }
        // Battle.net's, Ubisoft's and EA's launchers in Monet (Lutris) have Windows games as drive W:.
        SettingsControls.SettingRow {
            tone: look
            visible: sharedCard.s.state === "open"
            title: i18n("Battle.net, Ubisoft and EA games")
            detail: i18n("In Battle.net, Ubisoft Connect or the EA app here, install to drive W: (Windows games), and Windows plays it too. The first time, its launcher there may ask where it is: Play says what to pick.")
            // Got through Lutris here (Flathub's, if there's none); open once it's here.
            Row {
                spacing: 8
                Repeater {
                    model: [["battlenet", "Battle.net"], ["ubisoft", "Ubisoft Connect"], ["ea", "EA app"]]
                    SettingsControls.Pill {
                        required property var modelData
                        tone: look
                        text: sheet.gettingLauncher === modelData[0] ? i18n("Getting %1…", modelData[1])
                            : sharedCard.s[modelData[0]] === true ? i18n("Open %1", modelData[1])
                            : i18n("Get %1", modelData[1])
                        enabledPill: sheet.gettingLauncher === ""
                        onClicked: {
                            sheet.gettingLauncher = modelData[0]
                            sheet.ask("get-launcher " + modelData[0], out => {
                                sheet.gettingLauncher = ""
                                sheet.gameInfo = sheet.changed(sheet.gameInfo, ["shared"], sheet.json(out, sharedCard.s))
                            })
                        }
                    }
                }
            }
        }
        // Downloads, mods and installers saved once, for both.
        SettingsControls.SettingRow {
            tone: look
            visible: sharedCard.s.state === "open" && !!sharedCard.s.files
            title: i18n("Shared with Windows")
            detail: i18n("A folder Windows has too, as Shared with Monet: save a download, a mod or an installer there once, and it's in both. Files lists it with your places.")
            SettingsControls.Pill {
                tone: look
                text: i18n("Show")
                onClicked: Qt.openUrlExternally("file://" + encodeURI(sharedCard.s.files))
            }
        }
    }
    SettingsControls.Caption {
        tone: look
        text: i18n("Where your games are")
    }
    SettingsControls.Card {
        tone: look
        Repeater {
            model: gamesColumn.libraries
            SettingsControls.SettingRow {
                id: libraryRow
                required property var modelData
                required property int index
                tone: look
                divider: index > 0
                title: modelData.name
                detail: sheet.library(modelData)
                SettingsControls.Pill {
                    tone: look
                    text: i18n("Show")
                    onClicked: Qt.openUrlExternally("file://" + encodeURI(libraryRow.modelData.path))
                }
            }
        }
        SettingsControls.SettingRow {
            tone: look
            divider: false
            visible: gamesColumn.libraries.length === 0
            title: i18n("No games yet")
            detail: i18n("Steam, Heroic and Lutris keep theirs here once you install one")
        }
    }
    // Games installed here whose anti-cheat only lets them run on Windows.
    SettingsControls.Caption {
        tone: look
        visible: (sheet.gameMarks.blocked || []).length > 0
        text: i18n("Needs Windows")
    }
    SettingsControls.Card {
        tone: look
        visible: (sheet.gameMarks.blocked || []).length > 0
        Repeater {
            model: sheet.gameMarks.blocked || []
            SettingsControls.SettingRow {
                id: blockedRow
                required property var modelData
                required property int index
                tone: look
                divider: index > 0
                title: modelData.name
                detail: modelData.shared ? i18n("Its anti-cheat only allows Windows. It's in Windows games, ready there.")
                    : modelData.onWindows ? i18n("Its anti-cheat only allows Windows. It's there too.")
                    : (sheet.gameInfo.shared || {}).steam ? i18n("Its anti-cheat only allows Windows. In Steam, move it to Windows games (Properties, Installed Files, Move install folder), and it's ready there.")
                    : i18n("Its anti-cheat only allows Windows. Install it in Windows' Steam to play.")
                SettingsControls.Pill {
                    tone: look
                    visible: blockedRow.modelData.onWindows === true
                    text: i18n("Play on Windows…")
                    onClicked: {
                        sheet.page = "windows"
                        sheet.asking = ({ id: "steam:" + blockedRow.modelData.id, name: blockedRow.modelData.name })
                    }
                }
            }
        }
    }
    Text {
        horizontalAlignment: Text.AlignLeft
        Layout.fillWidth: true
        visible: (sheet.gameMarks.blocked || []).length > 0
        text: i18n("Which games need Windows comes from AreWeAntiCheatYet and ProtonDB.")
        color: look.dim
        font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
        wrapMode: Text.Wrap
    }
    SettingsControls.Pill {
        tone: look
        text: i18n("More controller settings…")
        onClicked: sheet.ask("kde gamecontroller")
    }
}
