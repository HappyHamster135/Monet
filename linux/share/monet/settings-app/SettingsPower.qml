// Loaded by the Settings page loader; shares its window context.
import QtCore
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Templates as T
import QtQuick.Window
import org.kde.plasma.workspace.dbus as DBus
import org.kde.kirigami as Kirigami
import "../games" as Shared
import "FocusNavigation.js" as FocusNavigation


ColumnLayout {
    id: powerColumn
    readonly property var screenTimes: [300, 600, 1800, 3600, 0].map(s => [s, sheet.span(s)])
    readonly property var sleepTimes: [900, 1800, 3600, 7200, 0].map(s => [s, sheet.span(s)])
    // On battery, KDE sleeps after 10 minutes: shorter times, that one among them, and 15
    // (the shortest this offered before, so a time chosen then still shows).
    readonly property var batterySleepTimes: [300, 600, 900, 1800, 3600, 0].map(s => [s, sheet.span(s)])
    spacing: 20
    DBus.SignalWatcher {
        enabled: sheet.pollingActive
        busType: DBus.BusType.Session; service: "org.monet.KeepAwake"
        path: "/org/monet/KeepAwake"; iface: "org.monet.KeepAwake"
        function dbusStatusChanged(value) {
            const state = sheet.json(value, {})
            if (typeof state.active !== "boolean") return
            sheet.keepAwakeRevision++
            sheet.keepAwakeProblem = ""
            sheet.keepAwakeInfo = state
            sheet.keepAwakeTick++
        }
    }
    DBus.DBusServiceWatcher {
        watchedService: "org.monet.KeepAwake"; busType: DBus.BusType.Session
        onRegisteredChanged: {
            if (!sheet.pollingActive) return
            if (registered) { sheet.loadKeepAwake(); return }
            const interrupted = sheet.keepAwakeInfo.active || sheet.keepAwakeInfo.pending
            sheet.keepAwakeRevision++
            sheet.keepAwakeInfo = {active: false, duration: 0, error: interrupted ? "interrupted" : ""}
        }
    }
    SettingsControls.PageTitle {
        tone: look
        entry: sheet.entry("power")
        art: sheet.art
        text: i18n("Power & Sleep")
        detail: i18n("When the screen rests or locks, when the PC sleeps, and how hard it works.")
    }
    // The battery, on a laptop: how full, and charging or how long it lasts.
    SettingsControls.Card {
        tone: look
        visible: typeof sheet.info.battery === "number" || sheet.currentAnchor === "battery-limit"
        SettingsControls.SettingRow {
            tone: look
            divider: false
            visible: typeof sheet.info.battery === "number"
            title: i18n("Battery %1%", sheet.info.battery)
            objectName: "batteryStatusRow"
            detail: sheet.batteryDescription()
        }
        // Battery care, where the battery can do it (ThinkPads and many others): it stops at 80%.
        SettingsControls.SettingRow {
            tone: look
            visible: sheet.batteryCare.supported === true || sheet.currentAnchor === "battery-limit"
            tappable: sheet.batteryCare.supported === true
            objectName: "search-battery-limit"
            title: i18n("Protect the battery")
            detail: sheet.batteryCare.supported === true
                ? i18n("Stops charging at 80%, so the battery lasts more years. Best for a laptop that's mostly plugged in.")
                : sheet.batteryCare.supported === false ? i18n("This PC doesn't report support for a charging limit.")
                : i18n("Checking charging-limit support…")
            onTapped: {
                const limit = sheet.batteryCare.limit <= 80 ? 100 : 80
                sheet.batteryCare = { supported: true, limit: limit }
                sheet.ask("battery-limit " + limit, () => sheet.ask("battery-care", out => sheet.batteryCare = sheet.json(out, sheet.batteryCare)))
            }
            SettingsControls.Switch {
                tone: look
                visible: sheet.batteryCare.supported === true
                active: sheet.batteryCare.limit <= 80
            }
        }
    }
    // Native demand scaling in Automatic; fixed preferences remain available.
    SettingsControls.ChoiceGrid {
        optionCount: powerModeOptions.count
        visible: (sheet.powerInfo.modes || []).length > 0
        Repeater {
            id: powerModeOptions
            model: [
                ["automatic", i18n("Automatic"), i18n("Uses more power when needed and saves energy during lighter work"),
                 "M4 12h16M12 4v16M5 5l14 14M5 19L19 5"],
                ["power-saver", i18n("Power saver"), sheet.powerInfo.hasBattery
                    ? i18n("Uses less power to extend battery life") : i18n("Favors lower power use and less heat"),
                 "M5 19c0-9 5-14 14-14c0 9-5 14-14 14zM5 19l7-7"],
                ["balanced", i18n("Balanced"), i18n("Quick when it counts"),
                 "M12 4v16M6 8h12M6 8l-3 6a3 3 0 0 0 6 0zM18 8l-3 6a3 3 0 0 0 6 0zM8 20h8"],
                ["performance", i18n("Performance"), i18n("Favors faster response, with potentially more heat and fan noise"),
                 "M13 3L5 13h6l-1 8 8-10h-6z"]
            ].filter(m => (sheet.powerInfo.modes || []).indexOf(m[0]) !== -1)
            Rectangle {
                id: modeChoice
                objectName: "powerMode-" + modelData[0]
                required property var modelData
                readonly property bool picked: sheet.powerInfo.mode === modelData[0]
                enabled: !sheet.powerBusy
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 1
                implicitHeight: modeColumn.implicitHeight + 28
                radius: 18
                color: picked ? Qt.rgba(0.302, 0.706, 0.627, 0.1) : modeHover.hovered ? look.wash2 : look.wash
                border.width: picked || activeFocus ? 2 : 1
                border.color: picked || activeFocus ? look.lily : look.line
                scale: modeTap.pressed ? 0.98 : 1
                activeFocusOnTab: true
                Keys.onSpacePressed: sheet.powerMode(modelData[0])
                Keys.onReturnPressed: sheet.powerMode(modelData[0])
                Keys.onEnterPressed: sheet.powerMode(modelData[0])
                Behavior on scale { NumberAnimation { duration: Math.round(160 * sheet.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }
                Behavior on color { ColorAnimation { duration: Math.round(160 * sheet.speed) } }
                ColumnLayout {
                    id: modeColumn
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 14
                    spacing: 4
                    SettingsControls.Glyph {
                        Layout.preferredWidth: 22
                        Layout.preferredHeight: 22
                        Layout.bottomMargin: 6
                        path: modeChoice.modelData[3]
                        color: modeChoice.picked ? look.lily : look.ink
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        text: modeChoice.modelData[1]
                        color: look.ink
                        font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
                        font.weight: Font.DemiBold
                        wrapMode: Text.Wrap
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        text: modeChoice.modelData[2]
                        color: look.dim
                        font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                        wrapMode: Text.Wrap
                    }
                }
                HoverHandler { id: modeHover }
                TapHandler {
                    id: modeTap
                    onTapped: sheet.powerMode(modeChoice.modelData[0])
                }
                Accessible.role: Accessible.RadioButton
                Accessible.name: modelData[1]
                Accessible.description: modelData[2]
                Accessible.checked: picked
                Accessible.onPressAction: sheet.powerMode(modelData[0])
            }
        }
    }
    Text {
        objectName: "powerSettingProblem"
        Layout.fillWidth: true
        visible: sheet.powerProblem !== "" || sheet.powerBusy
        text: sheet.powerBusy ? i18n("Changing power settings…") : sheet.powerProblem
        wrapMode: Text.Wrap
        color: sheet.powerBusy ? look.dim : Kirigami.Theme.negativeTextColor
    }
    SettingsControls.Card {
        tone: look
        visible: sheet.powerInfo.hasBattery === true && (sheet.powerInfo.modes || []).indexOf("power-saver") !== -1
        SettingsControls.SettingRow {
            tone: look
            objectName: "automaticBatterySaver"
            title: i18n("Automatic battery saver")
            checkable: true
            checked: sheet.powerInfo.batterySaverAuto === true
            detail: sheet.powerInfo.batterySaverAuto === true
                ? i18n("Turns on at %1% on battery. Plug in to return to your normal power mode.", sheet.powerInfo.batterySaverThreshold || 20)
                : i18n("Choose when to use Power saver yourself.")
            tappable: !sheet.powerBusy
            onTapped: sheet.changePower("battery-saver " + (sheet.powerInfo.batterySaverAuto ? "off" : "automatic"))
            SettingsControls.Switch { objectName: "batterySaverSwitch"; tone: look; active: sheet.powerInfo.batterySaverAuto === true }
        }
        SettingsControls.SettingRow {
            tone: look
            divider: false
            visible: sheet.powerInfo.batterySaverAuto === true
            title: i18n("Turn on battery saver at")
            objectName: "batterySaverThresholdRow"
            SettingsControls.Segments {
                tone: look
                objectName: "batterySaverThreshold"
                enabled: !sheet.powerBusy
                options: [10, 20, 30, 50, sheet.powerInfo.batterySaverThreshold || 20]
                    .filter((value, index, values) => value > (sheet.powerInfo.batteryCriticalLevel || 5) && values.indexOf(value) === index)
                    .sort((a, b) => a - b).map(v => [v, i18n("%1%", v)])
                current: sheet.powerInfo.batterySaverThreshold || 20
                onPicked: value => sheet.changePower("battery-saver threshold " + value)
            }
        }
        SettingsControls.SettingRow {
            tone: look
            divider: false
            visible: sheet.powerInfo.activeMode === "power-saver"
            title: i18n("Power saver is active")
            detail: i18n("Background updates already wait while Power saver is on.")
        }
    }
    // Plugged in, and on battery when there is one.
    Repeater {
        model: sheet.powerInfo.hasBattery === true ? [["ac", i18n("Plugged in")], ["battery", i18n("On battery")]] : [["ac", ""]]
        ColumnLayout {
            id: powerState
            required property var modelData
            readonly property var times: sheet.powerInfo[modelData[0]] || {}
            Layout.fillWidth: true
            spacing: 20
            SettingsControls.Caption {
                tone: look
                visible: powerState.modelData[1] !== ""
                text: powerState.modelData[1]
            }
            SettingsControls.Card {
                tone: look
                SettingsControls.SettingRow {
                    tone: look
                    divider: false
                    title: i18n("Turn off the screen")
                    detail: i18n("After this long untouched")
                    SettingsControls.Segments {
                        tone: look
                        options: powerColumn.screenTimes
                        current: powerState.times.screen
                        onPicked: value => sheet.powerTime(powerState.modelData[0], "screen", value)
                    }
                }
                SettingsControls.SettingRow {
                    tone: look
                    title: i18n("Sleep")
                    detail: i18n("It wakes where you left off")
                    SettingsControls.Segments {
                        tone: look
                        options: powerState.modelData[0] === "battery" ? powerColumn.batterySleepTimes : powerColumn.sleepTimes
                        current: powerState.times.sleep
                        onPicked: value => sheet.powerTime(powerState.modelData[0], "sleep", value)
                    }
                }
            }
        }
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            objectName: "search-keep-awake"
            title: i18n("Keep awake")
            detail: sheet.keepAwakeDescription()
            SettingsControls.Segments {
                objectName: "keepAwakeDuration"
                tone: look
                enabled: !sheet.keepAwakeBusy
                options: [[0, i18n("Off")], [1800, i18n("30 min")], [3600, i18n("1 hour")], [-1, i18n("Until off")]]
                current: sheet.keepAwakeInfo.active === true ? sheet.keepAwakeInfo.duration : 0
                onPicked: value => sheet.changeKeepAwake(value)
            }
        }
        Text {
            Layout.fillWidth: true
            Layout.margins: 18
            text: i18n("A manual timer keeps the screen on and delays automatic locking and sleep until it ends.")
            color: look.dim
            font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
            wrapMode: Text.Wrap
        }
        SettingsControls.SettingRow {
            tone: look
            divider: false
            tappable: true
            title: i18n("Automatic Keep awake rules")
            detail: i18n("While plugged in, using an external display or running selected apps")
            onTapped: sheet.ask("utilities awake settings")
            SettingsControls.Glyph {
                width: 16; height: 16; path: "M9 5l7 7-7 7"; color: look.dim
            }
        }
    }
    SettingsControls.Caption {
        tone: look
        text: i18n("Locking")
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Lock the screen")
            objectName: "search-lock"
            detail: i18n("Locks after this long untouched, even when sleep is off")
            SettingsControls.Segments {
                tone: look
                objectName: "autoLockTime"
                options: [[1, i18n("1 min")], [5, i18n("5 min")], [15, i18n("15 min")], [30, i18n("30 min")],
                          [0, i18n("Never")]]
                current: typeof sheet.powerInfo.lockAfter === "number" ? sheet.powerInfo.lockAfter : 5
                onPicked: value => sheet.powerLock("lockAfter", value)
            }
        }
        SettingsControls.SettingRow {
            tone: look
            tappable: true
            title: i18n("Ask for the password after sleep")
            objectName: "lockOnResumeRow"
            checkable: true
            checked: sheet.powerInfo.lockOnResume !== false
            detail: i18n("Waking the PC shows the lock screen")
            onTapped: sheet.powerLock("lockOnResume", sheet.powerInfo.lockOnResume === false)
            SettingsControls.Switch {
                tone: look
                active: sheet.powerInfo.lockOnResume !== false
            }
        }
        SettingsControls.SettingRow {
            tone: look
            title: i18n("Lock now")
            detail: i18n("Or press the Windows key and L")
            SettingsControls.Pill {
                tone: look
                text: i18n("Lock")
                onClicked: sheet.ask("lock-now")
            }
        }
    }
    SettingsControls.Caption {
        tone: look
        text: i18n("Buttons")
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Power button")
            detail: i18n("What a press does")
            SettingsControls.Segments {
                tone: look
                options: [[16, i18n("Ask")], [1, i18n("Sleep")], [8, i18n("Shut down")], [0, i18n("Nothing")]]
                current: sheet.powerInfo.button
                onPicked: value => sheet.powerAction("button", value)
            }
        }
        SettingsControls.SettingRow {
            tone: look
            visible: sheet.powerInfo.hasLid === true
            title: i18n("Closing the lid")
            SettingsControls.Segments {
                tone: look
                objectName: "lidActionChoices"
                options: [[1, i18n("Sleep")], [32, i18n("Lock")], [64, i18n("Screen off")], [0, i18n("Nothing")]]
                current: sheet.powerInfo.lidAction
                onPicked: value => sheet.powerAction("lid", value)
            }
        }
    }
    SettingsControls.Caption {
        tone: look
        text: i18n("When you restart")
    }
    SettingsControls.Card {
        tone: look
        // After a restart, a sign-out, a crash or a power cut, and after Windows: the same
        // switch as Play on Windows' (monet-work keeps the work; monet-quick reopens it).
        SettingsControls.SettingRow {
            tone: look
            divider: false
            tappable: true
            checkable: true
            checked: sheet.ready.apps !== false
            objectName: "search-reopen"
            title: i18n("Reopen your work")
            detail: i18n("After a restart, a sign-out or a trip to Windows, your apps come back on the same screens and desktops, where they were, with saved documents and Files tabs. Unsaved changes and private tabs aren't kept.")
            onTapped: sheet.setReopenWork(sheet.ready.apps === false)
            SettingsControls.Switch {
                tone: look
                active: sheet.ready.apps !== false
            }
        }
    }
    // Only when something didn't reopen after the last restart: with everything back,
    // there's nothing to say.
    Loader {
        Layout.fillWidth: true
        active: sheet.returnInfo.available === true && sheet.returnInfo.kind === "restart"
            && (sheet.returnInfo.items || []).some(item => item.needsAttention === true || item.retry === true)
        visible: active
        sourceComponent: returnSummary
    }
    SettingsControls.Pill {
        tone: look
        text: i18n("More power settings…")
        onClicked: sheet.ask("kde power")
    }
}
