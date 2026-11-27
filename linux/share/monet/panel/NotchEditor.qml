pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as C
import QtQuick.Templates as T
import org.kde.kirigami as K

ColumnLayout {
    id: editor
    objectName: "notchVisualEditor"
    property var notchState: ({})
    property bool busy: false
    property int page: 0
    property bool showNavigation: true
    property bool showIntroduction: true
    property string selected: "music"
    property string shortcutSide: "left"
    readonly property var choices: notchState.layout || ({})
    property int draftWidth: 464
    property int draftHeight: 420
    property bool resizing: false
    function syncSize() {
        if (resizing) return
        draftWidth = choices.expandedWidth || 464
        draftHeight = choices.toolHeight || 420
    }
    onChoicesChanged: syncSize()
    onBusyChanged: if (!busy) syncSize()
    function previewSize(width, height) {
        draftWidth = Math.max(340, Math.min(640, Math.round(width/2)*2))
        draftHeight = Math.max(316, Math.min(640, Math.round(height/2)*2))
    }
    function saveSize() {
        resizing = false
        if (draftWidth !== (choices.expandedWidth || 464) || draftHeight !== (choices.toolHeight || 420))
            requested("size-"+draftWidth+"-"+draftHeight)
    }
    readonly property var options: notchState.options || ({})
    readonly property var tabs: notchState.tabs || []
    readonly property bool enabledNotch: !!notchState.mode && notchState.mode !== "off"
    readonly property color accent: "#438f7d"
    readonly property bool dark: K.Theme.backgroundColor.hslLightness < 0.5
    readonly property color ink: dark ? "#eef1f0" : "#25292c"
    readonly property color surface: dark ? "#292b30" : "#ffffff"
    readonly property color field: dark ? "#222428" : "#f4f5f2"
    readonly property color outline: dark ? "#3b4044" : "#dce1db"
    readonly property var sections: [
        {key:"music",name:qsTr("Music"),icon:"media-playback-start"}, {key:"activity",name:qsTr("Activity"),icon:"view-history"},
        {key:"time",name:qsTr("Time"),icon:"chronometer"}, {key:"calendar",name:qsTr("Calendar"),icon:"view-calendar"},
        {key:"notes",name:qsTr("Notes"),icon:"document-edit"}, {key:"camera",name:qsTr("Camera"),icon:"camera-web"},
        {key:"clipboard",name:qsTr("Clipboard"),icon:"edit-paste"}, {key:"tools",name:qsTr("Tools"),icon:"applications-utilities"},
        {key:"agents",name:qsTr("AI agents"),icon:"dialog-scripts"}, {key:"notifications",name:qsTr("Notifications"),icon:"notifications"}]
    readonly property var allShortcuts: [{key:"none",name:qsTr("None"),icon:"list-add"},
        {key:"controls",name:qsTr("Controls"),icon:"configure"}, {key:"mixer",name:qsTr("Volume mixer"),icon:"audio-volume-high"},
        {key:"files",name:qsTr("File shelf"),icon:"folder-open"}].concat(sections)
    readonly property var ordered: tabs.concat(sections.map(s => s.key).filter(key => !tabs.includes(key)))
    ListModel { id: sectionRows }
    function syncRows() {
        if (!sectionRows.count) ordered.forEach(key => sectionRows.append({key:key}))
        else ordered.forEach((key,index) => {
            for (let at=index; at<sectionRows.count; at++) {
                if (sectionRows.get(at).key === key) { if (at !== index) sectionRows.move(at,index,1); break }
            }
        })
    }
    Component.onCompleted: { syncRows(); syncSize() }
    onOrderedChanged: syncRows()
    signal requested(string command)
    spacing: 14
    function info(key) { return allShortcuts.find(s => s.key === key) || allShortcuts[0] }
    function rail(side) { const value = choices[side+"Rail"] ?? (side === "left" ? "time" : "controls,mixer,files"); return value === "none" ? [] : String(value).split(",") }
    function setShortcut(index, key) {
        let rows = rail(shortcutSide).slice(); rows[index] = key
        rows = rows.filter((value, at) => value && value !== "none" && rows.indexOf(value) === at)
        requested("rail-"+shortcutSide+"-"+(rows.join(",") || "none"))
    }
    function moveTab(key, target) {
        const rows = tabs.slice(), from = rows.indexOf(key), to = rows.indexOf(target)
        if (from < 0 || to < 0 || from === to || busy) return
        rows.splice(to, 0, rows.splice(from, 1)[0]); requested("tabs-"+rows.join(","))
    }
    component TextLabel: C.Label { color: editor.ink }
    component Title: TextLabel { Layout.fillWidth: true; wrapMode: Text.Wrap; font.weight: Font.DemiBold; font.pixelSize: 16 }
    component Help: TextLabel { Layout.fillWidth: true; wrapMode: Text.Wrap; opacity: 0.65; font.pixelSize: 13 }
    component Card: C.Pane {
        Layout.fillWidth: true; Layout.minimumWidth: 0; padding: 20
        background: Rectangle { radius: 18; color: editor.surface }
    }
    // Fully styled here. The desktop style's editable cursor assumes a TextField
    // and cannot be inherited when the visible content is our own label.
    component MenuChoice: T.ComboBox {
        id: choice
        displayText: currentText.length ? currentText[0].toUpperCase()+currentText.slice(1) : ""
        wheelEnabled: false; hoverEnabled: true
        implicitWidth: Math.max(120, implicitContentWidth + leftPadding + rightPadding)
        implicitHeight: 40; leftPadding: 12; rightPadding: 30
        contentItem: TextLabel { text: choice.displayText; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight; color: editor.ink }
        indicator: TextLabel { text: "⌄"; x: choice.width-width-12; anchors.verticalCenter: parent.verticalCenter; color: editor.ink }
        background: Rectangle { radius: 10; color: editor.field; border.color: choice.visualFocus ? editor.accent : editor.outline }
        popup: C.Popup {
            y: choice.height+4; width: choice.width; padding: 5
            height: Math.min(280,contentItem.implicitHeight+10)
            background: Rectangle { radius: 12; color: editor.surface; border.color: editor.outline }
            contentItem: ListView {
                clip: true; implicitHeight: contentHeight; model: choice.popup.visible ? choice.delegateModel : null
                currentIndex: choice.highlightedIndex; C.ScrollBar.vertical: C.ScrollBar {}
            }
        }
        delegate: C.ItemDelegate {
            required property int index; required property var modelData
            width: choice.width-10; text: choice.textRole ? modelData[choice.textRole] : modelData
            highlighted: choice.highlightedIndex===index
            contentItem: TextLabel { text: parent.text; color: editor.ink; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter }
            background: Rectangle { radius: 7; color: parent.highlighted ? Qt.rgba(editor.accent.r,editor.accent.g,editor.accent.b,.2) : "transparent" }
        }
    }
    component Level: C.Slider {
        id: level; implicitHeight: 32; wheelEnabled: false
        background: Rectangle {
            x: level.leftPadding; y: level.topPadding+(level.availableHeight-height)/2
            width: level.availableWidth; height: 5; radius: 3; color: editor.outline
            Rectangle { width: level.visualPosition*parent.width; height: parent.height; radius: 3; color: editor.accent }
        }
        handle: Rectangle {
            x: level.leftPadding+level.visualPosition*(level.availableWidth-width)
            y: level.topPadding+(level.availableHeight-height)/2; width: 20; height: 20; radius: 10
            color: "#f4f6f5"; border.color: level.visualFocus ? editor.accent : "#bcc5c1"
        }
    }
    component ActionButton: C.Button {
        id: action
        padding: 10; leftPadding: 12; rightPadding: 12; implicitHeight: Math.max(38,implicitContentHeight+20)
        contentItem: RowLayout {
            spacing: 8
            IslandGlyph { source: action.icon.name; visible: !!action.icon.name; Layout.preferredWidth: 18; Layout.preferredHeight: 18; color: editor.ink }
            TextLabel { text: action.text; Layout.fillWidth: true; elide: Text.ElideRight; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        }
        background: Rectangle { radius: 10; color: action.checked ? Qt.rgba(editor.accent.r,editor.accent.g,editor.accent.b,.18) : action.flat && !action.hovered ? "transparent" : editor.field; border.width: action.flat && !action.visualFocus ? 0 : 1; border.color: action.checked || action.visualFocus ? editor.accent : editor.outline }
    }
    component PageCheck: C.CheckBox {
        id: check; spacing: 10; implicitWidth: text ? implicitContentWidth+36 : 28; implicitHeight: 32
        indicator: Rectangle {
            x: 4; y: (check.height-height)/2; width: 20; height: 20; radius: 6
            color: check.checked ? editor.accent : editor.field
            border.color: check.visualFocus ? editor.accent : editor.outline
            TextLabel { anchors.centerIn: parent; text: check.checked ? "✓" : ""; color: "white"; font.pixelSize: 14 }
        }
        contentItem: TextLabel { text: check.text; leftPadding: check.text ? 34 : 0; verticalAlignment: Text.AlignVCenter; wrapMode: Text.Wrap }
    }
    component IconAction: C.ToolButton {
        id: action; implicitWidth: 30; implicitHeight: 30
        contentItem: TextLabel { text: action.icon.name === "arrow-up" ? "↑" : "↓"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; opacity: action.enabled ? 1 : .3 }
        background: Rectangle { radius: 8; color: action.hovered ? editor.field : "transparent"; border.color: action.visualFocus ? editor.accent : "transparent" }
    }
    component Tile: C.Button {
        id: tile
        property string symbol: ""
        Layout.fillWidth: true; Layout.minimumWidth: 0
        Layout.preferredWidth: 1
        padding: 14; implicitHeight: Math.max(88, implicitContentHeight+28); checkable: false
        contentItem: ColumnLayout {
            spacing: 7
            IslandGlyph { visible: !!tile.symbol; source: tile.symbol; Layout.alignment: Qt.AlignHCenter; Layout.preferredWidth: 23; Layout.preferredHeight: 23; color: tile.checked ? editor.accent : editor.ink }
            TextLabel { text: tile.text; color: editor.ink; font.weight: tile.checked ? Font.DemiBold : Font.Normal; Layout.fillWidth: true; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter }
        }
        background: Rectangle { radius: 13; color: tile.checked ? Qt.rgba(editor.accent.r,editor.accent.g,editor.accent.b,0.14) : Qt.rgba(0.5,0.5,0.5,tile.hovered ? 0.17 : 0.08); border.width: tile.checked || tile.visualFocus ? 1 : 0; border.color: editor.accent }
    }
    component Toggle: C.AbstractButton {
        id: toggle
        property string option: ""
        property string detail: ""
        Layout.fillWidth: true; Layout.minimumWidth: 0
        implicitHeight: Math.max(58, contentItem.implicitHeight + 20)
        objectName: "notchOption-" + option
        padding: 10; checked: !!editor.options[option]; enabled: !editor.busy
        onClicked: editor.requested(option+(editor.options[option] ? "-off" : "-on"))
        contentItem: RowLayout {
            ColumnLayout {
                Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 4
                TextLabel { text: toggle.text; Layout.fillWidth: true; wrapMode: Text.Wrap }
                Help { visible: !!toggle.detail; text: toggle.detail }
            }
            Rectangle {
                Layout.preferredWidth: 38; Layout.preferredHeight: 22; radius: 11
                color: toggle.checked ? editor.accent : Qt.rgba(0.5,0.5,0.5,0.4)
                Rectangle { width: 16; height: 16; radius: 8; y: 3; x: toggle.checked ? 19 : 3; color: "white" }
            }
        }
        background: Rectangle { radius: 10; color: toggle.hovered ? Qt.rgba(0.5,0.5,0.5,0.08) : "transparent"; border.width: toggle.visualFocus ? 1 : 0; border.color: editor.accent }
    }
    component PreviewCard: Card {
        id: previewCard
        property bool resizable: false
        contentItem: ColumnLayout {
            spacing: 10
            RowLayout {
                Layout.fillWidth: true
                Title { text: previewCard.resizable ? qsTr("Shape your notch") : qsTr("Preview") }
                TextLabel { visible: previewCard.resizable; text: editor.draftWidth+" × "+editor.draftHeight+" px"; opacity: 0.65; font.pixelSize: 12 }
            }
            Item {
                id: previewCanvas
                readonly property real previewScale: Math.max(0.1, Math.min(0.48,(width-100)/640))
                Layout.fillWidth: true
                Layout.preferredHeight: previewCard.resizable ? Math.max(206,640*previewScale+38) : 210
                Rectangle { anchors.horizontalCenter: parent.horizontalCenter; width: 1; height: parent.height-12; color: editor.accent; opacity: 0.18; visible: previewCard.resizable }
                Rectangle {
                    id: preview
                    objectName: previewCard.resizable ? "notchSizePreview" : "notchContentPreview"
                    anchors.top: parent.top; anchors.horizontalCenter: parent.horizontalCenter
                    anchors.topMargin: 8
                    width: editor.draftWidth * previewCanvas.previewScale
                    height: previewCard.resizable ? editor.draftHeight * previewCanvas.previewScale : 184
                    radius: 18; color: "#08080a"
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 12; spacing: 8
                        RowLayout {
                            IslandGlyph { source: previewCard.resizable ? "applications-utilities" : editor.info(editor.selected).icon; color: "#e5e5ec"; Layout.preferredWidth: 17; Layout.preferredHeight: 17 }
                            TextLabel { text: previewCard.resizable ? qsTr("Tool page") : editor.info(editor.selected).name; color: "#f5f5fa"; font.bold: true; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
                            Rectangle { visible: !!editor.options.companion; width: 16; height: 21; radius: 8; color: "#c9b0e1" }
                        }
                        Rectangle {
                            Layout.fillWidth: true; Layout.fillHeight: true; radius: 12; color: "#19191d"
                            ColumnLayout {
                                visible: !previewCard.resizable
                                anchors.centerIn: parent; width: parent.width-16; spacing: 8
                                IslandGlyph { source: previewCard.resizable ? "document-edit" : editor.info(editor.selected).icon; color: "#c5c5d1"; Layout.alignment: Qt.AlignHCenter; Layout.preferredWidth: 24; Layout.preferredHeight: 24 }
                                TextLabel { text: previewCard.resizable ? qsTr("Room for your tools") : editor.selected === "music" ? qsTr("Nothing playing") : editor.selected === "time" ? "25:00" : editor.info(editor.selected).name; color: "#b7b7c2"; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; font.pixelSize: 11 }
                            }
                            Column {
                                visible: previewCard.resizable
                                anchors.fill: parent; anchors.margins: 10; spacing: 7
                                Rectangle { width: parent.width*0.65; height: 5; radius: 2; color: "#81818d" }
                                Rectangle { width: parent.width; height: Math.max(8,(parent.height-26)*0.6); radius: 6; color: "#292930" }
                                Rectangle { width: parent.width; height: Math.max(6,(parent.height-26)*0.4); radius: 6; color: "#292930" }
                            }
                        }
                    }
                }
                Repeater {
                    model: previewCard.resizable ? [-1,1] : []
                    ResizeGrip {
                        required property int modelData
                        objectName: modelData < 0 ? "notchResizeLeft" : "notchResizeRight"
                        referenceItem: previewCanvas; mirrored: modelData < 0
                        enabled: !editor.busy
                        description: qsTr("Resize notch from %1 corner").arg(modelData < 0 ? qsTr("left") : qsTr("right"))
                        x: preview.x + (modelData < 0 ? 0 : preview.width) - width/2
                        y: preview.y + preview.height - height/2
                        property int startWidth
                        property int startHeight
                        property real startScale
                        onStarted: { startWidth = editor.draftWidth; startHeight = editor.draftHeight; startScale = previewCanvas.previewScale; editor.resizing = true }
                        onDragged: (dx,dy) => editor.previewSize(startWidth+modelData*2*dx/startScale,startHeight+dy/startScale)
                        onFinished: editor.saveSize()
                        onCanceled: { editor.resizing = false; editor.syncSize() }
                        onNudged: (dx,dy) => { editor.previewSize(editor.draftWidth+dx,editor.draftHeight+dy); editor.saveSize() }
                    }
                }
                Repeater {
                    model: ["left","right"]
                    Column {
                        id: railPreview
                        required property string modelData
                        x: modelData === "left" ? preview.x-40 : preview.x+preview.width+8
                        y: 8; spacing: 6
                        Repeater {
                            model: editor.rail(railPreview.modelData).concat("none")
                            ActionButton {
                                id: shortcutButton
                                required property string modelData
                                padding: 6; leftPadding: 6; rightPadding: 6
                                contentItem: IslandGlyph { source: editor.info(shortcutButton.modelData).icon; color: "#ececf4" }
                                background: Rectangle { radius: 16; color: "#151518"; border.width: parent.visualFocus ? 1 : 0; border.color: editor.accent }
                                icon.color: "#ececf4"
                                width: 32; height: 32; icon.name: editor.info(modelData).icon; display: C.AbstractButton.IconOnly
                                Accessible.name: qsTr("Edit %1 shortcuts").arg(railPreview.modelData)
                                onClicked: { editor.shortcutSide = railPreview.modelData; editor.page = 0 }
                            }
                        }
                    }
                }
            }
            Help { text: previewCard.resizable ? qsTr("Drag either lower corner to resize. Tool pages use this height; music and quick controls stay compact.") : qsTr("Choose a page to preview its place in the notch.") }
        }
    }
    component PagesCard: Card {
        contentItem: ColumnLayout {
            spacing: 6
            Title { text: qsTr("Pages") }
            Help { text: qsTr("Drag the grip to reorder. Use the checkbox to show or hide a page.") }
            Repeater {
                model: sectionRows
                Rectangle {
                    id: section; required property string key; required property int index
                    readonly property string modelData: key
                    Layout.fillWidth: true; implicitHeight: 48; radius: 10
                    color: editor.selected === modelData ? Qt.rgba(editor.accent.r,editor.accent.g,editor.accent.b,0.13) : "transparent"
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 4; spacing: 5
                        Item {
                            objectName: "notchGrip-"+section.modelData
                            Layout.preferredWidth: 22; Layout.fillHeight: true
                            TextLabel { anchors.centerIn: parent; text: "⠿"; opacity: 0.5 }
                            DragHandler { id: drag; target: null; enabled: editor.tabs.includes(section.modelData) && !editor.busy; onActiveChanged: if (!active) dragToken.Drag.drop() }
                            Item { id: dragToken; x: drag.centroid.position.x; y: drag.centroid.position.y; width: 1; height: 1; property string key: section.modelData; Drag.active: drag.active; Drag.source: dragToken; Drag.hotSpot.x: 0; Drag.hotSpot.y: 0 }
                        }
                        PageCheck { objectName: "notchTab-"+section.modelData; checked: editor.tabs.includes(section.modelData); Accessible.name: qsTr("Show %1").arg(editor.info(section.modelData).name); enabled: !editor.busy; onClicked: editor.requested("tab-"+section.modelData+(checked ? "-show" : "-hide")) }
                        ActionButton { text: editor.info(section.modelData).name; icon.name: editor.info(section.modelData).icon; flat: true; Layout.fillWidth: true; Layout.minimumWidth: 0; onClicked: editor.selected = section.modelData }
                        IconAction { objectName: "notchEarlier-"+section.modelData; icon.name: "arrow-up"; Accessible.name: qsTr("Move %1 earlier").arg(editor.info(section.modelData).name); enabled: !editor.busy && editor.tabs.includes(section.modelData) && section.index > 0; onClicked: editor.requested("tab-"+section.modelData+"-earlier") }
                        IconAction { objectName: "notchLater-"+section.modelData; icon.name: "arrow-down"; Accessible.name: qsTr("Move %1 later").arg(editor.info(section.modelData).name); enabled: !editor.busy && editor.tabs.includes(section.modelData) && section.index < editor.tabs.length-1; onClicked: editor.requested("tab-"+section.modelData+"-later") }
                    }
                    DropArea { anchors.fill: parent; onDropped: drop => { if (drop.source?.key) editor.moveTab(drop.source.key,section.modelData) } }
                }
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        ColumnLayout {
            Layout.fillWidth: true
            Title { text: editor.showIntroduction ? qsTr("Make the notch yours") : qsTr("Enable notch"); font.pixelSize: editor.showIntroduction ? 22 : 16 }
            Help { visible: editor.showIntroduction; text: qsTr("Arrange your pages, choose shortcuts, and decide what appears.") }
        }
        C.Switch {
            id: enableSwitch
            indicator: Rectangle {
                implicitWidth: 38; implicitHeight: 22; radius: 11
                x: enableSwitch.leftPadding; y: (enableSwitch.height-height)/2
                color: enableSwitch.checked ? editor.accent : editor.outline
                border.color: enableSwitch.visualFocus ? editor.accent : "transparent"
                Rectangle { x: enableSwitch.checked ? 19 : 3; y: 3; width: 16; height: 16; radius: 8; color: "white" }
            }
            objectName: "notchEnabled"; Accessible.name: qsTr("Enable notch"); checked: editor.enabledNotch; enabled: !editor.busy && !!editor.notchState.mode; onClicked: editor.requested(checked ? "add" : "off") }
    }
    RowLayout {
        visible: editor.showNavigation
        Layout.fillWidth: true; spacing: 4; enabled: editor.enabledNotch
        Repeater {
            model: [qsTr("Layout"),qsTr("Content"),qsTr("Activity"),qsTr("Behavior")]
            ActionButton {
                id: sectionTab
                required property int index; required property string modelData
                padding: 8; implicitHeight: Math.max(38, implicitContentHeight+16)
                contentItem: TextLabel { text: sectionTab.text; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; color: editor.ink; font.weight: sectionTab.checked ? Font.DemiBold : Font.Normal; elide: Text.ElideRight }
                background: Rectangle { radius: 9; color: parent.checked ? Qt.rgba(editor.accent.r,editor.accent.g,editor.accent.b,0.16) : Qt.rgba(0.5,0.5,0.5,0.09); border.width: parent.visualFocus ? 1 : 0; border.color: editor.accent }
                objectName: ["notchLayoutTab","editNotchTabs","notchActivityTab","notchBehaviorTab"][index]
                Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 1; text: modelData; checked: editor.page === index
                onClicked: editor.page = index
            }
        }
    }
    Card {
        visible: !editor.enabledNotch
        contentItem: ColumnLayout {
            Title { text: qsTr("Your tools, one click away") }
            Help { text: qsTr("Turn on the notch to customize it. Your saved choices will return.") }
            ActionButton { objectName: "notchEnable"; text: qsTr("Add notch"); enabled: !editor.busy; onClicked: editor.requested("add") }
        }
    }
    PreviewCard { visible: editor.enabledNotch && editor.page === 0; resizable: true }
    Card {
        visible: editor.enabledNotch && editor.page === 0
        contentItem: ColumnLayout {
            spacing: 12
            Title { text: qsTr("Size") }
            RowLayout {
                Repeater {
                    model: [{title:qsTr("Compact"),w:414,h:380},{title:qsTr("Comfortable"),w:464,h:420},{title:qsTr("Spacious"),w:560,h:520}]
                    Tile {
                        required property var modelData
                        text: modelData.title; symbol: "view-preview"
                        checked: editor.draftWidth === modelData.w && editor.draftHeight === modelData.h
                        enabled: !editor.busy
                        onClicked: { editor.previewSize(modelData.w,modelData.h); editor.saveSize() }
                    }
                }
            }
            Repeater {
                model: [{key:"expandedWidth",title:qsTr("Open width"),low:340,fallback:464},{key:"toolHeight",title:qsTr("Tool page height"),low:316,fallback:420}]
                ColumnLayout {
                    id: sizeRow; required property var modelData; Layout.fillWidth: true
                    RowLayout { TextLabel { text: sizeRow.modelData.title; Layout.fillWidth: true } TextLabel { text: Math.round(sizeSlider.value)+" px"; opacity: 0.65 } }
                    Level {
                        id: sizeSlider; objectName: "notchSize-"+sizeRow.modelData.key
                        Layout.fillWidth: true; from: sizeRow.modelData.low; to: 640; stepSize: 2
                        value: sizeRow.modelData.key === "expandedWidth" ? editor.draftWidth : editor.draftHeight
                        enabled: !editor.busy; wheelEnabled: false; Accessible.name: sizeRow.modelData.title
                        onMoved: editor.previewSize(sizeRow.modelData.key === "expandedWidth" ? value : editor.draftWidth,sizeRow.modelData.key === "toolHeight" ? value : editor.draftHeight)
                        onPressedChanged: { if (pressed) editor.resizing = true; else editor.saveSize() }
                        Keys.onReleased: event => { if ([Qt.Key_Left,Qt.Key_Right,Qt.Key_Home,Qt.Key_End,Qt.Key_PageUp,Qt.Key_PageDown].includes(event.key)) editor.saveSize() }
                    }
                }
            }
            ActionButton { objectName: "notchResetSize"; text: qsTr("Reset size"); enabled: !editor.busy; onClicked: { editor.previewSize(464,420); editor.saveSize() } }
            PageCheck { text: qsTr("Wider closed notch"); checked: editor.notchState.mode === "wide"; enabled: !editor.busy; onClicked: editor.requested(checked ? "wide" : "compact") }
        }
    }
    Card {
        visible: editor.enabledNotch && editor.page === 0
        contentItem: ColumnLayout {
            spacing: 10
            Title { text: qsTr("Side shortcuts") }
            RowLayout {
                ActionButton { text: qsTr("Left"); Layout.fillWidth: true; checked: editor.shortcutSide === "left"; onClicked: editor.shortcutSide = "left" }
                ActionButton { text: qsTr("Right"); Layout.fillWidth: true; checked: editor.shortcutSide === "right"; onClicked: editor.shortcutSide = "right" }
            }
            Repeater {
                model: Math.min(4,editor.rail(editor.shortcutSide).length+1)
                RowLayout {
                    id: shortcut; required property int index; Layout.fillWidth: true
                    TextLabel { text: String(shortcut.index+1); opacity: 0.6 }
                    MenuChoice {
                        objectName: "notchShortcut-" + shortcut.index
                        Layout.fillWidth: true; Layout.minimumWidth: 0; model: editor.allShortcuts; textRole: "name"; valueRole: "key"
                        Accessible.name: qsTr("Shortcut %1").arg(shortcut.index+1); enabled: !editor.busy
                        currentIndex: editor.allShortcuts.findIndex(row => row.key === (editor.rail(editor.shortcutSide)[shortcut.index] || "none"))
                        onActivated: index => editor.setShortcut(shortcut.index, editor.allShortcuts[index].key)
                    }
                }
            }
            Help { text: qsTr("Up to four on each side. A hidden page also hides its shortcut. Back always stays available.") }
        }
    }
    GridLayout {
        visible: editor.enabledNotch && editor.page === 1
        Layout.fillWidth: true; columns: editor.width >= 620 ? 2 : 1; columnSpacing: 14
        PagesCard { Layout.preferredWidth: 1; Layout.alignment: Qt.AlignTop }
        PreviewCard { Layout.preferredWidth: 1; Layout.alignment: Qt.AlignTop }
    }
    Card {
        visible: editor.enabledNotch && editor.page === 2
        contentItem: ColumnLayout {
            spacing: 14
            Title { text: qsTr("Live activity") }
            Help { text: qsTr("Choose what stays visible when your notch is closed.") }
            GridLayout {
                Layout.fillWidth: true; columns: editor.width >= 480 ? 3 : 2; columnSpacing: 10; rowSpacing: 10
                Repeater {
                    model: [{key:"levels",title:qsTr("Music levels"),icon:"audio-volume-high"},
                        {key:"combined",title:qsTr("Music + timer"),icon:"media-playback-start"},
                        {key:"countdown",title:qsTr("Running timers"),icon:"chronometer"},
                        {key:"awake",title:qsTr("Keep awake"),icon:"weather-clear"},
                        {key:"previews",title:qsTr("Notifications"),icon:"notifications"},
                        {key:"alerts",title:qsTr("Battery alerts"),icon:"battery"}]
                    Tile {
                        required property var modelData
                        objectName: "notchOption-"+modelData.key
                        text: modelData.title; symbol: modelData.icon
                        checked: !!editor.options[modelData.key]; enabled: !editor.busy
                        Accessible.checkable: true; Accessible.checked: checked
                        onClicked: editor.requested(modelData.key+(checked ? "-off" : "-on"))
                        TextLabel { anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 8; text: parent.checked ? "✓" : "+"; color: editor.accent; font.pixelSize: 14 }
                    }
                }
            }
            Help { text: qsTr("Notification previews include message text. Battery alerts appear when an accessory is running low.") }
        }
    }
    Card {
        visible: editor.enabledNotch && editor.page === 2
        contentItem: ColumnLayout {
            Title { text: qsTr("Companion") }
            Toggle { option: "companion"; text: qsTr("Show a companion") }
            GridLayout {
                visible: !!editor.options.companion; Layout.fillWidth: true; columns: editor.width > 500 ? 2 : 1
                Repeater {
                    model: [{key:"style",title:qsTr("Style"),values:["soft","robot"]}, {key:"shape",title:qsTr("Shape"),values:["round","egg","square","pill"]},
                        {key:"color",title:qsTr("Color"),values:["mint","pearl","lemon","peach","rose","lilac","sky"]}, {key:"side",title:qsTr("Side"),values:["left","right"]},
                        {key:"visits",title:qsTr("Visits"),values:["off","rare","normal","frequent"]}, {key:"reactions",title:qsTr("Reactions"),values:["on","off"]}, {key:"rest",title:qsTr("Between visits"),values:["show","hide"]}]
                    ColumnLayout {
                        id: companionField; required property var modelData; Layout.fillWidth: true
                        TextLabel { text: companionField.modelData.title }
                        MenuChoice {
            wheelEnabled: false; Layout.fillWidth: true; Layout.minimumWidth: 0; objectName: "companion-"+companionField.modelData.key; Accessible.name: companionField.modelData.title; model: companionField.modelData.values; enabled: !editor.busy; currentIndex: model.indexOf((editor.notchState.companionSettings || {})[companionField.modelData.key]); onActivated: index => editor.requested("companion-"+companionField.modelData.key+"-"+model[index]) }
                    }
                }
            }
        }
    }
    Card {
        visible: editor.enabledNotch && editor.page === 3
        contentItem: ColumnLayout {
            spacing: 14
            Title { text: qsTr("Opening") }
            RowLayout {
                Tile { text: qsTr("Click to open"); symbol: "input-mouse"; checked: !editor.options.hoverControls; enabled: !editor.busy; onClicked: editor.requested("hoverControls-off") }
                Tile { text: qsTr("Preview on hover"); symbol: "view-preview"; checked: !!editor.options.hoverControls; enabled: !editor.busy; onClicked: editor.requested("hoverControls-on") }
            }
            Help { text: qsTr("Hover opens a preview without taking keyboard focus. Move away to close it, or click inside to keep it open.") }
            Toggle {
                option: "autoHide"
                text: qsTr("Hidden until hover")
                detail: qsTr("Hide the closed notch when idle. Move to its spot at the top of the screen to reveal it. It stays visible while editing.")
            }
        }
    }
    Card {
        visible: editor.enabledNotch && editor.page === 3
        contentItem: ColumnLayout {
            spacing: 12
            Title { text: qsTr("Navigation") }
            Toggle { option: "gestures"; text: qsTr("Notch gestures"); detail: qsTr("Scroll to open or close. Swipe over music to change tracks.") }
            Toggle { option: "openActivity"; text: qsTr("Open the visible activity"); detail: qsTr("Go straight to the music, timer, or activity shown in the closed notch.") }
            Title { text: qsTr("Otherwise, reopen to") }
            RowLayout {
                Tile { objectName: "notchReopenSections"; text: qsTr("All sections"); symbol: "view-grid"; checked: editor.choices.reopen !== "last"; enabled: !editor.busy; onClicked: editor.requested("reopen-sections") }
                Tile { objectName: "notchReopenLast"; text: qsTr("Last page"); symbol: "view-history"; checked: editor.choices.reopen === "last"; enabled: !editor.busy; onClicked: editor.requested("reopen-last") }
            }
        }
    }
}
