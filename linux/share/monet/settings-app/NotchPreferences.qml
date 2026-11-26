import QtQuick
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
    property var state: ({})
    property bool savesImages: false
    property string problem: ""
    function query(choice) {
        const host = screens[selected]
        if (!host) return
        loading = true
        sheet.ask("panel-notch " + host.id + (choice ? " " + choice : ""), (out, code) => {
            const result = sheet.json(out, {})
            loading = false
            if (result.ok) { state = result; problem = "" }
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
        RowLayout {
            enabled: !prefs.loading && !!prefs.screens.length
            Repeater {
                model: [[i18n("Off"),"off"],[i18n("Compact"),"compact"],[i18n("Wide"),"wide"]]
                C.Button { required property var modelData
                    text: modelData[0]; checked: prefs.state.mode === modelData[1]
                    onClicked: prefs.query(modelData[1])
                }
            }
        }
        C.Label { visible: !!prefs.problem; text: prefs.problem; wrapMode: Text.Wrap }
        Flow {
            visible: !!prefs.state.mode && prefs.state.mode !== "off"; Layout.fillWidth: true; spacing: 5
            enabled: !prefs.loading
            Repeater {
                model: [["music",i18n("Music")],["activity",i18n("Activity")],["time",i18n("Time")],
                    ["calendar",i18n("Calendar")],["notes",i18n("Notes")],["camera",i18n("Camera")],
                    ["clipboard",i18n("Clipboard")],["tools",i18n("Tools")],["agents",i18n("AI agents")],["notifications",i18n("Notifications")]]
                C.CheckBox { required property var modelData
                    text: modelData[1]; checked: (prefs.state.tabs || []).includes(modelData[0])
                    onClicked: prefs.query("tab-"+modelData[0]+(checked ? "-show" : "-hide"))
                }
            }
        }
        Flow {
            visible: !!prefs.state.mode && prefs.state.mode !== "off"; Layout.fillWidth: true; spacing: 5; enabled: !prefs.loading
            Repeater {
                model: [["gestures",i18n("Gestures")],["hoverControls",i18n("Hover controls")],["companion",i18n("Companion")],
                    ["levels",i18n("Audio levels")],["previews",i18n("Notification previews")],["alerts",i18n("Accessory alerts")],
                    ["awake",i18n("Keep awake")],["combined",i18n("Music and timer")],["countdown",i18n("Countdown")]]
                C.CheckBox { required property var modelData; text: modelData[1]
                    checked: !!prefs.state.options?.[modelData[0]]
                    onClicked: prefs.query(modelData[0]+(checked ? "-on" : "-off"))
                }
            }
        }
        C.CheckBox {
            visible: !!prefs.state.mode && prefs.state.mode !== "off"
            text: i18n("Keep copied images in Recent captures")
            checked: prefs.savesImages
            onClicked: prefs.clipboardImages(checked ? "on" : "off")
        }
        ColumnLayout {
            Layout.fillWidth: true
            visible: prefs.state.mode !== "off" && !!prefs.state.options?.companion
            Repeater {
                model: [
                    {key:"style", title:i18n( "Style"), keys:["soft","robot"], names:[i18n("Soft"),i18n("Robot")]},
                    {key:"shape", title:i18n( "Shape"), keys:["round","egg","square","pill"], names:[i18n("Round"),i18n("Egg"),i18n("Rounded square"),i18n("Capsule")]},
                    {key:"color", title:i18n( "Color"), keys:["mint","pearl","lemon","peach","rose","lilac","sky"], names:[i18n("Mint"),i18n("Pearl"),i18n("Lemon"),i18n("Peach"),i18n("Rose"),i18n("Lilac"),i18n("Sky")]},
                    {key:"side", title:i18n( "Side"), keys:["left","right"], names:[i18n("Left"),i18n("Right")]},
                    {key:"visits", title:i18n( "Visits"), keys:["off","rare","normal","frequent"], names:[i18n("Off"),i18n("Rare"),i18n("Regular"),i18n("Frequent")]}
                ]
                RowLayout {
                    id: field
                    required property var modelData
                    Layout.fillWidth: true
                    C.Label { Layout.fillWidth: true; text: field.modelData.title; wrapMode: Text.Wrap }
                    C.ComboBox {
                        objectName: "companion-" + field.modelData.key
                        Accessible.name: field.modelData.title
                        enabled: !prefs.loading
                        model: field.modelData.names
                        currentIndex: field.modelData.keys.indexOf((prefs.state.companionSettings || {})[field.modelData.key])
                        onActivated: index => prefs.query("companion-" + field.modelData.key + "-" + field.modelData.keys[index])
                    }
                }
            }
            C.CheckBox {
                objectName: "companion-reactions"
                text: i18n( "React to desktop activity")
                enabled: !prefs.loading
                checked: (prefs.state.companionSettings || {}).reactions === "on"
                onClicked: prefs.query("companion-reactions-" + (checked ? "on" : "off"))
            }
            C.CheckBox {
                objectName: "companion-rest"
                text: i18n( "Hide between visits and reactions")
                enabled: !prefs.loading
                checked: (prefs.state.companionSettings || {}).rest === "hide"
                onClicked: prefs.query("companion-rest-" + (checked ? "hide" : "show"))
            }
        }
    }
}
