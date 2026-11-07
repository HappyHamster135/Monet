/*
 * A day's note, to read and to write: the date in Fraunces, the day before
 * and after (and back to today), the note on a sheet of paper, kept as you
 * type, and the next days that have a note, a click away. The Calendar
 * widget shows it in a panel beside the month; the bar's clock, beside its
 * month in a separate inward-opening panel.
 *
 * install.sh copies this file into the Calendar's and the Clock's packages.
 */
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Templates as T
import QtQuick.Window
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: page

    property QtObject store: null
    property date day
    property date today
    property color ink
    property color dim
    property color lily
    // A way to put it away (the Calendar's panel); the clock's has its own.
    property bool closable: false
    property string recurrence: "none"
    // To another day: the day before or after, today, or one coming up.
    signal moved(date day)
    signal closed()

    spacing: 8
    Keys.onEscapePressed: { keepNow(); closed(); }
    onVisibleChanged: if (!visible) keepNow()
    Component.onDestruction: keepNow()

    function sameDay(a, b) {
        return a.toDateString() === b.toDateString();
    }

    function step(by) {
        moved(new Date(day.getFullYear(), day.getMonth(), day.getDate() + by));
    }

    // What's typed is kept before anything else shows.
    function keepNow() {
        if (keep.running) {
            keep.stop();
            store.write(note.written, note.text, recurrence);
        }
    }

    function write() {
        note.forceActiveFocus();
        note.cursorPosition = note.length;
    }

    // Another day: keep what was written, then show its own.
    onDayChanged: {
        keepNow();
        note.written = day;
        recurrence = store ? store.repeatFor(day) : "none";
        note.text = store ? store.noteFor(day) : "";
    }
    // Notes that arrive (from the helper, or the other calendar), unless they're being typed.
    Connections {
        target: page.store
        function onNotesChanged() {
            if (!note.activeFocus && !keep.running) {
                note.text = page.store.noteFor(page.day);
                page.recurrence = page.store.repeatFor(page.day);
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 8

        // The date, today's in the sun's color.
        Text {
            horizontalAlignment: Text.AlignLeft
            text: page.day.getDate()
            color: page.sameDay(page.day, page.today) ? "#E2471F" : page.ink
            font.family: "Fraunces 72pt SuperSoft"
            font.pixelSize: 40
            font.features: { "tnum": 1 }
            Layout.alignment: Qt.AlignVCenter
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0
            Text {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignLeft
                text: Qt.locale().dayName(page.day.getDay(), Locale.LongFormat)
                color: page.ink
                elide: Text.ElideRight
                font.family: "Fraunces 72pt SuperSoft"
                font.italic: true
                font.pixelSize: 17
            }
            Text {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignLeft
                text: Qt.locale().standaloneMonthName(page.day.getMonth()) + " " + page.day.getFullYear()
                color: page.dim
                elide: Text.ElideRight
                font.family: "Inter"
                font.pixelSize: 12
            }
        }
        T.AbstractButton {
            id: toToday
            visible: !page.sameDay(page.day, page.today)
            text: i18n("Today")
            implicitWidth: todayLabel.implicitWidth + 18
            implicitHeight: 26
            onClicked: page.moved(page.today)
            background: Rectangle {
                radius: height / 2
                color: page.lily
                opacity: toToday.hovered ? 0.2 : 0.12
            }
            contentItem: Text {
                id: todayLabel
                text: toToday.text
                color: page.lily
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.family: "Inter"
                font.pixelSize: 12
                font.weight: Font.DemiBold
            }
        }
        // The day before, the day after.
        Repeater {
            model: [-1, 1]
            Item {
                id: stepper
                activeFocusOnTab: true
                Keys.onReturnPressed: page.step(stepper.modelData)
                Keys.onEnterPressed: page.step(stepper.modelData)
                Keys.onSpacePressed: page.step(stepper.modelData)
                Accessible.onPressAction: page.step(stepper.modelData)
                required property int modelData
                Layout.preferredWidth: 26
                Layout.preferredHeight: 26
                Accessible.role: Accessible.Button
                Accessible.name: modelData < 0 ? i18n("The day before") : i18n("The day after")
                Rectangle {
                    anchors.fill: parent
                    radius: 13
                    color: stepper.activeFocus ? "transparent" : page.ink
                    border.width: stepper.activeFocus ? 2 : 0
                    border.color: page.lily
                    opacity: stepper.activeFocus ? 1 : stepArea.pressed ? 0.14 : stepArea.containsMouse ? 0.08 : 0
                }
                Text {
                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: -1
                    text: (stepper.modelData < 0) !== page.LayoutMirroring.enabled ? "‹" : "›"
                    color: stepArea.containsMouse ? page.ink : page.dim
                    font.family: "Inter"
                    font.pixelSize: 20
                }
                MouseArea {
                    id: stepArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: page.step(stepper.modelData)
                }
            }
        }
        // Put away.
        Item {
            id: closeButton
            visible: page.closable
            activeFocusOnTab: true
            Keys.onReturnPressed: { page.keepNow(); page.closed(); }
            Keys.onSpacePressed: { page.keepNow(); page.closed(); }
            Accessible.onPressAction: { page.keepNow(); page.closed(); }
            Layout.preferredWidth: 26
            Layout.preferredHeight: 26
            Accessible.role: Accessible.Button
            Accessible.name: i18n("Close")
            Rectangle {
                anchors.fill: parent
                radius: 13
                color: closeButton.activeFocus ? "transparent" : page.ink
                border.width: closeButton.activeFocus ? 2 : 0
                border.color: page.lily
                opacity: closeButton.activeFocus ? 1 : closeArea.pressed ? 0.14 : closeArea.containsMouse ? 0.08 : 0
            }
            Text {
                anchors.centerIn: parent
                text: "×"
                color: closeArea.containsMouse ? page.ink : page.dim
                font.family: "Inter"
                font.pixelSize: 18
            }
            MouseArea {
                id: closeArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    page.keepNow();
                    page.closed();
                }
            }
        }
    }

    // The day's note, on a sheet of paper.
    Rectangle {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: 90
        // Lighter glass with light in its rim, as Monet's fields are.
        readonly property bool dark: page.ink.hslLightness > 0.5
        radius: 12
        color: dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.34)
        border.width: note.activeFocus ? 2 : 1
        border.color: note.activeFocus ? page.lily : dark ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(1, 1, 1, 0.75)

        QQC2.ScrollView {
            anchors.fill: parent
            anchors.margins: 4
            QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff

            QQC2.TextArea {
                id: note
                // The day this text belongs to, so a save on its way keeps to it.
                property date written: new Date()
                placeholderText: i18n("Nothing planned. Write something for this day…")
                placeholderTextColor: page.dim
                color: page.ink
                wrapMode: TextEdit.Wrap
                font.family: "Inter"
                font.pixelSize: 13
                selectionColor: "#9FD3C4"
                selectedTextColor: "#1C1B19"
                background: null
                Keys.onTabPressed: repeatChoice.forceActiveFocus()
                Keys.onEscapePressed: {
                    page.keepNow();
                    page.closed();
                }
                onTextChanged: if (activeFocus) keep.restart()
                onActiveFocusChanged: if (!activeFocus) page.keepNow()
                Accessible.name: i18n("Note for %1", Qt.formatDate(page.day, Qt.locale().dateFormat(Locale.LongFormat)))
                KeyNavigation.tab: repeatChoice
                Component.onCompleted: {
                    written = page.day;
                    text = page.store ? page.store.noteFor(page.day) : "";
                    page.recurrence = page.store ? page.store.repeatFor(page.day) : "none";
                }
            }
        }

        Timer {
            id: keep
            interval: 600
            onTriggered: page.store.write(note.written, note.text, page.recurrence)
        }
    }

    RowLayout {
        Layout.fillWidth: true
        T.AbstractButton {
            id: repeatChoice
            objectName: "noteRepeat"
            Layout.fillWidth: true
            implicitHeight: Math.max(42, repeatLabel.implicitHeight + 20)
            leftPadding: mirrored ? 42 : 16
            rightPadding: mirrored ? 16 : 42
            hoverEnabled: true
            activeFocusOnTab: true
            readonly property color fill: "#357F72"
            readonly property var intervals: ["none", "yearly", "monthly", "weekly", "daily"]
            readonly property var model: [i18n("Doesn't repeat"), i18n("Every year"), i18n("Every month"), i18n("Every week"), i18n("Every day")]
            readonly property int currentIndex: Math.max(0, intervals.indexOf(page.recurrence))
            readonly property string displayText: model[currentIndex]
            property int highlightedIndex: currentIndex
            signal activated(int index)
            Accessible.name: i18n("Repeat note")
            Accessible.role: Accessible.ComboBox
            Accessible.description: displayText
            function choose(index) {
                if (index < 0 || index >= model.length) return
                activated(index)
                popup.close()
            }
            function togglePicker() {
                if (popup.visible) popup.close()
                else { highlightedIndex = currentIndex; popup.open() }
            }
            function key(event) {
                let index = popup.visible ? highlightedIndex : currentIndex
                if (event.key === Qt.Key_Down) index = Math.min(model.length - 1, index + 1)
                else if (event.key === Qt.Key_Up) index = Math.max(0, index - 1)
                else if (event.key === Qt.Key_Home) index = 0
                else if (event.key === Qt.Key_End) index = model.length - 1
                else if ([Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space].includes(event.key)) {
                    if (popup.visible) choose(highlightedIndex)
                    else togglePicker()
                    event.accepted = true; return
                } else { event.accepted = false; return }
                if (popup.visible) {
                    highlightedIndex = index
                    repeatOptions.positionViewAtIndex(index, ListView.Contain)
                } else choose(index)
                event.accepted = true
            }
            onClicked: togglePicker()
            Keys.onPressed: event => key(event)
            contentItem: Text {
                id: repeatLabel
                text: repeatChoice.displayText
                color: "#FBF7EE"
                font.family: "Inter"
                font.pixelSize: Math.max(13, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3))
                verticalAlignment: Text.AlignVCenter
                horizontalAlignment: repeatChoice.mirrored ? Text.AlignRight : Text.AlignLeft
                elide: Text.ElideRight
            }
            background: Rectangle {
                radius: 12
                color: repeatChoice.down ? "#2C6D62" : repeatChoice.fill
                border.width: repeatChoice.visualFocus ? 2 : 0
                border.color: "#9FD3C4"
            }
            indicator: Item {
                x: repeatChoice.mirrored ? 16 : repeatChoice.width - width - 16
                y: (repeatChoice.height - height) / 2
                width: 12; height: 8
                rotation: repeatChoice.popup.visible ? 180 : 0
                Behavior on rotation { NumberAnimation { duration: Kirigami.Units.shortDuration } }
                Rectangle { x: 1; y: 3; width: 7; height: 1.5; radius: 0.75; rotation: 40; color: "#FBF7EE" }
                Rectangle { x: 6; y: 3; width: 7; height: 1.5; radius: 0.75; rotation: -40; color: "#FBF7EE" }
            }
            property Component optionDelegate: T.ItemDelegate {
                id: option
                required property int index
                required property var modelData
                objectName: "noteRepeatOption-" + index
                width: ListView.view ? ListView.view.width : repeatChoice.width - 12
                implicitHeight: Math.max(40, optionText.implicitHeight + 18)
                leftPadding: repeatChoice.mirrored ? 36 : 14; rightPadding: repeatChoice.mirrored ? 14 : 36
                text: modelData
                hoverEnabled: true
                highlighted: repeatChoice.highlightedIndex === index
                onHoveredChanged: if (hovered) repeatChoice.highlightedIndex = index
                onClicked: repeatChoice.choose(index)
                Accessible.name: text
                contentItem: Text {
                    id: optionText
                    text: option.text
                    color: "#FBF7EE"
                    font: repeatLabel.font
                    wrapMode: Text.Wrap
                    verticalAlignment: Text.AlignVCenter
                    horizontalAlignment: repeatChoice.mirrored ? Text.AlignRight : Text.AlignLeft
                }
                background: Rectangle {
                    radius: 10
                    color: option.down ? "#2C6D62" : repeatChoice.fill
                    opacity: option.highlighted || option.hovered || option.index === repeatChoice.currentIndex ? 1 : 0.82
                    border.width: option.highlighted || option.index === repeatChoice.currentIndex ? 2 : 0
                    border.color: "#9FD3C4"
                    Text {
                        anchors.right: parent.right; anchors.rightMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        visible: option.index === repeatChoice.currentIndex
                        text: "✓"; color: "#FBF7EE"; font.pixelSize: 14
                    }
                }
            }
            readonly property QQC2.Popup popup: QQC2.Popup {
                id: repeatPopup
                objectName: "noteRepeatPopup"
                // Plasma's Dialog can offset its Controls overlay. Position
                // directly in that overlay, measuring room in the real window.
                popupType: QQC2.Popup.Item
                focus: true
                onOpened: repeatOptions.forceActiveFocus(Qt.PopupFocusReason)
                readonly property Item overlayItem: repeatChoice.QQC2.Overlay.overlay
                parent: overlayItem || repeatChoice
                readonly property Item windowContent: repeatChoice.Window.window ? repeatChoice.Window.window.contentItem : null
                readonly property point anchorPoint: {
                    // mapToItem alone does not track layout changes. Observe
                    // the ancestor geometry so resizing/reopening stays anchored.
                    for (let item = repeatChoice; item && item !== windowContent; item = item.parent) {
                        const geometry = [item.x, item.y, item.width, item.height, item.scale, item.rotation]
                    }
                    return windowContent ? repeatChoice.mapToItem(windowContent, 0, 0) : Qt.point(0, 0)
                }
                readonly property real anchorY: anchorPoint.y
                readonly property point overlayAnchor: {
                    const anchor = anchorPoint
                    if (!overlayItem) return Qt.point(0, 0)
                    const geometry = [overlayItem.x, overlayItem.y, overlayItem.width, overlayItem.height]
                    return repeatChoice.mapToItem(overlayItem, 0, 0)
                }
                readonly property real above: Math.max(1, anchorY - 8)
                readonly property real below: windowContent ? Math.max(1, windowContent.height - anchorY - repeatChoice.height - 8) : 1
                readonly property real desiredHeight: repeatOptions.contentHeight + topPadding + bottomPadding
                readonly property bool opensDown: below >= desiredHeight || below >= above
                x: overlayAnchor.x
                y: overlayAnchor.y + (opensDown ? repeatChoice.height + 6 : -height - 6)
                width: repeatChoice.width
                height: Math.min(desiredHeight, opensDown ? below : above)
                padding: 6
                // The overlay origin can be outside the window; our bounds
                // above already constrain the visible menu to the window.
                margins: -1
                closePolicy: QQC2.Popup.CloseOnEscape | QQC2.Popup.CloseOnPressOutside
                background: Rectangle {
                    radius: 15
                    color: page.ink.hslLightness > 0.5 ? "#292824" : "#F7F5EF"
                    border.width: 1; border.color: page.lily
                }
                contentItem: ListView {
                    id: repeatOptions
                    objectName: "noteRepeatOptions"
                    clip: true
                    LayoutMirroring.enabled: repeatChoice.mirrored
                    LayoutMirroring.childrenInherit: true
                    spacing: 4
                    model: repeatPopup.visible ? repeatChoice.model : null
                    delegate: repeatChoice.optionDelegate
                    currentIndex: repeatChoice.highlightedIndex
                    focus: true
                    Keys.onPressed: event => repeatChoice.key(event)
                    boundsBehavior: Flickable.StopAtBounds
                    QQC2.ScrollIndicator.vertical: QQC2.ScrollIndicator {}
                }
            }
            onActivated: index => {
                page.keepNow();
                page.recurrence = intervals[index];
                if (note.text.trim()) page.store.write(note.written,note.text,page.recurrence);
            }
        }
    }
    Text {
        Layout.fillWidth: true
        visible: page.recurrence !== "none"
        text: i18n("Changes apply to every occurrence.")
            + (page.recurrence === "monthly" && page.day.getDate() > 28
               ? " " + i18n("Months without this date are skipped.")
               : page.recurrence === "yearly" && page.day.getMonth() === 1 && page.day.getDate() === 29
               ? " " + i18n("29 February repeats in leap years.") : "")
        color: page.dim; font.pixelSize: 11; wrapMode: Text.WordWrap
    }
    QQC2.Button {
        Layout.fillWidth: true
        visible: page.store && page.store.problem !== ""
        text: i18n("Try saving again")
        Accessible.description: page.store ? page.store.problem : ""
        onClicked: page.store.retry()
    }

    // The next days with a note.
    Text {
        Layout.fillWidth: true
        Layout.topMargin: 2
        horizontalAlignment: Text.AlignLeft
        visible: upcoming.count > 0
        text: i18n("Coming up")
        color: page.dim
        font.family: "Inter"
        font.pixelSize: 11
        font.weight: Font.DemiBold
        font.capitalization: Font.AllUppercase
        font.letterSpacing: 0.6
    }
    Repeater {
        id: upcoming
        model: page.store ? page.store.after(page.day, 3) : []
        Item {
            id: soon
            activeFocusOnTab: true
            Keys.onReturnPressed: page.moved(soon.modelData.day)
            Keys.onSpacePressed: page.moved(soon.modelData.day)
            Accessible.onPressAction: page.moved(soon.modelData.day)
            required property var modelData
            Layout.fillWidth: true
            Layout.preferredHeight: 26
            Accessible.role: Accessible.Button
            Accessible.name: Qt.locale().toString(modelData.day, Qt.locale().dateFormat(Locale.LongFormat)) + ", "
                             + modelData.text.split("\n")[0]
            Rectangle {
                anchors.fill: parent
                radius: 9
                color: page.ink
                border.width: soon.activeFocus ? 2 : 0
                border.color: page.lily
                opacity: soon.activeFocus ? 0.3 : soonArea.pressed ? 0.12 : soonArea.containsMouse ? 0.07 : 0
            }
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 8
                // A dot of lily, as the month marks the day.
                Rectangle {
                    Layout.preferredWidth: 5
                    Layout.preferredHeight: 5
                    radius: 2.5
                    color: page.lily
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    text: Qt.locale().toString(soon.modelData.day, "ddd d MMM")
                    color: page.ink
                    font.family: "Inter"
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                }
                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignLeft
                    text: soon.modelData.text.split("\n")[0]
                    textFormat: Text.PlainText
                    color: page.dim
                    elide: Text.ElideRight
                    font.family: "Inter"
                    font.pixelSize: 12
                }
            }
            MouseArea {
                id: soonArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: page.moved(soon.modelData.day)
            }
        }
    }
}
