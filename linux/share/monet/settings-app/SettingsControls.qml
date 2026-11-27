// Common Settings controls. Page implementations are loaded separately.
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


QtObject {
    // Pieces ----------------------------------------------------------------
    // Inline components can't see this file's ids, so everything they need
    // comes in through properties.

    component Glyph: Shared.Glyph {}

    component ChoiceGrid: GridLayout {
        property int optionCount: 3
        readonly property real minimumCardWidth: Math.max(132, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) * 8.5)
        Layout.fillWidth: true
        columns: Math.max(1, Math.min(3, optionCount, Math.floor((width + columnSpacing) / (minimumCardWidth + columnSpacing))))
        columnSpacing: 12
        rowSpacing: 12
    }

    component Rounded: Item {
        id: rounded
        property real radius: 12
        default property alias content: inside.data
        Item {
            id: inside
            anchors.fill: parent
            layer.enabled: true
            layer.effect: MultiEffect {
                maskEnabled: true
                maskSource: shape
                maskThresholdMin: 0.5
                maskSpreadAtMin: 1.0
            }
        }
        Rectangle {
            id: shape
            anchors.fill: parent
            radius: rounded.radius
            visible: false
            layer.enabled: true
        }
    }

    // A page's title next to its swatch, as large as the one in the list.
    component PageTitle: RowLayout {
        id: heading
        property var tone
        property string text
        property string detail
        property var entry: ({})
        property string art
        Layout.fillWidth: true
        spacing: 16
        Item {
            visible: heading.entry.glyph !== undefined
            Layout.preferredWidth: 46
            Layout.preferredHeight: 46
            Layout.alignment: Qt.AlignTop
            Image {
                anchors.fill: parent
                source: heading.art + "swatch-" + (heading.entry.swatch || heading.entry.id) + ".png"
                sourceSize: Qt.size(92, 92)
                smooth: true
            }
            Glyph {
                anchors.centerIn: parent
                anchors.verticalCenterOffset: 1
                width: 24
                height: 24
                path: heading.entry.glyph || ""
                filled: heading.entry.filled === true
                color: Qt.rgba(0, 0, 0, 0.3)
            }
            Glyph {
                anchors.centerIn: parent
                width: 24
                height: 24
                path: heading.entry.glyph || ""
                filled: heading.entry.filled === true
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                text: heading.text
                color: heading.tone.ink
                font.family: "Fraunces 72pt SuperSoft"
                font.weight: Font.Light
                font.pixelSize: 30
                elide: Text.ElideRight
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                visible: heading.detail !== ""
                text: heading.detail
                color: heading.tone.dim
                font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
                wrapMode: Text.Wrap
            }
        }
    }

    component Caption: Text {
        property var tone
        Layout.fillWidth: true
        Layout.bottomMargin: -10
        color: tone.dim
        font.pixelSize: Math.max(14, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 2)
        font.weight: Font.DemiBold
        font.letterSpacing: 0.7
        font.capitalization: Font.AllUppercase
    }

    component ScreenSizes: ColumnLayout {
        id: sizes
        property var tone
        property var displays: []
        property bool busy: false
        property string problem: ""
        signal picked(string name, int percent)
        Layout.fillWidth: true
        spacing: 10
        objectName: "search-size"
        Caption {
            tone: sizes.tone
            text: i18n("Size of text, apps and windows")
        }
        Text {
            objectName: "displaySizeHelp"
            Layout.fillWidth: true
            color: sizes.tone.ink
            opacity: 0.7
            font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
            wrapMode: Text.Wrap
            textFormat: Text.PlainText
            text: i18n("Choose a comfortable size for this screen. 125% is a starting point for standard displays; high-density screens usually need 175–200%. Each screen keeps its own size.")
        }
        Repeater {
            model: sizes.displays
            Card {
                id: sizeCard
                required property var modelData
                tone: sizes.tone
                SettingRow {
                    tone: sizes.tone
                    divider: false
                    title: sizeCard.modelData.name
                    objectName: "screenSizeRow-" + sizeCard.modelData.name
                    detail: i18n("%1 × %2 · Current size: %3%", sizeCard.modelData.width, sizeCard.modelData.height, sizeCard.modelData.scale)
                        + (sizeCard.modelData.highDensity ? "\n" + i18n("High-density display") : "")
                    Segments {
                        tone: sizes.tone
                        objectName: "displaySize-" + sizeCard.modelData.name
                        enabled: !sizes.busy
                        options: [100, 125, 150, 175, 200].map(s => [s, s + "%"])
                        current: sizeCard.modelData.scale
                        onPicked: value => sizes.picked(sizeCard.modelData.name, value)
                    }
                }
            }
        }
        Text {
            Layout.fillWidth: true
            color: sizes.tone.ink
            font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
            wrapMode: Text.Wrap
            textFormat: Text.PlainText
            visible: sizes.busy || sizes.problem !== "" || sizes.displays.length === 0
            text: sizes.busy ? i18n("Changing screen size…") : sizes.problem || i18n("No display information available. Open the display settings to try again.")
        }
    }

    component MaintenanceText: Text {
        required property var tone
        Layout.fillWidth: true
        wrapMode: Text.Wrap
        textFormat: Text.PlainText
        color: tone.ink
        font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
    }

    component Card: Rectangle {
        id: card
        property var tone
        default property alias rows: list.data
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        Layout.maximumWidth: parent && parent.width > 0 ? parent.width : Infinity
        implicitHeight: list.implicitHeight
        radius: 16
        color: tone.wash
        border.width: activeFocus ? 2 : 1
        border.color: activeFocus ? tone.lily : tone.line
        Keys.onTabPressed: event => {
            event.accepted = card.activeFocus && FocusNavigation.enter(card)
        }
        ColumnLayout {
            id: list
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            spacing: 0
        }
    }

    component SettingRow: Item {
        id: row
        property var tone
        property string title
        property string detail
        property bool divider: true
        property bool tappable: false
        property bool checkable: false
        property bool checked: false
        property bool strong: true
        default property alias trailing: slot.data
        property alias lead: leadSlot.data
        signal tapped()
        readonly property bool stacked: slot.childrenRect.width > 0
            && width - slot.childrenRect.width - leadSlot.width - 52 < 180
        Layout.fillWidth: true
        implicitHeight: stacked ? Math.max(texts.implicitHeight, leadSlot.childrenRect.height) + slot.childrenRect.height + 40
            : Math.max(texts.implicitHeight, slot.childrenRect.height, leadSlot.childrenRect.height) + 28
        activeFocusOnTab: tappable
        Keys.onSpacePressed: event => { if (tappable && !event.isAutoRepeat) row.tapped() }
        Keys.onReturnPressed: event => { if (tappable && !event.isAutoRepeat) row.tapped() }
        Keys.onEnterPressed: event => { if (tappable && !event.isAutoRepeat) row.tapped() }
        Keys.onTabPressed: event => {
            event.accepted = row.activeFocus && FocusNavigation.enter(row)
        }

        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            radius: 14
            color: row.tone.wash
            opacity: hover.hovered && row.tappable ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Math.round(140 * row.tone.speed) } }
        }
        Rectangle {
            visible: row.divider
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: 18
            anchors.rightMargin: 18
            height: 1
            color: row.tone.line
        }
        Rectangle {
            anchors.fill: parent
            anchors.margins: 2
            radius: 14
            color: "transparent"
            border.width: 2
            border.color: row.tone.lily
            visible: row.activeFocus
        }
        Item {
            id: leadSlot
            anchors.left: parent.left
            anchors.leftMargin: 18
            y: row.stacked ? texts.y + (texts.height - height) / 2 : (row.height - height) / 2
            width: childrenRect.width
            height: childrenRect.height
        }
        ColumnLayout {
            id: texts
            objectName: "settingRowText"
            anchors.left: leadSlot.right
            anchors.leftMargin: leadSlot.width > 0 ? 12 : 0
            anchors.right: row.stacked ? parent.right : slot.left
            anchors.rightMargin: row.stacked ? 18 : 16
            y: row.stacked ? 14 : (row.height - height) / 2
            spacing: 3
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                text: row.title
                textFormat: Text.PlainText
                color: row.tone.ink
                font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
                font.weight: row.strong ? Font.DemiBold : Font.Medium
                wrapMode: row.stacked || row.checkable ? Text.Wrap : Text.NoWrap
                elide: wrapMode === Text.Wrap ? Text.ElideNone : Text.ElideRight
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                visible: row.detail !== ""
                text: row.detail
                textFormat: Text.PlainText
                color: row.tone.dim
                font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                wrapMode: Text.Wrap
            }
        }
        Item {
            id: slot
            objectName: "settingRowControls"
            readonly property real controlsAvailableWidth: Math.max(1, row.width - 36)
            anchors.right: parent.right
            anchors.rightMargin: 18
            y: row.stacked ? Math.max(texts.y + texts.height, leadSlot.y + leadSlot.height) + 12
                : (row.height - height) / 2
            width: childrenRect.width
            height: childrenRect.height
        }
        HoverHandler { id: hover }
        TapHandler {
            enabled: row.tappable
            onTapped: row.tapped()
        }
        Accessible.role: checkable ? Accessible.CheckBox : tappable ? Accessible.Button : Accessible.StaticText
        Accessible.checked: checked
        Accessible.name: title
        Accessible.description: detail
        Accessible.onPressAction: if (tappable) row.tapped()
        Accessible.onToggleAction: if (tappable) row.tapped()
    }

    component Switch: Rectangle {
        id: toggle
        property var tone
        property bool active
        implicitWidth: 44
        implicitHeight: 26
        radius: 13
        color: active ? "#357F72" : (tone.dark ? Qt.rgba(1, 1, 1, 0.18) : Qt.rgba(0.11, 0.106, 0.098, 0.16))
        Behavior on color { ColorAnimation { duration: Math.round(200 * toggle.tone.speed) } }
        Rectangle {
            x: toggle.active ? 21 : 3
            y: 3
            width: 20
            height: 20
            radius: 10
            color: "#FFFFFF"
            Behavior on x { NumberAnimation { duration: Math.round(220 * toggle.tone.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.2, 1, 1] } }
        }
        Accessible.role: Accessible.CheckBox
        Accessible.checked: active
    }

    component Check: Rectangle {
        id: tick
        property var tone
        property bool active
        implicitWidth: 22
        implicitHeight: 22
        radius: 11
        color: active ? "#357F72" : "transparent"
        border.width: active ? 0 : 1.5
        border.color: tone.dark ? Qt.rgba(1, 1, 1, 0.3) : Qt.rgba(0.11, 0.106, 0.098, 0.28)
        Glyph {
            anchors.centerIn: parent
            width: 12
            height: 12
            visible: tick.active
            path: "M5 12.4l4.8 4.6 9.2-10"
            color: "#FFFFFF"
        }
    }

    // Security's mark for each row: lily with a tick when it's as it should be, amber with "!"
    // when it wants a look, an empty ring when Monet can't tell.
    component Mark: Rectangle {
        id: mark
        property var tone
        property bool good
        property bool known: true
        implicitWidth: 22
        implicitHeight: 22
        radius: 11
        color: !known ? "transparent" : good ? "#357F72" : "#D9892E"
        border.width: known ? 0 : 1.5
        border.color: tone.dark ? Qt.rgba(1, 1, 1, 0.3) : Qt.rgba(0.11, 0.106, 0.098, 0.28)
        Glyph {
            anchors.centerIn: parent
            width: 12
            height: 12
            visible: mark.known
            path: mark.good ? "M5 12.4l4.8 4.6 9.2-10" : "M12 5v8M12 18.5v.5"
            color: "#FFFFFF"
        }
    }

    component Bars: Row {
        id: bars
        property var tone
        property int level: 3
        spacing: 2
        Repeater {
            model: [5, 9, 14]
            Rectangle {
                anchors.bottom: parent.bottom
                width: 3
                height: modelData
                radius: 1
                color: index < bars.level ? bars.tone.ink : (bars.tone.dark ? Qt.rgba(1, 1, 1, 0.25) : Qt.rgba(0.11, 0.106, 0.098, 0.22))
            }
        }
        height: 14
    }

    component Pill: Rectangle {
        id: pill
        property var tone
        property string text
        // "plain", "lily", or "sun" (the one bright thing: Play and Restart in Windows).
        property string kind: "plain"
        property bool enabledPill: true
        signal clicked()
        Layout.minimumWidth: 0
        Layout.maximumWidth: parent && parent.width > 0 ? parent.width : Infinity
        implicitWidth: label.implicitWidth + (kind === "sun" ? 40 : 32)
        implicitHeight: Math.max(kind === "sun" ? 44 : 40, label.implicitHeight + 18)
        radius: kind === "sun" ? 20 : 12
        opacity: enabledPill ? 1 : 0.5
        enabled: enabledPill
        color: kind === "sun" ? (hover.hovered ? "#FF6A42" : "#F2552C")
            : kind === "lily" ? (hover.hovered ? "#3F9483" : "#357F72")
            : (hover.hovered ? tone.press : tone.wash2)
        border.width: activeFocus ? 2 : 0
        border.color: kind === "plain" ? tone.lily : "#FFFFFF"
        activeFocusOnTab: enabledPill
        Keys.onSpacePressed: event => { if (enabledPill && !event.isAutoRepeat) pill.clicked() }
        Keys.onReturnPressed: event => { if (enabledPill && !event.isAutoRepeat) pill.clicked() }
        Keys.onEnterPressed: event => { if (enabledPill && !event.isAutoRepeat) pill.clicked() }
        Behavior on color { ColorAnimation { duration: Math.round(140 * pill.tone.speed) } }
        Text {
            horizontalAlignment: Text.AlignHCenter
            id: label
            scale: tap.pressed ? 0.96 : hover.hovered && pill.kind === "sun" ? 1.04 : 1
            Behavior on scale { NumberAnimation { duration: Math.round(160 * pill.tone.speed); easing.type: Easing.OutCubic } }
            anchors.centerIn: parent
            width: Math.min(implicitWidth, Math.max(1, pill.width - 24))
            wrapMode: Text.Wrap
            text: pill.text
            color: pill.kind === "plain" ? pill.tone.ink : "#FFFFFF"
            font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3))
            font.weight: Font.DemiBold
        }
        HoverHandler { id: hover }
        TapHandler {
            id: tap
            enabled: pill.enabledPill
            onTapped: pill.clicked()
        }
        Accessible.role: Accessible.Button
        Accessible.name: text
        Accessible.onPressAction: if (enabledPill) pill.clicked()
    }

    // A few choices side by side, the chosen one on a pebble: [[value, label], …].
    // A key on the keyboard, as a small pebble; the Windows key ("Meta" to KDE) as its four panes.
    component Key: Rectangle {
        id: keyCap
        property var tone
        property string keyName
        implicitWidth: keyName === "Meta" ? 28 : Math.max(26, keyWord.implicitWidth + 14)
        implicitHeight: 24
        radius: 6
        color: tone.wash2
        border.width: 1
        border.color: tone.line
        Text {
            horizontalAlignment: Text.AlignLeft
            id: keyWord
            anchors.centerIn: parent
            visible: keyCap.keyName !== "Meta"
            text: keyCap.keyName
            color: keyCap.tone.ink
            font.pixelSize: Math.max(14, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 2)
            font.weight: Font.DemiBold
        }
        Grid {
            anchors.centerIn: parent
            visible: keyCap.keyName === "Meta"
            columns: 2
            spacing: 2
            Repeater {
                model: 4
                Rectangle {
                    width: 5
                    height: 5
                    radius: 1
                    color: keyCap.tone.ink
                }
            }
        }
    }

    component Segments: Rectangle {
        id: segments
        property var tone
        property var options: []
        property var current
        property real maximumWidth: parent && typeof parent.controlsAvailableWidth === "number"
            ? parent.controlsAvailableWidth : naturalWidth
        readonly property real naturalWidth: {
            // Metric calls depend on the font as well as the option text.
            const measuredFont = segmentMetrics.font
            return options.reduce((width, option) => width
                + Math.ceil(segmentMetrics.advanceWidth(String(option[1]))) + 24, 6 + Math.max(0, options.length - 1) * 2)
        }
        signal picked(var value)
        implicitWidth: Math.min(naturalWidth, maximumWidth)
        implicitHeight: segmentRow.implicitHeight + 6
        radius: 11
        color: tone.wash2
        FontMetrics {
            id: segmentMetrics
            font.family: Kirigami.Theme.defaultFont.family
            font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
            font.weight: Font.DemiBold
        }
        Flow {
            id: segmentRow
            anchors.centerIn: parent
            width: Math.max(1, segments.width - 6)
            spacing: 2
            Repeater {
                model: segments.options
                Rectangle {
                    id: segment
                    required property var modelData
                    readonly property bool chosen: segments.current === modelData[0]
                    implicitWidth: Math.ceil(segmentMetrics.advanceWidth(String(modelData[1]))) + 24
                    width: Math.min(implicitWidth, segmentRow.width)
                    height: Math.max(34, segmentLabel.implicitHeight + 14)
                    radius: 9
                    color: chosen ? (segments.tone.dark ? Qt.rgba(1, 1, 1, 0.17) : "#FFFFFF")
                        : segmentHover.hovered ? segments.tone.press : "transparent"
                    border.width: segment.activeFocus ? 2 : 0
                    border.color: segments.tone.lily
                    activeFocusOnTab: true
                    Keys.onSpacePressed: segments.picked(modelData[0])
                    Keys.onReturnPressed: segments.picked(modelData[0])
                    Keys.onEnterPressed: segments.picked(modelData[0])
                    Behavior on color { ColorAnimation { duration: Math.round(140 * segments.tone.speed) } }
                    Text {
                        id: segmentLabel
                        horizontalAlignment: Text.AlignHCenter
                        anchors.centerIn: parent
                        width: Math.max(0, segment.width - 16)
                        text: segment.modelData[1]
                        textFormat: Text.PlainText
                        wrapMode: Text.WordWrap
                        elide: Text.ElideRight
                        color: segments.tone.ink
                        font.family: segmentMetrics.font.family
                        font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                        font.weight: segment.chosen ? Font.DemiBold : Font.Medium
                    }
                    HoverHandler { id: segmentHover }
                    TapHandler { onTapped: segments.picked(segment.modelData[0]) }
                    Accessible.role: Accessible.RadioButton
                    Accessible.name: modelData[1]
                    Accessible.checked: chosen
                    Accessible.onPressAction: segments.picked(modelData[0])
                }
            }
        }
    }

    component SliderRow: Item {
        id: sliderRow
        property var tone
        property string title
        property real from: 0
        property real to: 100
        property real value: 0
        property bool divider: true
        signal moved(real value)
        signal held(bool down)
        Layout.fillWidth: true
        implicitHeight: 54
        Rectangle {
            visible: sliderRow.divider
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: 18
            anchors.rightMargin: 18
            height: 1
            color: sliderRow.tone.line
        }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 18
            anchors.rightMargin: 18
            spacing: 16
            // Room for the longer words other languages use ("Zeigergeschwindigkeit"), up to a point.
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.preferredWidth: Math.min(Math.max(120, implicitWidth), 190)
                elide: Text.ElideRight
                text: sliderRow.title
                color: sliderRow.tone.ink
                font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
                font.weight: Font.DemiBold
            }
            Slide {
                tone: sliderRow.tone
                Layout.fillWidth: true
                from: sliderRow.from
                to: sliderRow.to
                stepSize: 1
                value: sliderRow.value
                Accessible.name: sliderRow.title
                onPressedChanged: sliderRow.held(pressed)
                onMoved: sliderRow.moved(value)
            }
        }
    }

    // A slider: a lily track and a white stone.
    component Slide: T.Slider {
        id: slide
        wheelEnabled: false
        property var tone
        implicitWidth: 200
        implicitHeight: 28
        background: Rectangle {
            x: slide.leftPadding
            y: slide.topPadding + (slide.availableHeight - height) / 2
            width: slide.availableWidth
            height: 4
            radius: 2
            color: slide.tone.wash2
            Rectangle {
                width: slide.visualPosition * parent.width
                height: parent.height
                radius: 2
                color: slide.tone.lily
            }
        }
        handle: Rectangle {
            x: slide.leftPadding + slide.visualPosition * (slide.availableWidth - width)
            y: slide.topPadding + (slide.availableHeight - height) / 2
            width: 20
            height: 20
            radius: 10
            color: "#FFFFFF"
            border.width: slide.visualFocus ? 2 : 1
            border.color: slide.visualFocus ? slide.tone.lily : Qt.rgba(0, 0, 0, 0.18)
            scale: slide.pressed ? 1.1 : 1
            Behavior on scale { NumberAnimation { duration: Math.round(120 * slide.tone.speed) } }
        }
    }

    // A list's scroll bar: a thin stroke that shows while it's used.
    component Rail: T.ScrollBar {
        id: rail
        property var tone
        implicitWidth: 10
        padding: 2
        contentItem: Rectangle {
            implicitWidth: 6
            radius: 3
            color: rail.tone.dim
            opacity: rail.policy === T.ScrollBar.AlwaysOn || rail.active ? 0.55 : 0
            Behavior on opacity { NumberAnimation { duration: Math.round(200 * rail.tone.speed) } }
        }
    }

    // Still working, with no number to show: a short lily stroke going along.
    component Busy: T.ProgressBar {
        id: meter
        property var tone
        property bool active: true
        implicitWidth: 200
        implicitHeight: 4
        background: Rectangle {
            radius: 2
            color: meter.tone.wash2
        }
        contentItem: Item {
            clip: true
            Rectangle {
                id: stroke
                width: parent.width * 0.3
                height: parent.height
                radius: 2
                color: meter.tone.lily
                NumberAnimation on x {
                    running: meter.visible && meter.active
                    loops: Animation.Infinite
                    from: -stroke.width
                    to: meter.width
                    duration: 1400
                }
            }
        }
    }

    // A well to type in, like Wi-Fi's password.
    component Field: Rectangle {
        id: field
        property var tone
        property alias text: input.text
        property string hint
        property bool secret
        signal accepted()
        function focusInput() {
            input.forceActiveFocus()
        }
        Layout.fillWidth: true
        Layout.preferredHeight: 38
        radius: 12
        color: tone.dark ? Qt.rgba(0, 0, 0, 0.28) : Qt.rgba(1, 1, 1, 0.9)
        border.width: input.activeFocus ? 2 : 1
        border.color: input.activeFocus ? tone.lily : tone.line
        TextInput {
            id: input
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            verticalAlignment: TextInput.AlignVCenter
            echoMode: field.secret ? TextInput.Password : TextInput.Normal
            color: field.tone.ink
            font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
            clip: true
            selectByMouse: true
            selectionColor: field.tone.lily
            Accessible.role: Accessible.EditableText
            Accessible.name: field.hint
            onAccepted: field.accepted()
            Text {
                horizontalAlignment: Text.AlignLeft
                anchors.fill: parent
                verticalAlignment: Text.AlignVCenter
                visible: input.text === ""
                text: field.hint
                color: field.tone.dim
                font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
            }
        }
    }

    // Someone's picture, or their initial on a glaze.
    component Face: Item {
        id: face
        property string name
        property string picture
        property var glaze: ["#4DB4A0", "#245A50"]
        Rounded {
            anchors.fill: parent
            radius: width / 2
            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0; color: face.glaze[0] }
                    GradientStop { position: 1; color: face.glaze[1] }
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: -1
                    text: face.name.charAt(0).toUpperCase()
                    color: "#FBF7EE"
                    font.family: "Fraunces 72pt SuperSoft"
                    font.pixelSize: Math.round(face.height * 0.46)
                }
            }
            Image {
                anchors.fill: parent
                source: face.picture !== "" ? "file://" + encodeURI(face.picture) : ""
                sourceSize: Qt.size(face.width * 2, face.height * 2)
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                cache: false
                visible: status === Image.Ready
            }
        }
        Accessible.role: Accessible.Graphic
        Accessible.name: name
    }

    // The game covers on Play on Windows.
    component Cover: Item {
        id: cover
        property string name
        property string artwork
        property var glaze: ["#5C88D0", "#1B2546"]
        property bool here: false
        signal picked()
        implicitHeight: width * 215 / 460
        scale: tap.pressed ? 0.97 : hover.hovered ? 1.03 : 1
        Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }
        Rounded {
            anchors.fill: parent
            radius: 10
            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: cover.glaze[0] }
                    GradientStop { position: 1; color: cover.glaze[1] }
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    anchors.fill: parent
                    anchors.margins: 10
                    verticalAlignment: Text.AlignBottom
                    text: cover.name
                    color: "#FFFFFF"
                    elide: Text.ElideRight
                    font.family: "Fraunces 72pt SuperSoft"
                    font.pixelSize: Math.max(12, Math.round(parent.height * 0.17))
                }
            }
            Image {
                anchors.fill: parent
                source: cover.artwork
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                visible: status === Image.Ready
            }
            // A pebble on the corner: this one plays in Monet too.
            Rectangle {
                visible: cover.here
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.margins: 6
                width: hereText.implicitWidth + 14
                height: 20
                radius: 10
                color: Qt.rgba(0.11, 0.106, 0.098, 0.72)
                Text {
                    id: hereText
                    anchors.centerIn: parent
                    text: i18n("Plays here too")
                    color: "#FFFFFF"
                    font.pixelSize: Math.max(13, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 3)
                    font.weight: Font.DemiBold
                }
            }
        }
        HoverHandler { id: hover }
        TapHandler {
            id: tap
            onTapped: cover.picked()
        }
        Accessible.role: Accessible.Button
        Accessible.name: i18n("Play %1", name)
        Accessible.onPressAction: cover.picked()
    }
}
