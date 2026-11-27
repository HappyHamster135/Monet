import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kirigami as K
import org.kde.plasma.private.volume 0.1 as Audio
import org.kde.plasma.private.brightnesscontrolplugin as Brightness

C.ScrollView {
    id: controls
    implicitWidth: 240; implicitHeight: 240
    required property bool soundAvailable
    required property bool brightnessAvailable
    property var shortcuts: []
    signal selected(string key)
    clip: true; contentWidth: availableWidth
    readonly property var output: soundAvailable ? Audio.PreferredDevice.sink : null
    readonly property var input: soundAvailable ? Audio.PreferredDevice.source : null
    readonly property bool hasControls: !!output || !!input || brightnessLevels.count > 0 || shortcuts.length > 0
    Brightness.ScreenBrightnessControl { id: display; isSilent: true }
    ColumnLayout {
        width: controls.availableWidth
        spacing: 12
        IslandEmpty {
            Layout.fillWidth: true; Layout.preferredHeight: Math.max(100, controls.availableHeight)
            visible: !controls.hasControls
            symbol: "preferences-system"; title: i18n("No controls available")
            detail: i18n("Connect an audio device or a display with brightness controls.")
        }
        component Level: RowLayout {
            id: row
            required property string title
            required property int percent
            property string glyph: "brightness-high"
            signal adjusted(int percent)
            spacing: 10
            K.Icon {
                source: row.glyph; isMask: true; color: "#ededf2"
                Layout.preferredWidth: 18; Layout.preferredHeight: 18

            }
            C.Slider {
                id: slider
                from: 0; to: 100; stepSize: 1; Layout.fillWidth: true
                Accessible.name: row.title
                value: row.percent
                implicitHeight: 28; leftPadding: 0; rightPadding: 0


                background: Rectangle {
                    x: slider.leftPadding; y: (slider.height - height) / 2
                    width: slider.availableWidth; height: 8; radius: 4
                    color: "#37373b"; border.width: slider.visualFocus ? 1 : 0; border.color: "#a3caff"
                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        x: slider.mirrored ? parent.width - width : 0
                        width: slider.position * parent.width; height: parent.height; radius: parent.radius
                        color: slider.pressed ? "#ffffff" : "#dedee3"
                    }
                }
                handle: Rectangle {
                    x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
                    y: (slider.height - height) / 2; implicitHeight: 12; implicitWidth: 12; radius: 6
                    color: "#ffffff"
                }
                onMoved: row.adjusted(Math.round(value))
            }
        }
        Level {
            visible: !!controls.output
            Layout.fillWidth: true; title: i18n("Output volume")
            glyph: controls.output?.muted ? "audio-volume-muted" : "audio-volume-high"
            percent: controls.output ? Math.round(100 * controls.output.volume / Audio.PulseAudio.NormalVolume) : 0
            onAdjusted: percent => {
                if (!controls.output) return
                controls.output.volume = Math.round(percent * Audio.PulseAudio.NormalVolume / 100)
                if (percent > 0 && controls.output.muted) controls.output.muted = false
            }
        }
        Repeater {
            id: brightnessLevels
            model: controls.brightnessAvailable ? display.displays : null
            Level {
                required property var model
                Layout.fillWidth: true; enabled: model.maxBrightness > 0
                title: i18n("Brightness on %1", model.label || model.displayName)
                percent: enabled ? Math.round(model.brightness * 100 / model.maxBrightness) : 0
                onAdjusted: percent => display.setBrightness(model.displayName, Math.round(percent * model.maxBrightness / 100))
            }
        }
        GridLayout {
            Layout.fillWidth: true
            columns: Math.max(1, Math.floor(controls.availableWidth / 76))
            rowSpacing: 7; columnSpacing: 7
            IslandActionTile {
                Layout.fillWidth: true; Layout.preferredWidth: 1
                visible: !!controls.output; diameter: 40
                text: controls.output?.muted ? i18n("Unmute") : i18n("Mute")
                symbol: controls.output?.muted ? "muted" : "volume"
                icon.name: controls.output?.muted ? "audio-volume-muted" : "audio-volume-high"
                checked: !!controls.output?.muted
                onClicked: controls.output.muted = !controls.output.muted
            }
            IslandActionTile {
                Layout.fillWidth: true; Layout.preferredWidth: 1
                visible: !!controls.input; diameter: 40
                text: i18n("Microphone"); icon.name: controls.input?.muted ? "microphone-sensitivity-muted" : "audio-input-microphone"
                symbol: "mic"
                Accessible.description: controls.input?.muted ? i18n("Muted") : i18n("On")
                checked: !!controls.input?.muted
                onClicked: controls.input.muted = !controls.input.muted
            }
            Repeater {
                model: controls.shortcuts
                IslandActionTile {
                    required property var modelData
                    objectName: "notch-control-" + modelData.key
                    Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.minimumWidth: 0
                    diameter: 40; text: modelData.label; icon.name: modelData.icon
                    symbol: modelData.key
                    onClicked: controls.selected(modelData.key)
                }
            }
        }
    }
}
