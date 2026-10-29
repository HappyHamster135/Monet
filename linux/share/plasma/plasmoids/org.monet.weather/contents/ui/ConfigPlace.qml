/*
 * Where the weather is for: every place the card goes through with its
 * arrows (type a town and pick it, from Open-Meteo's place search), and
 * degrees.
 */
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    id: page

    property string cfg_place
    property real cfg_latitude
    property real cfg_longitude
    property var cfg_places: []
    property bool cfg_fahrenheit
    property string cfg_placeDefault
    property real cfg_latitudeDefault
    property real cfg_longitudeDefault
    property var cfg_placesDefault: []
    property bool cfg_fahrenheitDefault

    // The dialog edits a draft. Apply/OK updates the shared preference; Cancel
    // discards it, just like the other Plasma configuration pages.
    WeatherStore { id: shared }
    property bool initialized: false
    Connections {
        target: shared
        function onLoadedChanged() {
            if (!shared.loaded || page.initialized) return;
            page.initialized = true;
            page.cfg_place = shared.config.place;
            page.cfg_latitude = shared.config.latitude;
            page.cfg_longitude = shared.config.longitude;
            page.cfg_places = shared.config.places.map(p => JSON.stringify(p));
            page.cfg_fahrenheit = shared.config.fahrenheit;
        }
    }
    function saveConfig() {
        shared.write({place: cfg_place, latitude: cfg_latitude, longitude: cfg_longitude,
            places: Array.from(cfg_places), fahrenheit: cfg_fahrenheit});
    }

    property var found: []
    property bool searching: false

    // The card's list: the place it shows is always in it.
    readonly property var shown: ({name: cfg_place, latitude: cfg_latitude, longitude: cfg_longitude})
    readonly property var places: {
        const list = Array.from(cfg_places || []).map(text => {
            try {
                return JSON.parse(text);
            } catch (e) {
                return null;
            }
        }).filter(place => place && place.name);
        return cfg_place !== "" && !list.some(place => same(place, shown)) ? list.concat([shown]) : list;
    }

    function same(a, b) {
        return Math.abs(a.latitude - b.latitude) < 0.0001 && Math.abs(a.longitude - b.longitude) < 0.0001;
    }

    function show(place) {
        cfg_place = place.name;
        cfg_latitude = place.latitude;
        cfg_longitude = place.longitude;
    }

    function keep(list) {
        cfg_places = list.map(place => JSON.stringify({name: place.name, latitude: place.latitude, longitude: place.longitude}));
    }

    function add(place) {
        if (!places.some(known => same(known, place))) {
            keep(places.concat([place]));
        }
        if (cfg_place === "") {
            show(place);
        }
        found = [];
        query.text = "";
    }

    // The place shown can go too: the card then shows its neighbour.
    function remove(index) {
        const gone = places[index];
        const rest = places.filter((place, i) => i !== index);
        keep(rest);
        if (same(gone, shown)) {
            if (rest.length > 0) {
                show(rest[Math.min(index, rest.length - 1)]);
            } else {
                cfg_place = "";
            }
        }
    }

    function search() {
        const name = query.text.trim();
        if (name.length < 2) {
            return;
        }
        searching = true;
        const request = new XMLHttpRequest();
        request.onreadystatechange = () => {
            if (request.readyState !== XMLHttpRequest.DONE) {
                return;
            }
            searching = false;
            try {
                found = JSON.parse(request.responseText).results || [];
            } catch (e) {
                found = [];
            }
        };
        request.open("GET", "https://geocoding-api.open-meteo.com/v1/search?count=8&format=json&name="
                     + encodeURIComponent(name) + "&language=" + Qt.locale().name.split("_")[0]);
        request.send();
    }

    Kirigami.FormLayout {
        ColumnLayout {
            Kirigami.FormData.label: i18n("Places:")
            spacing: 0

            QQC2.Label {
                visible: page.places.length === 0
                text: i18n("No place yet")
            }
            Repeater {
                model: page.places
                RowLayout {
                    id: placeRow
                    required property var modelData
                    required property int index
                    QQC2.Label {
                        Layout.minimumWidth: Kirigami.Units.gridUnit * 10
                        text: placeRow.modelData.name
                        // The one the card shows now.
                        font.bold: page.same(placeRow.modelData, page.shown)
                    }
                    QQC2.ToolButton {
                        icon.name: "list-remove"
                        text: i18nc("%1 is a town", "Remove %1", placeRow.modelData.name)
                        display: QQC2.AbstractButton.IconOnly
                        QQC2.ToolTip.text: text
                        QQC2.ToolTip.visible: hovered
                        onClicked: page.remove(placeRow.index)
                    }
                }
            }
        }

        RowLayout {
            Kirigami.FormData.label: i18n("Add a place:")
            QQC2.TextField {
                id: query
                placeholderText: i18n("A town or a city")
                onAccepted: page.search()
            }
            QQC2.Button {
                text: i18n("Search")
                enabled: query.text.trim().length >= 2 && !page.searching
                onClicked: page.search()
            }
        }

        ColumnLayout {
            visible: page.found.length > 0
            Repeater {
                model: page.found
                QQC2.Button {
                    required property var modelData
                    Layout.fillWidth: true
                    flat: true
                    text: [modelData.name, modelData.admin1, modelData.country].filter(p => p).join(", ")
                    onClicked: page.add(modelData)
                }
            }
        }

        QQC2.CheckBox {
            Kirigami.FormData.label: i18n("Degrees:")
            text: i18n("Fahrenheit")
            checked: page.cfg_fahrenheit
            onToggled: page.cfg_fahrenheit = checked
        }

        QQC2.Label {
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            opacity: 0.7
            text: i18n("The desktop and bar share these places and degrees. Weather comes from Open-Meteo; only the places are sent.")
        }
    }
}
