/*
 * Calendar: the month on Monet's glass, its name in Fraunces and today on a
 * dab of the sun. The arrows turn the page; a click on the name comes back
 * to today.
 */
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    property date today: new Date()
    // The month on the page: its first day.
    property date shown: new Date(today.getFullYear(), today.getMonth(), 1)
    readonly property int firstWeekday: Qt.locale().firstDayOfWeek  // 0 is Sunday

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

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "x-office-calendar"
    preferredRepresentation: fullRepresentation
    toolTipMainText: Qt.formatDate(today, Qt.locale().dateFormat(Locale.LongFormat))

    Timer {
        // The day turns at midnight.
        interval: 60 * 1000
        running: true
        repeat: true
        onTriggered: {
            const now = new Date();
            if (now.getDate() !== root.today.getDate()) {
                const following = root.shown.getMonth() === root.today.getMonth();
                root.today = now;
                if (following) {
                    root.shown = new Date(now.getFullYear(), now.getMonth(), 1);
                }
            }
        }
    }

    fullRepresentation: Item {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 11
        Layout.minimumHeight: Kirigami.Units.gridUnit * 11
        Layout.preferredWidth: Kirigami.Units.gridUnit * 12
        Layout.preferredHeight: Kirigami.Units.gridUnit * 12

        Glass {
            id: card
            anchors.fill: parent

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Kirigami.Units.gridUnit * 0.8
                spacing: Kirigami.Units.smallSpacing

                RowLayout {
                    Layout.fillWidth: true

                    Text {
                        Layout.fillWidth: true
                        text: Qt.locale().standaloneMonthName(root.shown.getMonth())
                              + (root.shown.getFullYear() !== root.today.getFullYear() ? " " + root.shown.getFullYear() : "")
                        color: card.ink
                        elide: Text.ElideRight
                        font.family: "Fraunces 72pt SuperSoft"
                        font.pixelSize: 20
                        MouseArea {
                            anchors.fill: parent
                            onClicked: root.shown = new Date(root.today.getFullYear(), root.today.getMonth(), 1)
                        }
                    }
                    Repeater {
                        model: [-1, 1]
                        Text {
                            required property int modelData
                            text: modelData < 0 ? "‹" : "›"
                            color: turnArea.containsMouse ? card.ink : card.dim
                            font.family: "Inter"
                            font.pixelSize: 20
                            Layout.preferredWidth: 18
                            horizontalAlignment: Text.AlignHCenter
                            MouseArea {
                                id: turnArea
                                anchors.fill: parent
                                anchors.margins: -6
                                hoverEnabled: true
                                onClicked: root.turn(parent.modelData)
                            }
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
                            horizontalAlignment: Text.AlignHCenter
                            text: Qt.locale().dayName((root.firstWeekday + index) % 7, Locale.NarrowFormat)
                            color: card.dim
                            font.family: "Inter"
                            font.pixelSize: 10
                            font.weight: Font.DemiBold
                        }
                    }

                    Repeater {
                        model: root.days
                        Item {
                            id: cell
                            required property var modelData
                            readonly property bool inMonth: modelData.getMonth() === root.shown.getMonth()
                            readonly property bool isToday: modelData.toDateString() === root.today.toDateString()
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            Layout.fillHeight: true
                            implicitHeight: 20

                            // Today: a dab of the sun.
                            Rectangle {
                                anchors.centerIn: parent
                                width: Math.min(parent.width, parent.height) - 2
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
                                color: cell.isToday ? "#FBF7EE" : card.ink
                                opacity: cell.inMonth ? 1 : 0.32
                                font.family: "Inter"
                                font.pixelSize: 12
                                font.weight: cell.isToday ? Font.DemiBold : Font.Normal
                            }
                        }
                    }
                }
            }
        }
    }
}
