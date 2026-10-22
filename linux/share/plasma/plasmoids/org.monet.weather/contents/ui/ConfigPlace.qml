/*
 * Where the weather is for: type a town and pick it (Open-Meteo's place
 * search), and choose degrees.
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
    property bool cfg_fahrenheit
    property string cfg_placeDefault
    property real cfg_latitudeDefault
    property real cfg_longitudeDefault
    property bool cfg_fahrenheitDefault

    property var found: []
    property bool searching: false

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
        QQC2.Label {
            Kirigami.FormData.label: i18n("Now:")
            text: page.cfg_place || i18n("No place yet")
        }

        RowLayout {
            Kirigami.FormData.label: i18n("Find a place:")
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
                    onClicked: {
                        page.cfg_place = modelData.name;
                        page.cfg_latitude = modelData.latitude;
                        page.cfg_longitude = modelData.longitude;
                        page.found = [];
                    }
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
            text: i18n("The weather comes from Open-Meteo. Only the place is sent.")
        }
    }
}
