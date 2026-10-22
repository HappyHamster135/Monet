/*
 * Clock: the time and the date in the panel, in Monet's type. A click opens
 * the day and its month on the panel's glass: the day's name in Fraunces,
 * the month as Monet's calendar draws it, today on a dab of the sun.
 */
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    property date now: new Date()
    // The month on the page: its first day.
    property date shown: new Date(now.getFullYear(), now.getMonth(), 1)
    readonly property int firstWeekday: Qt.locale().firstDayOfWeek  // 0 is Sunday
    readonly property color ink: Kirigami.Theme.textColor
    readonly property color dim: Qt.rgba(ink.r, ink.g, ink.b, 0.62)

    function turn(by) {
        shown = new Date(shown.getFullYear(), shown.getMonth() + by, 1);
    }

    // The 42 days the page shows, from the week the month starts in.
    readonly property var days: {
        const lead = (shown.getDay() - firstWeekday + 7) % 7;
        const out = [];
        for (let i = 0; i < 42; i++) {
            out.push(new Date(shown.getFullYear(), shown.getMonth(), 1 - lead + i));
        }
        return out;
    }

    Plasmoid.icon: "x-office-calendar"
    toolTipMainText: Qt.formatDate(now, Qt.locale().dateFormat(Locale.LongFormat))
    toolTipSubText: Qt.formatTime(now, Qt.locale().timeFormat(Locale.ShortFormat))
    // Back on this month whenever the page opens.
    onExpandedChanged: if (expanded) shown = new Date(now.getFullYear(), now.getMonth(), 1)

    Timer {
        // On the minute, so the time turns when the clock on the wall does.
        interval: (60 - new Date().getSeconds()) * 1000
        running: true
        repeat: true
        onTriggered: {
            const following = root.shown.getMonth() === root.now.getMonth() && root.shown.getFullYear() === root.now.getFullYear();
            root.now = new Date();
            if (following && root.now.getDate() === 1) {
                root.shown = new Date(root.now.getFullYear(), root.now.getMonth(), 1);
            }
            interval = (60 - root.now.getSeconds()) * 1000;
        }
    }

    compactRepresentation: MouseArea {
        Layout.minimumWidth: Math.max(time.implicitWidth, date.implicitWidth) + Kirigami.Units.smallSpacing * 2
        Layout.preferredWidth: Layout.minimumWidth
        hoverEnabled: true
        onClicked: root.expanded = !root.expanded

        Column {
            anchors.centerIn: parent
            spacing: 0
            Text {
                id: time
                anchors.horizontalCenter: parent.horizontalCenter
                text: Qt.formatTime(root.now, Qt.locale().timeFormat(Locale.ShortFormat))
                color: root.ink
                font.family: "Inter"
                font.pixelSize: 14
                font.weight: Font.DemiBold
                font.features: { "tnum": 1 }
            }
            Text {
                id: date
                anchors.horizontalCenter: parent.horizontalCenter
                text: Qt.formatDate(root.now, "ddd d MMM")
                color: root.dim
                font.family: "Inter"
                font.pixelSize: 11
            }
        }
    }

    fullRepresentation: ColumnLayout {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 16
        Layout.preferredWidth: Kirigami.Units.gridUnit * 17
        Layout.preferredHeight: Kirigami.Units.gridUnit * 18
        spacing: Kirigami.Units.smallSpacing

        // The day.
        Text {
            Layout.fillWidth: true
            Layout.leftMargin: Kirigami.Units.smallSpacing
            text: Qt.locale().standaloneDayName(root.now.getDay(), Locale.LongFormat)
            color: root.ink
            font.family: "Fraunces 72pt SuperSoft"
            font.pixelSize: 28
            font.weight: Font.Light
            elide: Text.ElideRight
        }
        Text {
            Layout.fillWidth: true
            Layout.leftMargin: Kirigami.Units.smallSpacing
            Layout.bottomMargin: Kirigami.Units.largeSpacing
            text: Qt.formatDate(root.now, Qt.locale().dateFormat(Locale.LongFormat).replace(/dddd,?\s*/i, ""))
            color: root.dim
            font.family: "Inter"
            font.pixelSize: 13
            elide: Text.ElideRight
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Qt.rgba(root.ink.r, root.ink.g, root.ink.b, 0.12)
        }

        // The month's page, with arrows to turn it.
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: Kirigami.Units.smallSpacing
            Text {
                Layout.fillWidth: true
                Layout.leftMargin: Kirigami.Units.smallSpacing
                text: Qt.locale().standaloneMonthName(root.shown.getMonth())
                      + (root.shown.getFullYear() !== root.now.getFullYear() ? " " + root.shown.getFullYear() : "")
                color: root.ink
                elide: Text.ElideRight
                font.family: "Fraunces 72pt SuperSoft"
                font.pixelSize: 19
                MouseArea {
                    anchors.fill: parent
                    onClicked: root.shown = new Date(root.now.getFullYear(), root.now.getMonth(), 1)
                }
            }
            Repeater {
                model: [-1, 1]
                Rectangle {
                    required property int modelData
                    Layout.preferredWidth: 28
                    Layout.preferredHeight: 28
                    radius: 14
                    color: turnArea.containsMouse ? Qt.rgba(root.ink.r, root.ink.g, root.ink.b, 0.08) : "transparent"
                    Text {
                        anchors.centerIn: parent
                        anchors.verticalCenterOffset: -1
                        text: parent.modelData < 0 ? "‹" : "›"
                        color: turnArea.containsMouse ? root.ink : root.dim
                        font.family: "Inter"
                        font.pixelSize: 20
                    }
                    MouseArea {
                        id: turnArea
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: root.turn(parent.modelData)
                    }
                    Accessible.role: Accessible.Button
                    Accessible.name: modelData < 0 ? i18n("Previous month") : i18n("Next month")
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: 7
            rowSpacing: 0
            columnSpacing: 0

            // The days of the week, as letters.
            Repeater {
                model: 7
                Text {
                    required property int index
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.bottomMargin: 4
                    horizontalAlignment: Text.AlignHCenter
                    text: Qt.locale().dayName((root.firstWeekday + index) % 7, Locale.NarrowFormat)
                    color: root.dim
                    font.family: "Inter"
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                }
            }

            Repeater {
                model: root.days
                Item {
                    id: cell
                    required property var modelData
                    readonly property bool inMonth: modelData.getMonth() === root.shown.getMonth()
                    readonly property bool isToday: modelData.toDateString() === root.now.toDateString()
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.fillHeight: true
                    implicitHeight: 30

                    // Today: a dab of the sun.
                    Rectangle {
                        anchors.centerIn: parent
                        width: Math.min(parent.width, parent.height) - 4
                        height: width
                        radius: width / 2
                        visible: cell.isToday
                        gradient: Gradient {
                            GradientStop { position: 0; color: "#FF7A45" }
                            GradientStop { position: 1; color: "#E2471F" }
                        }
                    }
                    Text {
                        anchors.centerIn: parent
                        text: cell.modelData.getDate()
                        color: cell.isToday ? "#FBF7EE" : root.ink
                        opacity: cell.inMonth ? 1 : 0.32
                        font.family: "Inter"
                        font.pixelSize: 13
                        font.weight: cell.isToday ? Font.DemiBold : Font.Normal
                        font.features: { "tnum": 1 }
                    }
                }
            }
        }
    }
}
