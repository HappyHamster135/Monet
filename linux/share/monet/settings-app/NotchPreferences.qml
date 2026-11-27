import QtQuick
import "../panel" as EditorUI
import QtQuick.Layouts
import QtQuick.Controls as C

SettingsControls.Card {
    id: prefs
    objectName: "search-notch"
    tone: look
    property bool expanded: false
    property bool loading: false
    property var screens: []
    property int selected: 0
    property var notchState: ({})
    property bool savesImages: false
    property string problem: ""
    function query(choice) {
        const host = screens[selected]
        if (!host) return
        loading = true
        sheet.ask("panel-notch " + host.id + (choice ? " " + choice : ""), (out, code) => {
            const result = sheet.json(out, {})
            loading = false
            if (result.ok) { notchState = result; problem = "" }
            else problem = i18n("Could not change notch settings.")
        })
    }
    Component.onCompleted: if (sheet.currentAnchor === "notch" && !expanded) discover()
    Connections {
        target: sheet
        function onCurrentAnchorChanged() {
            if (sheet.currentAnchor === "notch" && !prefs.expanded) prefs.discover()
        }
    }
    function clipboardImages(mode) {
        sheet.ask("notch-copied-images" + (mode ? " "+mode : ""), (out, code) => {
            const result = sheet.json(out, {})
            if (result.ok) savesImages = result.enabled
            else problem = i18n("Could not change notch settings.")
        })
    }
    function discover() {
        expanded = !expanded
        if (!expanded) return
        loading = true
        clipboardImages("")
        sheet.ask("notch-screens", (out, code) => {
            screens = sheet.json(out, []); selected = 0; loading = false
            if (screens.length) query("")
            else problem = i18n("No desktop panel is available.")
        })
    }
    SettingsControls.SettingRow {
        tone: look; title: i18n("Notch"); divider: false
        detail: i18n("Choose its size, pages and controls.")
        tappable: true; onTapped: prefs.discover()
        SettingsControls.Pill { tone: look; text: i18n("Customize"); onClicked: prefs.discover() }
    }
    ColumnLayout {
        visible: prefs.expanded; Layout.fillWidth: true; spacing: 8
        C.ComboBox {
            visible: prefs.screens.length > 1; enabled: !prefs.loading
            model: prefs.screens.map(host => i18n("Screen %1",host.screen+1))
            onActivated: index => { prefs.selected = index; prefs.query("") }
        }
        EditorUI.NotchEditor {
            Layout.fillWidth: true
            notchState: prefs.notchState
            busy: prefs.loading
            onRequested: command => prefs.query(command)
        }
        C.Label { Layout.fillWidth: true; visible: !!prefs.problem; text: prefs.problem; wrapMode: Text.Wrap }
        C.CheckBox {
            visible: prefs.notchState.mode !== "off" && !!prefs.notchState.mode
            text: i18n("Keep copied images in Recent captures")
            checked: prefs.savesImages
            onClicked: prefs.clipboardImages(checked ? "on" : "off")
        }
    }
}
