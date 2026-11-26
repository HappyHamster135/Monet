import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kirigami as K
import org.kde.plasma.private.volume 0.1 as Audio
import org.kde.plasma.private.brightnesscontrolplugin as Brightness

C.ScrollView {
    id: controls
    required property bool soundAvailable
    required property bool brightnessAvailable
    clip: true; contentWidth: availableWidth
    readonly property var output: soundAvailable ? Audio.PreferredDevice.sink : null
    readonly property var input: soundAvailable ? Audio.PreferredDevice.source : null
    Brightness.ScreenBrightnessControl { id: display; isSilent: true }
    ColumnLayout {
        width: controls.availableWidth
        spacing: 12
        component Level: ColumnLayout {
            id: row
            required property string title
            required property int percent
            signal adjusted(int percent)
            spacing: 3
            RowLayout {
                Text { text: row.title; textFormat: Text.PlainText; color: "white"; elide: Text.ElideRight; Layout.fillWidth: true; font.weight: Font.Medium }
                Text { text: Math.round(slider.pressed ? slider.value : row.percent) + "%"; color: "#c2c2c7" }
            }
            C.Slider {
                id: slider
                from: 0; to: 100; stepSize: 1; Layout.fillWidth: true
                Accessible.name: row.title
                value: row.percent
                implicitHeight: 30; leftPadding: 0; rightPadding: 0
                background: Rectangle {
                    x: slider.leftPadding; y: (slider.height - height) / 2
                    width: slider.availableWidth; height: 16; radius: 8
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
                    y: (slider.height - height) / 2; implicitHeight: 16; implicitWidth: 16; radius: 8
                    color: "#ffffff"
                }
                onMoved: row.adjusted(Math.round(value))
            }
        }
        Level {
            visible: !!controls.output
            Layout.fillWidth: true; title: i18n("Output volume")
            percent: controls.output ? Math.round(100 * controls.output.volume / Audio.PulseAudio.NormalVolume) : 0
            onAdjusted: percent => {
                if (!controls.output) return
                controls.output.volume = Math.round(percent * Audio.PulseAudio.NormalVolume / 100)
                if (percent > 0 && controls.output.muted) controls.output.muted = false
            }
        }
        Repeater {
            model: controls.brightnessAvailable ? display.displays : null
            Level {
                required property var model
                Layout.fillWidth: true; enabled: model.maxBrightness > 0
                title: i18n("Brightness on %1", model.label || model.displayName)
                percent: enabled ? Math.round(model.brightness * 100 / model.maxBrightness) : 0
                onAdjusted: percent => display.setBrightness(model.displayName, Math.round(percent * model.maxBrightness / 100))
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 7
            IslandButton {
                Layout.fillWidth: true; Layout.preferredWidth: 1
                visible: !!controls.output; tile: true
                text: controls.output?.muted ? i18n("Unmute") : i18n("Mute")
                icon.name: controls.output?.muted ? "audio-volume-muted" : "audio-volume-high"
                checked: !!controls.output?.muted
                onClicked: controls.output.muted = !controls.output.muted
            }
            IslandButton {
                Layout.fillWidth: true; Layout.preferredWidth: 1
                visible: !!controls.input; tile: true
                text: i18n("Microphone"); icon.name: controls.input?.muted ? "microphone-sensitivity-muted" : "audio-input-microphone"
                Accessible.description: controls.input?.muted ? i18n("Muted") : i18n("On")
                checked: !!controls.input?.muted
                onClicked: controls.input.muted = !controls.input.muted
            }
        }
    }
}
