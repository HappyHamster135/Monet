/*
 * Weather: the sky where you are, on Monet's glass. Today's temperature in
 * Fraunces with the sky painted beside it, and the next four days beneath.
 * From Open-Meteo (no account, nothing sent but the place), every half hour,
 * once a place is chosen: right on the card (or in the widget's settings).
 */
import QtQuick
import QtQuick.Layouts
import QtQuick.Templates as T
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    readonly property bool placed: Plasmoid.configuration.place !== ""
    readonly property bool fahrenheit: Plasmoid.configuration.fahrenheit
    property var weather: null
    property string problem: ""

    // Choosing the place on the card: a town, then one of Open-Meteo's matches.
    property bool choosing: false
    property var found: []
    property bool searching: false
    property int lookup: 0

    function search(name) {
        name = name.trim();
        const mine = ++lookup;
        if (name.length < 2) {
            found = [];
            searching = false;
            return;
        }
        searching = true;
        const request = new XMLHttpRequest();
        request.onreadystatechange = () => {
            // Only the answer to the latest letters counts.
            if (request.readyState !== XMLHttpRequest.DONE || mine !== lookup) {
                return;
            }
            searching = false;
            try {
                found = JSON.parse(request.responseText).results || [];
            } catch (e) {
                found = [];
            }
        };
        request.open("GET", "https://geocoding-api.open-meteo.com/v1/search?count=3&format=json&name="
                     + encodeURIComponent(name) + "&language=" + Qt.locale().name.split("_")[0]);
        request.send();
    }

    function choose(place) {
        if (!placed) {
            // The first place: degrees the way this PC's region counts them.
            Plasmoid.configuration.fahrenheit = Qt.locale().measurementSystem === Locale.ImperialUSSystem;
        }
        Plasmoid.configuration.place = place.name;
        Plasmoid.configuration.latitude = place.latitude;
        Plasmoid.configuration.longitude = place.longitude;
        found = [];
        choosing = false;
    }

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
    Plasmoid.icon: "monet-weather"
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
            readonly property bool asking: root.choosing || !root.placed
            readonly property color lily: smoke ? "#4DB4A0" : "#357F72"

            ColumnLayout {
                anchors.fill: parent
                anchors.leftMargin: Kirigami.Units.gridUnit
                anchors.rightMargin: Kirigami.Units.gridUnit
                // A little less above and below, so the forecast has room under today.
                anchors.topMargin: Math.round(Kirigami.Units.gridUnit * 0.8)
                anchors.bottomMargin: Math.round(Kirigami.Units.gridUnit * 0.7)
                spacing: 0
                visible: card.now !== null && !card.asking

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
                            font.underline: placeArea.containsMouse

                            // Another place: click its name.
                            MouseArea {
                                id: placeArea
                                width: Math.min(parent.width, parent.implicitWidth)
                                height: parent.height
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.choosing = true
                            }
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
                                size: Kirigami.Units.gridUnit * 1.35
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

            // No weather yet.
            ColumnLayout {
                anchors.centerIn: parent
                width: parent.width - Kirigami.Units.gridUnit * 2
                visible: card.now === null && !card.asking
                spacing: Kirigami.Units.smallSpacing

                Sky {
                    Layout.alignment: Qt.AlignHCenter
                    size: Kirigami.Units.gridUnit * 3
                }
                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: root.problem || i18n("Looking at the sky…")
                    color: card.ink
                    font.family: "Fraunces 72pt SuperSoft"
                    font.italic: true
                    font.pixelSize: 17
                }
            }

            // The place, chosen right here: a town, then one of the matches.
            ColumnLayout {
                anchors.fill: parent
                anchors.leftMargin: Kirigami.Units.gridUnit
                anchors.rightMargin: Kirigami.Units.gridUnit
                anchors.topMargin: Math.round(Kirigami.Units.gridUnit * 0.8)
                anchors.bottomMargin: Math.round(Kirigami.Units.gridUnit * 0.7)
                visible: card.asking
                spacing: Kirigami.Units.smallSpacing

                onVisibleChanged: {
                    field.text = "";
                    root.found = [];
                    if (visible && root.choosing) {
                        field.forceActiveFocus();
                    }
                }

                RowLayout {
                    Layout.fillWidth: true

                    Text {
                        Layout.fillWidth: true
                        text: root.placed ? i18n("Another place?") : i18n("Where are you?")
                        color: card.ink
                        elide: Text.ElideRight
                        font.family: "Fraunces 72pt SuperSoft"
                        font.italic: true
                        font.pixelSize: 17
                    }
                    T.AbstractButton {
                        id: cancel
                        visible: root.placed
                        text: i18n("Cancel")
                        implicitWidth: cancelLabel.implicitWidth + 18
                        implicitHeight: 24
                        onClicked: root.choosing = false
                        background: Rectangle {
                            radius: height / 2
                            color: card.ink
                            opacity: cancel.hovered ? 0.08 : 0
                        }
                        contentItem: Text {
                            id: cancelLabel
                            text: cancel.text
                            color: card.dim
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            font.family: "Inter"
                            font.pixelSize: 12
                        }
                    }
                }

                T.TextField {
                    id: field
                    Layout.fillWidth: true
                    implicitHeight: 32
                    leftPadding: 12
                    rightPadding: 12
                    verticalAlignment: TextInput.AlignVCenter
                    color: card.ink
                    placeholderText: i18n("A town or a city")
                    selectionColor: Kirigami.Theme.highlightColor
                    selectedTextColor: Kirigami.Theme.highlightedTextColor
                    font.family: "Inter"
                    font.pixelSize: 13
                    Accessible.name: i18n("Find a place for the weather")
                    onTextChanged: typing.restart()
                    Keys.onReturnPressed: field.takeFirst()
                    Keys.onEnterPressed: field.takeFirst()
                    Keys.onEscapePressed: root.choosing = false

                    // Enter takes the first match, once the matches are for what's typed.
                    function takeFirst() {
                        if (typing.running) {
                            typing.stop();
                            root.search(text);
                        } else if (root.found.length > 0) {
                            root.choose(root.found[0]);
                        }
                    }

                    background: Rectangle {
                        radius: height / 2
                        color: Qt.rgba(card.ink.r, card.ink.g, card.ink.b, 0.07)
                        border.width: field.activeFocus ? 2 : 1
                        border.color: field.activeFocus ? card.lily : Qt.rgba(card.ink.r, card.ink.g, card.ink.b, 0.12)
                    }
                    // Templates draw no placeholder.
                    Text {
                        anchors.fill: parent
                        leftPadding: field.leftPadding
                        rightPadding: field.rightPadding
                        verticalAlignment: Text.AlignVCenter
                        visible: field.length === 0 && field.preeditText === ""
                        text: field.placeholderText
                        color: card.dim
                        elide: Text.ElideRight
                        font: field.font
                    }
                    Timer {
                        id: typing
                        interval: 350
                        onTriggered: root.search(field.text)
                    }
                }

                Column {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true

                    Repeater {
                        model: root.found.slice(0, 3)
                        T.AbstractButton {
                            id: match
                            required property var modelData
                            readonly property string where: [modelData.admin1, modelData.country].filter(p => p).join(", ")
                            width: parent.width
                            implicitHeight: 26
                            Accessible.name: [modelData.name, where].filter(p => p).join(", ")
                            onClicked: root.choose(modelData)
                            background: Rectangle {
                                radius: 8
                                color: card.ink
                                opacity: match.hovered || match.visualFocus ? 0.08 : 0
                            }
                            contentItem: RowLayout {
                                spacing: 6
                                Text {
                                    Layout.leftMargin: 8
                                    text: match.modelData.name
                                    textFormat: Text.PlainText
                                    color: card.ink
                                    font.family: "Inter"
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    Layout.fillWidth: true
                                    Layout.rightMargin: 8
                                    text: match.where
                                    textFormat: Text.PlainText
                                    color: card.dim
                                    elide: Text.ElideRight
                                    font.family: "Inter"
                                    font.pixelSize: 12
                                }
                            }
                        }
                    }
                    Text {
                        width: parent.width
                        visible: root.found.length === 0 && field.text.trim().length >= 2 && !root.searching && !typing.running
                        leftPadding: 8
                        topPadding: 4
                        text: i18n("No place by that name.")
                        color: card.dim
                        font.family: "Inter"
                        font.pixelSize: 12
                    }
                }
                // At the foot, while the matches don't need the room.
                Text {
                    Layout.fillWidth: true
                    visible: root.found.length === 0
                    elide: Text.ElideRight
                    text: i18n("Only the place is sent, to Open-Meteo.")
                    color: card.dim
                    font.family: "Inter"
                    font.pixelSize: 11
                }
            }
        }
    }
}
