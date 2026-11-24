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
    id: soundColumn
    readonly property var speakers: sheet.outputs.filter(o => !o.none)
    property bool showAllOutputs: false
    readonly property var visibleSpeakers: showAllOutputs || speakers.length <= 3
        ? speakers : [speakers.find(o => o.default) || speakers[0]]
    spacing: 20
    SettingsControls.PageTitle {
        readonly property var playing: sheet.outputs.find(o => o.default)
        tone: look
        entry: sheet.entry("sound")
        art: sheet.art
        text: i18n("Sound")
        detail: !playing ? "" : playing.none ? i18n("No speakers or headphones") : i18n("Playing through %1", playing.name)
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SliderRow {
            tone: look
            divider: false
            title: i18n("Volume")
            value: sheet.info.volume || 0
            onHeld: down => sheet.dragging = down
            onMoved: value => sheet.queue("volume", value)
        }
    }
    SettingsControls.Caption {
        tone: look
        visible: soundColumn.speakers.length > 0
        text: i18n("Play sound through")
    }
    SettingsControls.Card {
        tone: look
        objectName: "search-output"
        Accessible.role: Accessible.Grouping
        Accessible.name: i18n("Headphones and speakers")
        SettingsControls.SettingRow {
            tone: look
            visible: soundColumn.speakers.length === 0
            divider: false
            title: i18n("No speakers or headphones")
            detail: i18n("Connect an audio device, or pair wireless headphones in Bluetooth.")
            SettingsControls.Pill {
                tone: look
                text: i18n("Bluetooth")
                onClicked: sheet.open("bluetooth")
            }
        }
        Repeater {
            model: soundColumn.visibleSpeakers
            SettingsControls.SettingRow {
                tone: look
                divider: index > 0
                tappable: !sheet.outputBusy
                strong: false
                title: modelData.name
                // Asked for: checked only once the sound is seen playing there.
                detail: sheet.outputBusy && sheet.sameDevice(modelData, sheet.outputWanted) ? i18n("Changing…") : modelData.detail || ""
                onTapped: sheet.pickOutput(modelData)
                lead: SettingsControls.Glyph {
                    width: 18
                    height: 18
                    path: sheet.outputGlyph(modelData.name)
                    color: look.ink
                    opacity: modelData.default === true ? 1 : 0.6
                }
                SettingsControls.Check {
                    tone: look
                    active: modelData.default === true
                }
                SettingsControls.Pill {
                    tone: look
                    visible: typeof modelData.key === "string"
                    text: i18n("Rename…")
                    objectName: "renameOutput-" + modelData.id
                    onClicked: { sheet.audioRename = {key:modelData.key, name:modelData.name}; sheet.audioRenameProblem = ""; audioName.text = modelData.name; Qt.callLater(() => audioName.forceActiveFocus()) }
                }
            }
        }
        SettingsControls.SettingRow {
            tone: look
            visible: sheet.audioRename !== null
            title: i18n("Device name")
            detail: sheet.audioRenameProblem || i18n("This name is used in Settings and the taskbar. Leave it empty to use the device's original name.")
            ColumnLayout {
                QQC2.TextField {
                    id: audioName
                    objectName: "audioDeviceName"
                    maximumLength: 80
                    enabled: !sheet.audioRenameBusy
                    Accessible.name: i18n("Device name")
                    Keys.onEscapePressed: event => { sheet.audioRename = null; event.accepted = true }
                }
                RowLayout {
                    SettingsControls.Pill { tone: look; text: i18n("Cancel"); enabledPill: !sheet.audioRenameBusy; onClicked: sheet.audioRename = null }
                    SettingsControls.Pill {
                        tone: look; text: i18n("Save"); enabledPill: !sheet.audioRenameBusy
                        onClicked: {
                            if (!sheet.audioRename) return
                            sheet.audioRenameBusy = true
                            sheet.call(["helper", "audio-name", sheet.audioRename.key, sheet.hex(audioName.text)], out => {
                                sheet.audioRenameBusy = false
                                if (sheet.json(out, {}).ok === true) { sheet.audioRename = null; sheet.refresh() }
                                else sheet.audioRenameProblem = i18n("The name couldn't be saved. Try again.")
                            })
                        }
                    }
                }
            }
        }
        SettingsControls.SettingRow {
            objectName: "outputProblem"
            tone: look
            visible: sheet.outputProblem !== "" && !sheet.outputBusy
            divider: soundColumn.speakers.length > 0
            strong: false
            title: sheet.outputProblem
            Accessible.role: Accessible.AlertMessage
            SettingsControls.Pill {
                tone: look
                text: i18n("Try again")
                enabledPill: !sheet.outputBusy && sheet.outputWanted !== null
                onClicked: sheet.pickOutput(sheet.outputWanted)
            }
        }
    }
    SettingsControls.Pill {
        tone: look
        visible: soundColumn.speakers.length > 3
        text: soundColumn.showAllOutputs ? i18n("Show selected output") : i18n("Show all %1 outputs", soundColumn.speakers.length)
        onClicked: soundColumn.showAllOutputs = !soundColumn.showAllOutputs
    }
    OutputOrder { tone: look; host: sheet }
    SettingsControls.Card {
        tone: look
        SettingsControls.SliderRow {
            id: eventVolume
            tone: look
            divider: false
            enabled: sheet.notificationAudio.ok === true
            title: i18n("Notification volume")
            value: sheet.notificationAudio.volume ?? 35
            onHeld: down => sheet.dragging = down
            onMoved: level => {
                eventSave.level = Math.round(level)
                eventSave.restart()
            }
        }
        SettingsControls.SettingRow {
            tone: look
            title: i18n("Preview notification sound")
            detail: sheet.notificationAudioProblem || (sheet.notificationAudio.ok === false
                ? i18n("Notification audio is unavailable.")
                : sheet.notificationAudio.ok === true
                ? i18n("Plays the current notification tone at the selected volume.")
                : i18n("Checking notification audio…"))
            SettingsControls.Pill {
                tone: look
                text: sheet.notificationAudio.ok === false ? i18n("Try again") : i18n("Play test")
                enabledPill: sheet.notificationAudio.ok === false
                    || (eventVolume.enabled && !eventSave.running && !sheet.notificationAudioSaving)
                onClicked: {
                    if (sheet.notificationAudio.ok === false) {
                        sheet.loadNotificationAudio()
                    } else {
                        sheet.ask("notification-audio-test", out => {
                            sheet.notificationAudioProblem = sheet.json(out, {}).ok ? "" : i18n("Couldn't play the test sound.")
                        })
                    }
                }
            }
        }
    }
    Timer {
        id: eventSave
        property int level: 35
        interval: 240
        onTriggered: {
            if (sheet.notificationAudioSaving)
                restart()
            else
                sheet.setNotificationAudio(level)
        }
    }
    Component.onCompleted: sheet.loadNotificationAudio()
    SettingsControls.Caption {
        tone: look; objectName: "search-mixer"
        text: i18n("Volume mixer")
    }
    SettingsControls.Card {
        tone: look; visible: appMixer.status === Loader.Ready
        Loader {
            id: appMixer; active: sheet.pollingActive
            Layout.fillWidth: true; Layout.margins: 12
            Layout.preferredHeight: item ? Math.min(420, Math.max(38, item.contentHeight)) : 0
            source: "VolumeMixer.qml"
            onLoaded: {
                item.showOutput = false
                item.outputNames = Qt.binding(() => sheet.outputs)
            }
        }
    }
    QQC2.Label {
        visible: appMixer.status === Loader.Error && !sheet.appsSound.length
        text: i18n("Apps appear here when they play sound.")
        wrapMode: Text.Wrap
        Layout.fillWidth: true
    }
    SettingsControls.Card {
        tone: look
        visible: !(appMixer.active && appMixer.status === Loader.Ready) && sheet.appsSound.length > 0
        Repeater {
            model: sheet.appsSound
            SettingsControls.SliderRow {
                required property var modelData
                required property int index
                tone: look
                divider: index > 0
                title: modelData.name
                value: modelData.volume
                onHeld: down => sheet.dragging = down
                onMoved: value => sheet.queue("app-volume " + (modelData.ids || [modelData.id]).join(","), value)
            }
        }
    }
    Timer {
        interval: 3000
        repeat: true
        triggeredOnStart: true
        running: sheet.page === "sound" && sheet.pollingActive
        onTriggered: {
            if (!appMixer.active || appMixer.status === Loader.Error) sheet.loadAppsSound()
            sheet.loadMicrophones()
        }
    }
    SettingsControls.Caption {
        tone: look
        visible: sheet.microphones.length > 1 || sheet.microphoneProblem !== ""
        text: i18n("Record from")
    }
    SettingsControls.Card {
        tone: look
        objectName: "search-microphone-choice"
        // Kept while it says why a microphone wasn't chosen, even if that one has gone.
        visible: sheet.microphones.length > 1 || sheet.microphoneProblem !== ""
        Accessible.role: Accessible.Grouping
        Accessible.name: i18n("Microphones")
        Repeater {
            model: sheet.microphones
            SettingsControls.SettingRow {
                required property var modelData
                required property int index
                tone: look
                divider: index > 0
                tappable: !sheet.microphoneBusy
                strong: false
                title: modelData.name
                // Asked for: checked only once it's seen in use.
                detail: sheet.microphoneBusy && sheet.sameDevice(modelData, sheet.microphoneWanted) ? i18n("Changing…") : ""
                onTapped: sheet.pickMicrophone(modelData)
                SettingsControls.Check {
                    tone: look
                    active: modelData.default === true
                }
            }
        }
        SettingsControls.SettingRow {
            objectName: "microphoneProblem"
            tone: look
            visible: sheet.microphoneProblem !== "" && !sheet.microphoneBusy
            divider: sheet.microphones.length > 0
            strong: false
            title: sheet.microphoneProblem
            Accessible.role: Accessible.AlertMessage
            SettingsControls.Pill {
                tone: look
                text: i18n("Try again")
                enabledPill: !sheet.microphoneBusy && sheet.microphoneWanted !== null
                onClicked: sheet.pickMicrophone(sheet.microphoneWanted)
            }
        }
    }
    SettingsControls.Card {
        tone: look
        objectName: "search-microphone"
        Accessible.role: Accessible.Grouping
        Accessible.name: i18n("Microphone")
        SettingsControls.SettingRow {
            tone: look
            divider: false
            visible: typeof sheet.info.mic !== "number"
            title: i18n("No microphone found")
            detail: i18n("Connect a microphone or headset. If it still isn't found, its channels can be set up in Advanced sound settings below.")
        }
        SettingsControls.SliderRow {
            tone: look
            visible: typeof sheet.info.mic === "number"
            divider: false
            title: i18n("Microphone volume")
            value: sheet.info.mic || 0
            onHeld: down => sheet.dragging = down
            onMoved: value => sheet.queue("mic", value)
        }
    }
    SettingsControls.Pill {
        tone: look
        text: i18n("Advanced sound settings…")
        Accessible.description: i18n("Each sound device's profile and channels")
        onClicked: sheet.ask("kde sound")
    }
    SettingsControls.Caption {
        tone: look
        text: i18n("Only needed for a device's profile or channels, such as surround sound or an interface's direct monitoring.")
    }
}
