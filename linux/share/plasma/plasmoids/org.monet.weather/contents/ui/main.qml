/*
 * Weather: the sky where you are, on Monet's glass. Today's temperature in
 * Fraunces with the sky painted beside it, and the next four days beneath.
 * From Open-Meteo (no account, nothing sent but the place), every half hour,
 * once a place is chosen: right on the card (or in the widget's settings).
 * More places, in other towns or countries, are added the same way; the
 * arrows beside the name go through them.
 */
import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes
import QtQuick.Templates as T
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    readonly property bool placed: Plasmoid.configuration.place !== ""
    readonly property bool fahrenheit: Plasmoid.configuration.fahrenheit
    // The place shown, and every place in the order the arrows go (the one shown
    // is always among them, as it is when there was only ever one).
    readonly property var here: ({name: Plasmoid.configuration.place, latitude: Plasmoid.configuration.latitude,
                                   longitude: Plasmoid.configuration.longitude})
    readonly property var places: {
        const list = Array.from(Plasmoid.configuration.places || []).map(text => {
            try {
                return JSON.parse(text);
            } catch (e) {
                return null;
            }
        }).filter(place => place && place.name);
        return placed && !list.some(place => same(place, here)) ? list.concat([here]) : list;
    }
    readonly property int at: places.findIndex(place => same(place, here))
    // The last weather of each place, so going back to one shows it at once.
    property var weathers: ({})
    readonly property string key: here.latitude + "," + here.longitude
    readonly property var weather: weathers[key] || null
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

    function same(a, b) {
        return Math.abs(a.latitude - b.latitude) < 0.0001 && Math.abs(a.longitude - b.longitude) < 0.0001;
    }

    function show(place) {
        Plasmoid.configuration.place = place.name;
        Plasmoid.configuration.latitude = place.latitude;
        Plasmoid.configuration.longitude = place.longitude;
    }

    function keep(list) {
        Plasmoid.configuration.places = list.map(place => JSON.stringify(
            {name: place.name, latitude: place.latitude, longitude: place.longitude}));
    }

    // A place from the search: added after the others, and shown.
    function choose(place) {
        if (!placed) {
            // The first place: degrees the way this PC's region counts them.
            Plasmoid.configuration.fahrenheit = Qt.locale().measurementSystem === Locale.ImperialUSSystem;
        }
        if (!places.some(known => same(known, place))) {
            keep(places.concat([place]));
        }
        show(place);
        found = [];
        choosing = false;
    }

    // The next place (1) or the one before (-1), round and round.
    function step(by) {
        if (places.length > 1) {
            show(places[(Math.max(at, 0) + by + places.length) % places.length]);
        }
    }

    // The place shown leaves the list; its neighbour is shown, or none is.
    function forget() {
        const rest = places.filter((place, i) => i !== at);
        keep(rest);
        if (rest.length > 0) {
            show(rest[Math.min(Math.max(at, 0), rest.length - 1)]);
        } else {
            Plasmoid.configuration.place = "";
        }
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
        // The answer belongs to the place asked about, even if another is shown by then.
        const wanted = key;
        const request = new XMLHttpRequest();
        request.onreadystatechange = () => {
            if (request.readyState !== XMLHttpRequest.DONE) {
                return;
            }
            try {
                if (request.status !== 200) {
                    throw new Error(String(request.status));
                }
                const answer = JSON.parse(request.responseText);
                const all = Object.assign({}, weathers);
                all[wanted] = answer;
                weathers = all;
                problem = "";
            } catch (e) {
                // Keep the last weather; say why only when there's none.
                problem = i18n("The weather can't be reached right now. Click to try again.");
            }
        };
        request.open("GET", url);
        request.send();
    }

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "monet-weather"
    preferredRepresentation: fullRepresentation
    toolTipMainText: Plasmoid.configuration.place || i18n("Weather")

    Plasmoid.contextualActions: [
        PlasmaCore.Action {
            text: i18n("Add a place…")
            icon.name: "list-add"
            onTriggered: root.choosing = true
        },
        PlasmaCore.Action {
            text: i18nc("%1 is a town", "Forget %1", Plasmoid.configuration.place)
            icon.name: "list-remove"
            visible: root.placed
            onTriggered: root.forget()
        }
    ]

    // Beside the place's name, to the place before or after it.
    component Arrow: T.AbstractButton {
        id: arrow
        property bool back: false
        property color ink
        property color dim
        readonly property bool pointsLeft: back !== LayoutMirroring.enabled
        implicitWidth: 22
        implicitHeight: 22
        Accessible.name: back ? i18n("Place before") : i18n("Next place")
        background: Rectangle {
            radius: height / 2
            color: arrow.ink
            opacity: arrow.down ? 0.14 : arrow.hovered || arrow.visualFocus ? 0.08 : 0
        }
        contentItem: Shape {
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: arrow.hovered ? arrow.ink : arrow.dim
                strokeWidth: 1.7
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                PathPolyline {
                    path: arrow.pointsLeft ? [Qt.point(13, 6.5), Qt.point(8.5, 11), Qt.point(13, 15.5)]
                                           : [Qt.point(9, 6.5), Qt.point(13.5, 11), Qt.point(9, 15.5)]
                }
            }
        }
    }

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

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                Layout.maximumWidth: implicitWidth
                                text: Plasmoid.configuration.place
                                color: card.ink
                                elide: Text.ElideRight
                                font.family: "Inter"
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                                font.underline: placeArea.containsMouse

                                // Another place: click its name.
                                PlasmaCore.ToolTipArea {
                                    width: Math.min(parent.width, parent.implicitWidth)
                                    height: parent.height
                                    mainText: i18n("Add a place")
                                    MouseArea {
                                        id: placeArea
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.choosing = true
                                    }
                                }
                            }
                            // Taller than the name, without making its line taller.
                            Arrow {
                                Layout.leftMargin: 4
                                Layout.topMargin: -3
                                Layout.bottomMargin: -3
                                visible: root.places.length > 1
                                back: true
                                ink: card.ink
                                dim: card.dim
                                onClicked: root.step(-1)
                            }
                            Arrow {
                                Layout.topMargin: -3
                                Layout.bottomMargin: -3
                                visible: root.places.length > 1
                                ink: card.ink
                                dim: card.dim
                                onClicked: root.step(1)
                            }
                            Item { Layout.fillWidth: true }
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            text: card.now ? Math.round(card.now.temperature_2m) + "°" : ""
                            color: card.ink
                            font.family: "Fraunces 72pt SuperSoft"
                            font.weight: Font.Light
                            font.pixelSize: 50
                            Layout.topMargin: -4
                            Layout.bottomMargin: -6
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
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
                                horizontalAlignment: Text.AlignLeft
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
                                horizontalAlignment: Text.AlignLeft
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
                // Out of reach: a click tries again now, not in half an hour.
                TapHandler {
                    enabled: root.problem !== ""
                    onTapped: {
                        root.problem = "";
                        root.refresh();
                    }
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
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        text: root.placed ? i18n("Add a place") : i18n("Where are you?")
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

                    // A pebble of lighter glass with light in its rim.
                    background: Rectangle {
                        readonly property bool dark: card.ink.hslLightness > 0.5
                        radius: height / 2
                        color: dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.34)
                        border.width: field.activeFocus ? 2 : 1
                        border.color: field.activeFocus ? card.lily : dark ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(1, 1, 1, 0.75)
                    }
                    // Templates draw no placeholder.
                    Text {
                        horizontalAlignment: Text.AlignLeft
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
                                    horizontalAlignment: Text.AlignLeft
                                    Layout.leftMargin: 8
                                    text: match.modelData.name
                                    textFormat: Text.PlainText
                                    color: card.ink
                                    font.family: "Inter"
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    horizontalAlignment: Text.AlignLeft
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
                        horizontalAlignment: Text.AlignLeft
                        width: parent.width
                        visible: root.found.length === 0 && field.text.trim().length >= 2 && !root.searching && !typing.running
                        leftPadding: 8
                        topPadding: 4
                        text: i18n("No place by that name.")
                        color: card.dim
                        font.family: "Inter"
                        font.pixelSize: 12
                    }
                    // The place on the card, taken off it (the one before or after shows).
                    T.AbstractButton {
                        id: forgetPlace
                        visible: root.placed && field.text.trim().length === 0
                        text: i18nc("%1 is a town", "Forget %1", Plasmoid.configuration.place)
                        implicitWidth: Math.min(parent.width, forgetLabel.implicitWidth + 18)
                        implicitHeight: 26
                        onClicked: {
                            root.forget();
                            root.choosing = false;
                        }
                        background: Rectangle {
                            radius: height / 2
                            color: card.ink
                            opacity: forgetPlace.hovered || forgetPlace.visualFocus ? 0.08 : 0
                        }
                        contentItem: Text {
                            id: forgetLabel
                            text: forgetPlace.text
                            color: card.dim
                            elide: Text.ElideRight
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            font.family: "Inter"
                            font.pixelSize: 12
                        }
                    }
                }
                // At the foot, while the matches don't need the room.
                Text {
                    horizontalAlignment: Text.AlignLeft
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
