/*
 * Weather: the sky where you are, on Monet's glass. Today's temperature in
 * Fraunces with the sky painted beside it, and the next four days beneath.
 * From Open-Meteo (no account, nothing sent but the place), every half hour,
 * once a place is chosen in the widget's settings.
 */
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    readonly property bool placed: Plasmoid.configuration.place !== ""
    readonly property bool fahrenheit: Plasmoid.configuration.fahrenheit
    property var weather: null
    property string problem: ""

    function words(code) {
        return code === 0 ? i18n("Clear") : code === 1 ? i18n("Mostly clear") : code === 2 ? i18n("Partly cloudy")
            : code === 3 ? i18n("Overcast") : code === 45 || code === 48 ? i18n("Fog")
            : code >= 51 && code <= 57 ? i18n("Drizzle") : code >= 61 && code <= 67 ? i18n("Rain")
            : code >= 71 && code <= 77 ? i18n("Snow") : code >= 80 && code <= 82 ? i18n("Showers")
            : code === 85 || code === 86 ? i18n("Snow showers") : code >= 95 ? i18n("Thunderstorm") : ""
    }

    function refresh() {
        if (!placed) {
            return;
        }
        const url = "https://api.open-meteo.com/v1/forecast?latitude=" + Plasmoid.configuration.latitude
            + "&longitude=" + Plasmoid.configuration.longitude
            + "&current=temperature_2m,weather_code,is_day"
            + "&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=5"
            + (fahrenheit ? "&temperature_unit=fahrenheit" : "");
        const request = new XMLHttpRequest();
        request.onreadystatechange = () => {
            if (request.readyState !== XMLHttpRequest.DONE) {
                return;
            }
            try {
                if (request.status !== 200) {
                    throw new Error(String(request.status));
                }
                weather = JSON.parse(request.responseText);
                problem = "";
            } catch (e) {
                // Keep the last weather; say why only when there's none.
                problem = i18n("The weather can't be reached right now.");
            }
        };
        request.open("GET", url);
        request.send();
    }

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "monet"
    preferredRepresentation: fullRepresentation
    toolTipMainText: Plasmoid.configuration.place || i18n("Weather")

    // A new place or other degrees: look again.
    readonly property string asked: [Plasmoid.configuration.place, Plasmoid.configuration.latitude,
                                     Plasmoid.configuration.longitude, fahrenheit].join("|")
    onAskedChanged: refresh()

    Timer {
        interval: 30 * 60 * 1000
        running: root.placed
        repeat: true
        triggeredOnStart: true
        onTriggered: root.refresh()
    }

    fullRepresentation: Item {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 14
        Layout.minimumHeight: Kirigami.Units.gridUnit * 8
        Layout.preferredWidth: Kirigami.Units.gridUnit * 19
        Layout.preferredHeight: Kirigami.Units.gridUnit * 10

        Glass {
            id: card
            anchors.fill: parent

            readonly property var now: root.weather ? root.weather.current : null
            readonly property var days: root.weather ? root.weather.daily : null

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Kirigami.Units.gridUnit
                spacing: 0
                visible: card.now !== null

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0

                        Text {
                            Layout.fillWidth: true
                            text: Plasmoid.configuration.place
                            color: card.ink
                            elide: Text.ElideRight
                            font.family: "Inter"
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }
                        Text {
                            text: card.now ? Math.round(card.now.temperature_2m) + "°" : ""
                            color: card.ink
                            font.family: "Fraunces 72pt SuperSoft"
                            font.weight: Font.Light
                            font.pixelSize: 50
                            Layout.topMargin: -4
                            Layout.bottomMargin: -6
                        }
                        Text {
                            Layout.fillWidth: true
                            text: card.now && card.days
                                ? root.words(card.now.weather_code) + "  ·  "
                                  + i18nc("today's highest and lowest temperature", "H %1°  L %2°",
                                          Math.round(card.days.temperature_2m_max[0]), Math.round(card.days.temperature_2m_min[0]))
                                : ""
                            color: card.dim
                            elide: Text.ElideRight
                            font.family: "Inter"
                            font.pixelSize: 12
                        }
                    }

                    Sky {
                        Layout.alignment: Qt.AlignTop
                        size: Kirigami.Units.gridUnit * 4
                        code: card.now ? card.now.weather_code : 0
                        day: card.now ? card.now.is_day === 1 : true
                    }
                }

                Item { Layout.fillHeight: true }

                // The next four days, a quarter of the card each.
                Row {
                    id: forecast
                    Layout.fillWidth: true
                    Repeater {
                        model: card.days ? 4 : 0
                        Column {
                            required property int index
                            readonly property int day: index + 1
                            width: forecast.width / 4
                            spacing: 2
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: Qt.locale().dayName(new Date(card.days.time[parent.day] + "T12:00").getDay(), Locale.ShortFormat)
                                color: card.dim
                                font.family: "Inter"
                                font.pixelSize: 11
                            }
                            Sky {
                                anchors.horizontalCenter: parent.horizontalCenter
                                size: Kirigami.Units.gridUnit * 1.6
                                code: card.days.weather_code[parent.day]
                            }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: Math.round(card.days.temperature_2m_max[parent.day]) + "°"
                                color: card.ink
                                font.family: "Inter"
                                font.pixelSize: 12
                                font.weight: Font.Medium
                            }
                        }
                    }
                }
            }

            // No place yet, or no weather yet.
            ColumnLayout {
                anchors.centerIn: parent
                width: parent.width - Kirigami.Units.gridUnit * 2
                visible: card.now === null
                spacing: Kirigami.Units.smallSpacing

                Sky {
                    Layout.alignment: Qt.AlignHCenter
                    size: Kirigami.Units.gridUnit * 3
                }
                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: !root.placed ? i18n("Choose a place for the weather.") : (root.problem || i18n("Looking at the sky…"))
                    color: card.ink
                    font.family: "Fraunces 72pt SuperSoft"
                    font.italic: true
                    font.pixelSize: 17
                }
            }

            MouseArea {
                anchors.fill: parent
                enabled: !root.placed
                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: Plasmoid.internalAction("configure").trigger()
            }
        }
    }
}
