/*
 * World Clock: the time in other towns, on Monet's glass. Each town has a
 * little clock face, paper by day and smoke by night, its name (in your
 * language), how far ahead or behind it is, and its time. The towns are
 * chosen in the widget's settings. KDE's own clocks keep the time, so summer
 * time comes and goes by itself.
 */
import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes
import QtQuick.Templates as T
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import org.kde.plasma.clock
import org.kde.plasma.private.digitalclock

PlasmoidItem {
    id: root
    ClockFormat { id: clockFormat }

    readonly property var zones: Array.from(Plasmoid.configuration.zones || [])

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "preferences-system-time"
    preferredRepresentation: fullRepresentation

    // This PC's own time, to say how far each town is from it.
    Clock {
        id: here
    }

    // Days apart, as the calendar counts them: -1, 0 or 1.
    function daysApart(there, local) {
        return Math.round((new Date(there.getFullYear(), there.getMonth(), there.getDate())
                           - new Date(local.getFullYear(), local.getMonth(), local.getDate())) / 86400000);
    }

    // "Tomorrow · +8 h" and the like: the day if it's another, and the hours between.
    function apart(there, local) {
        const minutes = Math.round((there - local) / 60000 / 15) * 15;
        const days = daysApart(there, local);
        const day = days > 0 ? i18nc("in that town it's already", "Tomorrow")
                  : days < 0 ? i18nc("in that town it's still", "Yesterday") : i18nc("in that town it's", "Today");
        if (minutes === 0) {
            return i18nc("a town on the same time as this PC", "Same time");
        }
        const hours = Math.abs(minutes) / 60;
        const amount = Number.isInteger(hours) ? String(hours) : Qt.locale().toString(hours, "f", 1);
        const gap = minutes > 0 ? i18nc("hours ahead of this PC", "+%1 h", amount) : i18nc("hours behind this PC", "−%1 h", amount);
        return day + "  ·  " + gap;
    }

    // A little clock face: paper by day, smoke by night, its hands at the town's time.
    component Face: Item {
        id: face
        property date time
        readonly property bool night: time.getHours() < 6 || time.getHours() >= 20
        readonly property real minuteAngle: time.getMinutes() * 6
        readonly property real hourAngle: (time.getHours() % 12) * 30 + time.getMinutes() / 2
        implicitWidth: 34
        implicitHeight: 34

        Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: face.night ? "#2C2B29" : "#FBFAF7"
            border.width: 1
            border.color: face.night ? Qt.rgba(1, 1, 1, 0.14) : Qt.rgba(0, 0, 0, 0.12)
        }
        // The sun by day, a pale moon by night, at the top of the face.
        Rectangle {
            x: parent.width / 2 - width / 2
            y: 5
            width: 5
            height: 5
            radius: 2.5
            color: face.night ? "#C9C2B6" : "#F2552C"
        }
        Rectangle {
            x: parent.width / 2 - width / 2
            y: parent.height / 2 - height + 1.5
            width: 2.4
            height: parent.height * 0.27
            radius: 1.2
            antialiasing: true
            color: face.night ? "#EFECE6" : "#1C1B19"
            transform: Rotation { origin.x: 1.2; origin.y: face.height * 0.27 - 1.5; angle: face.hourAngle }
        }
        Rectangle {
            x: parent.width / 2 - width / 2
            y: parent.height / 2 - height + 1.5
            width: 1.6
            height: parent.height * 0.38
            radius: 0.8
            antialiasing: true
            color: face.night ? "#EFECE6" : "#1C1B19"
            transform: Rotation { origin.x: 0.8; origin.y: face.height * 0.38 - 1.5; angle: face.minuteAngle }
        }
        Rectangle {
            anchors.centerIn: parent
            width: 4
            height: 4
            radius: 2
            color: "#F2552C"
        }
    }

    fullRepresentation: Item {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 12
        Layout.minimumHeight: Kirigami.Units.gridUnit * 5
        Layout.preferredWidth: Kirigami.Units.gridUnit * 16
        Layout.preferredHeight: Kirigami.Units.gridUnit * 10

        Glass {
            id: card
            anchors.fill: parent

            ColumnLayout {
                anchors.fill: parent
                anchors.leftMargin: Kirigami.Units.gridUnit
                anchors.rightMargin: Kirigami.Units.gridUnit
                anchors.topMargin: Math.round(Kirigami.Units.gridUnit * 0.8)
                anchors.bottomMargin: Math.round(Kirigami.Units.gridUnit * 0.8)
                spacing: 0
                visible: root.zones.length > 0

                Repeater {
                    model: root.zones

                    RowLayout {
                        id: town
                        required property string modelData
                        required property int index
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: Kirigami.Units.gridUnit * 0.7

                        Clock {
                            id: clock
                            timeZone: town.modelData
                        }

                        Face {
                            time: clock.dateTime
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                text: TimeZonesI18n.i18nCity(town.modelData)
                                color: card.ink
                                elide: Text.ElideRight
                                font.family: "Inter"
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                            }
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                text: root.apart(clock.dateTime, here.dateTime)
                                color: card.dim
                                elide: Text.ElideRight
                                font.family: "Inter"
                                font.pixelSize: 11
                            }
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            text: clockFormat.time(clock.dateTime)
                            color: card.ink
                            font.family: "Fraunces 72pt SuperSoft"
                            font.pixelSize: 24
                            font.features: { "tnum": 1 }
                        }
                    }
                }
            }

            // Another town: a pebble in the corner while the card is pointed at.
            HoverHandler {
                id: pointing
            }
            T.AbstractButton {
                id: more
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                // Below the last town's time, not over it.
                anchors.rightMargin: 6
                anchors.bottomMargin: 3
                width: 24
                height: 24
                visible: root.zones.length > 0
                opacity: pointing.hovered || more.visualFocus ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: 160 } }
                text: i18n("Add a town")
                Accessible.name: text
                onClicked: Plasmoid.internalAction("configure").trigger()
                background: Rectangle {
                    radius: width / 2
                    color: card.ink
                    opacity: more.down ? 0.2 : more.hovered ? 0.14 : 0.08
                }
                contentItem: Text {
                    text: "+"
                    color: card.ink
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.family: "Inter"
                    font.pixelSize: 16
                }
                PlasmaCore.ToolTipArea {
                    anchors.fill: parent
                    mainText: more.text
                }
            }

            // No towns yet.
            ColumnLayout {
                anchors.centerIn: parent
                width: parent.width - Kirigami.Units.gridUnit * 2
                visible: root.zones.length === 0
                spacing: Kirigami.Units.smallSpacing * 2

                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: i18n("What time is it elsewhere?")
                    color: card.ink
                    font.family: "Fraunces 72pt SuperSoft"
                    font.italic: true
                    font.pixelSize: 17
                }
                T.AbstractButton {
                    id: add
                    Layout.alignment: Qt.AlignHCenter
                    text: i18n("Add a town")
                    implicitWidth: addLabel.implicitWidth + 28
                    implicitHeight: 30
                    onClicked: Plasmoid.internalAction("configure").trigger()
                    background: Rectangle {
                        radius: height / 2
                        color: card.ink
                        opacity: add.down ? 0.16 : add.hovered ? 0.12 : 0.08
                    }
                    contentItem: Text {
                        id: addLabel
                        text: add.text
                        color: card.ink
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.family: "Inter"
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                    }
                }
            }
        }
    }
}
