/*
 * Weather: the sky where you are, on Monet's glass. Today's temperature in
 * Fraunces with the sky painted beside it, and the next four days beneath.
 * From Open-Meteo (no account, nothing sent but the place), every half hour,
 * once a place is chosen: right on the card (or in the widget's settings).
 * More places, in other towns or countries, are added the same way; the
 * arrows beside the name go through them.
 */
import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import QtQuick.Shapes
import QtQuick.Templates as T
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    readonly property bool inPanel: Plasmoid.formFactor === PlasmaCore.Types.Horizontal
        || Plasmoid.formFactor === PlasmaCore.Types.Vertical
    readonly property var preferences: shared.config
    readonly property bool placed: preferences.place !== ""
    readonly property bool fahrenheit: preferences.fahrenheit
    readonly property var here: ({name: preferences.place, latitude: preferences.latitude, longitude: preferences.longitude})
    readonly property var places: preferences.places || []
    readonly property int at: places.findIndex(place => same(place, here))
    readonly property var weather: shared.weather
    readonly property string problem: shared.problem

    WeatherStore {
        id: shared
        Component.onCompleted: seed({place: Plasmoid.configuration.place,
            latitude: Plasmoid.configuration.latitude, longitude: Plasmoid.configuration.longitude,
            places: Array.from(Plasmoid.configuration.places || []), fahrenheit: Plasmoid.configuration.fahrenheit})
    }

    // Choosing the place on the card: a town, then one of Open-Meteo's matches.
    property bool choosing: false
    PlaceSearch { id: placeSearch }
    property alias found: placeSearch.results
    readonly property bool searching: placeSearch.busy
    function search(name) { placeSearch.find(name) }

    function same(a, b) {
        return Math.abs(a.latitude - b.latitude) < 0.0001 && Math.abs(a.longitude - b.longitude) < 0.0001;
    }

    function show(place) {
        shared.write({place: place.name, latitude: place.latitude, longitude: place.longitude});
    }
    function choose(place) {
        const list = places.some(known => same(known, place)) ? places : places.concat([place]);
        shared.write({place: place.name, latitude: place.latitude, longitude: place.longitude,
            places: list.map(p => ({name: p.name, latitude: p.latitude, longitude: p.longitude})),
            fahrenheit: placed ? fahrenheit : Qt.locale().measurementSystem === Locale.ImperialUSSystem});
        found = [];
        choosing = false;
    }
    function step(by) {
        if (places.length > 1) show(places[(Math.max(at, 0) + by + places.length) % places.length]);
    }
    function forget() {
        const rest = places.filter((place, i) => i !== at);
        const next = rest.length ? rest[Math.min(Math.max(at, 0), rest.length - 1)] : {name: "", latitude: 0, longitude: 0};
        shared.write({place: next.name, latitude: next.latitude, longitude: next.longitude, places: rest});
    }
    function refresh() { shared.retry(); }
    function openDetails() {
        shared.refresh();
        if (inPanel) expanded = true;
        else detailsPopup.visible = true;
    }

    function words(code) {
        return code === 0 ? i18n("Clear") : code === 1 ? i18n("Mostly clear") : code === 2 ? i18n("Partly cloudy")
            : code === 3 ? i18n("Overcast") : code === 45 || code === 48 ? i18n("Fog")
            : code >= 51 && code <= 57 ? i18n("Drizzle") : code >= 61 && code <= 67 ? i18n("Rain")
            : code >= 71 && code <= 77 ? i18n("Snow") : code >= 80 && code <= 82 ? i18n("Showers")
            : code === 85 || code === 86 ? i18n("Snow showers") : code >= 95 ? i18n("Thunderstorm") : ""
    }

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "monet-weather"
    preferredRepresentation: inPanel ? compactRepresentation : fullRepresentation
    toolTipMainText: preferences.place || i18n("Weather")
    toolTipSubText: weather ? Math.round(weather.current.temperature_2m) + (fahrenheit ? "°F" : "°C")
        + " · " + words(weather.current.weather_code) : i18n("Choose a place")
    onExpandedChanged: if (root.expanded) shared.refresh()

    compactRepresentation: T.AbstractButton {
        id: weatherButton
        activeFocusOnTab: true
        hoverEnabled: true
        // The panel's themed active highlight is inset eight pixels horizontally.
        // Leave another eight around the contents inside that highlight.
        leftPadding: 16
        rightPadding: 16
        topPadding: 3
        bottomPadding: 3
        Layout.minimumWidth: panelContents.implicitWidth + leftPadding + rightPadding
        Layout.preferredWidth: Layout.minimumWidth
        Accessible.name: i18n("Weather") + ", " + root.toolTipMainText + ", " + root.toolTipSubText
        onClicked: root.expanded = !root.expanded
        background: Rectangle {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            radius: 10
            // Plasma supplies the expanded highlight; don't paint a second one.
            color: weatherButton.hovered && !root.expanded ? Qt.rgba(0.5, 0.5, 0.5, 0.12) : "transparent"
            border.width: weatherButton.visualFocus ? 2 : 0
            border.color: Kirigami.Theme.highlightColor
        }
        // Control owns this item's padded geometry; center the natural-sized row
        // inside it so the icon and temperature share the whole highlighted area.
        contentItem: Item {
            implicitWidth: panelContents.implicitWidth
            implicitHeight: panelContents.implicitHeight
            Row {
                id: panelContents
                spacing: 4
                anchors.centerIn: parent
                Sky {
                    anchors.verticalCenter: parent.verticalCenter
                    size: 26
                    code: root.weather ? root.weather.current.weather_code : 2
                    day: root.weather ? root.weather.current.is_day === 1 : true
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.weather ? Math.round(root.weather.current.temperature_2m) + "°" : ""
                    font.family: "Inter"; font.pixelSize: 13; font.weight: Font.Medium
                    color: Kirigami.Theme.textColor
                }
            }
        }
    }

    Plasmoid.contextualActions: [
        PlasmaCore.Action {
            text: i18n("Add a place…")
            icon.name: "list-add"
            onTriggered: { root.choosing = true; if (root.inPanel) root.expanded = true; }
        },
        PlasmaCore.Action {
            text: i18nc("%1 is a town", "Forget %1", preferences.place)
            icon.name: "list-remove"
            visible: root.placed
            onTriggered: root.forget()
        },
        PlasmaCore.Action {
            text: root.fahrenheit ? i18n("Use Celsius") : i18n("Use Fahrenheit")
            icon.name: "monet-weather"
            onTriggered: shared.write({fahrenheit: !root.fahrenheit})
        },
        PlasmaCore.Action {
            text: i18n("Refresh weather")
            icon.name: "view-refresh"
            onTriggered: shared.retry()
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

    fullRepresentation: Loader {
        id: representation
        readonly property bool details: root.inPanel && root.placed && !root.choosing
        Layout.minimumWidth: Math.min(Kirigami.Units.gridUnit * (details ? 30 : 14), Screen.width - 48)
        Layout.minimumHeight: Math.min(Kirigami.Units.gridUnit * (details ? 38 : 10), Screen.height - 112)
        Layout.preferredWidth: Math.min(Kirigami.Units.gridUnit * (details ? 30 : 19), Screen.width - 48)
        Layout.preferredHeight: Math.min(Kirigami.Units.gridUnit * (details ? 38 : 10), Screen.height - 112)
        Layout.maximumWidth: root.inPanel ? Layout.preferredWidth : Infinity
        Layout.maximumHeight: root.inPanel ? Layout.preferredHeight : Infinity
        sourceComponent: details ? forecastComponent : summaryComponent
        onLoaded: if (details && item && root.expanded) item.opened()
        Connections {
            target: root
            function onExpandedChanged() {
                if (root.expanded && representation.details && representation.item) representation.item.opened();
            }
        }
    }

    Component {
        id: forecastComponent
        WeatherDetails {
            store: shared
            describe: root.words
            onClosed: root.expanded = false
            onPlacesRequested: root.choosing = true
        }
    }

    PlasmaCore.Dialog {
        id: detailsPopup
        location: PlasmaCore.Types.Floating
        hideOnWindowDeactivate: true
        transientParent: root.Window.window
        flags: Qt.Tool | Qt.WindowStaysOnTopHint
        function place() {
            const at = root.mapToGlobal(0, 0);
            const sx = root.Screen.virtualX, sy = root.Screen.virtualY;
            const sw = root.Screen.width, sh = root.Screen.height;
            const beside = at.x + root.width + 12;
            x = Math.round(Math.max(sx + 12, Math.min(sx + sw - width - 12,
                beside + width < sx + sw - 12 ? beside : at.x - width - 12)));
            y = Math.round(Math.max(sy + 12, Math.min(at.y, sy + sh - height - 80)));
        }
        onVisibleChanged: if (visible) Qt.callLater(function() { place(); requestActivate(); desktopDetails.opened(); })
        onWidthChanged: if (visible) Qt.callLater(place)
        onHeightChanged: if (visible) Qt.callLater(place)
        mainItem: WeatherDetails {
            id: desktopDetails
            width: Math.min(Kirigami.Units.gridUnit * 30, root.Screen.width - 48)
            height: Math.min(Kirigami.Units.gridUnit * 38, root.Screen.height - 112)
            store: shared
            describe: root.words
            onClosed: detailsPopup.visible = false
            onPlacesRequested: { detailsPopup.visible = false; root.choosing = true; }
        }
    }

    Component {
      id: summaryComponent
      Item {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 14
        Layout.minimumHeight: Kirigami.Units.gridUnit * 10
        Layout.preferredWidth: Kirigami.Units.gridUnit * 19
        Layout.preferredHeight: Kirigami.Units.gridUnit * 10
        Layout.maximumWidth: root.inPanel ? Kirigami.Units.gridUnit * 21 : Infinity
        Layout.maximumHeight: root.inPanel ? Kirigami.Units.gridUnit * 12 : Infinity

        Glass {
            id: card
            anchors.fill: parent
            drawBackground: !root.inPanel

            readonly property var now: root.weather ? root.weather.current : null
            readonly property var days: root.weather ? root.weather.daily : null
            readonly property bool asking: root.choosing || !root.placed
            readonly property color lily: smoke ? "#4DB4A0" : "#357F72"

            T.AbstractButton {
                anchors.fill: parent
                visible: !card.asking && !root.inPanel
                activeFocusOnTab: true
                Accessible.name: i18n("Open hourly and weekly weather for %1", root.preferences.place)
                onClicked: root.openDetails()
                background: Rectangle {
                    radius: card.radius
                    color: "transparent"
                    border.width: parent.visualFocus ? 2 : 0
                    border.color: card.lily
                }
            }

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
                                text: preferences.place
                                color: card.ink
                                elide: Text.ElideRight
                                font.family: "Inter"
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                                font.underline: placeArea.containsMouse || placeArea.activeFocus

                                // Another place: click its name.
                                PlasmaCore.ToolTipArea {
                                    width: Math.min(parent.width, parent.implicitWidth)
                                    height: parent.height
                                    mainText: i18n("Add a place")
                                    MouseArea {
                                        id: placeArea
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        activeFocusOnTab: true
                                        Accessible.role: Accessible.Button
                                        Accessible.name: i18n("Add a place")
                                        Accessible.onPressAction: root.choosing = true
                                        Keys.onReturnPressed: root.choosing = true
                                        Keys.onSpacePressed: root.choosing = true
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

                Text {
                    Layout.fillWidth: true
                    visible: shared.stale
                    text: i18n("Last update: %1", Qt.formatDateTime(new Date(shared.updated * 1000), "ddd HH:mm"))
                    color: card.dim; font.pixelSize: 10; elide: Text.ElideRight
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
                T.AbstractButton {
                    Layout.alignment: Qt.AlignHCenter
                    visible: root.problem !== ""
                    implicitWidth: 110; implicitHeight: 30
                    Accessible.name: i18n("Try again")
                    onClicked: root.refresh()
                    background: Rectangle { radius: 8; color: Qt.rgba(0.5, 0.5, 0.5, 0.15) }
                    contentItem: Text { text: i18n("Try again"); color: card.ink; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
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
                        Qt.callLater(() => field.forceActiveFocus());
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
                    onTextChanged: { placeSearch.cancel(); typing.restart() }
                    Keys.onReturnPressed: field.takeFirst()
                    Keys.onEnterPressed: field.takeFirst()
                    Keys.onEscapePressed: root.choosing = false
                    Connections {
                        target: field.Window.window
                        function onActiveChanged() {
                            if (field.Window.window.active && card.asking) field.forceActiveFocus();
                        }
                    }

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
                        text: placeSearch.problem || i18n("No place by that name.")
                        wrapMode: Text.Wrap
                        color: card.dim
                        font.family: "Inter"
                        font.pixelSize: 12
                    }
                    T.AbstractButton {
                        visible: placeSearch.problem !== "" && !root.searching
                        implicitHeight: 30
                        implicitWidth: parent.width
                        onClicked: root.search(field.text)
                        contentItem: Text { text: i18nd("monet", "Try again"); color: card.lily; verticalAlignment: Text.AlignVCenter }
                    }
                    // The place on the card, taken off it (the one before or after shows).
                    T.AbstractButton {
                        id: forgetPlace
                        visible: root.placed && field.text.trim().length === 0
                        text: i18nc("%1 is a town", "Forget %1", preferences.place)
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
}
