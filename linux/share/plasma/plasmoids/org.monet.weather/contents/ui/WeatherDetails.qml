/* One forecast for the desktop card and the bar, using their shared cache. */
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import QtQuick.Templates as T
import org.kde.kirigami as Kirigami
import "Forecast.js" as Forecast

FocusScope {
    id: details
    required property QtObject store
    required property var describe
    signal closed()
    signal placesRequested()
    readonly property var weather: store.weather
    readonly property var now: weather ? weather.current : null
    readonly property var days: Forecast.days(weather)
    property string selectedDay: ""
    property string locationKey: ""
    property double clockNow: Date.now()
    property int firstHour: 0
    readonly property int pageSize: width < Kirigami.Units.gridUnit * 24 ? 4 : 6
    readonly property var hours: Forecast.hours(weather, selectedDay, clockNow)
    readonly property var picked: days.find(day => day.time === selectedDay) || days[0] || ({})
    readonly property color ink: Kirigami.Theme.textColor
    readonly property color dim: Kirigami.Theme.disabledTextColor
    readonly property color lily: Kirigami.Theme.backgroundColor.hslLightness < 0.5 ? "#4DB4A0" : "#357F72"
    readonly property string windUnit: weather && weather.current_units ? weather.current_units.wind_speed_10m || "" : ""
    readonly property string today: Forecast.localHour(weather, clockNow).slice(0, 10)
    onSelectedDayChanged: firstHour = 0
    onPageSizeChanged: firstHour = 0
    onHoursChanged: if (firstHour >= hours.length) firstHour = 0
    Connections {
        target: details.store
        function onConfigChanged() {
            const key = [details.store.config.latitude, details.store.config.longitude].join(",");
            if (key !== details.locationKey) {
                details.locationKey = key;
                details.selectedDay = "";
                details.firstHour = 0;
            }
        }
    }
    Timer { interval: 60000; running: details.visible; repeat: true; onTriggered: details.clockNow = Date.now() }
    function opened() {
        clockNow = Date.now(); selectedDay = ""; firstHour = 0;
        closeButton.forceActiveFocus();
        if (scroll.contentItem) scroll.contentItem.contentY = 0;
    }
    function reveal(item) {
        let ancestor = item.parent;
        while (ancestor && ancestor !== scroll) ancestor = ancestor.parent;
        if (!ancestor) return; // Fixed header buttons must not move the forecast.
        const flick = scroll.contentItem;
        if (!flick || !flick.contentItem) return;
        const pos = item.mapToItem(flick.contentItem, 0, 0);
        if (pos.y < flick.contentY) flick.contentY = Math.max(0, pos.y - 8);
        else if (pos.y + item.height > flick.contentY + flick.height)
            flick.contentY = Math.min(Math.max(0, flick.contentHeight - flick.height), pos.y + item.height - flick.height + 8);
    }
    Keys.onEscapePressed: closed()
    Keys.onPressed: event => {
        const flick = scroll.contentItem;
        if (event.key === Qt.Key_PageDown || event.key === Qt.Key_PageUp) {
            flick.contentY = Math.max(0, Math.min(flick.contentHeight - flick.height,
                flick.contentY + flick.height * 0.8 * (event.key === Qt.Key_PageDown ? 1 : -1)));
            event.accepted = true;
        }
    }
    LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
    LayoutMirroring.childrenInherit: true

    component Copy: Text {
        color: Kirigami.Theme.textColor
        font.family: "Inter"
        font.pointSize: Kirigami.Theme.defaultFont.pointSize
        textFormat: Text.PlainText
        wrapMode: Text.WordWrap
    }
    component PaintButton: T.AbstractButton {
        id: button
        activeFocusOnTab: true
        implicitWidth: label.implicitWidth + 20
        implicitHeight: Math.max(32, label.implicitHeight + 12)
        Accessible.name: text
        signal revealRequested(var item)
        onActiveFocusChanged: if (activeFocus) revealRequested(button)
        opacity: enabled ? 1 : 0.45
        contentItem: Copy {
            id: label
            text: button.text
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            radius: 10
            color: button.down ? Qt.rgba(0.5, 0.5, 0.5, 0.24) : Qt.rgba(0.5, 0.5, 0.5, button.hovered ? 0.18 : 0.09)
            border.width: button.visualFocus ? 2 : 0
            border.color: Kirigami.Theme.backgroundColor.hslLightness < 0.5 ? "#4DB4A0" : "#357F72"
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Kirigami.Units.smallSpacing * 2
        spacing: Kirigami.Units.smallSpacing * 2
        RowLayout {
            Layout.fillWidth: true
            Copy {
                Layout.fillWidth: true
                text: details.store.config.place || i18n("Weather")
                font.family: "Fraunces 72pt SuperSoft"
                font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.7
                maximumLineCount: 2
                elide: Text.ElideRight
                Accessible.role: Accessible.Heading
            }
            PaintButton { text: i18n("Places"); onClicked: details.placesRequested() }
            PaintButton {
                id: closeButton
                text: "×"
                Accessible.name: i18n("Close weather")
                onClicked: details.closed()
            }
        }

        QQC2.ScrollView {
            id: scroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: availableWidth
            clip: true
            QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
            QQC2.ScrollBar.vertical.policy: QQC2.ScrollBar.AsNeeded
            ColumnLayout {
                width: scroll.availableWidth - Kirigami.Units.smallSpacing * 2
                spacing: Kirigami.Units.smallSpacing * 3
                RowLayout {
                    Layout.fillWidth: true
                    visible: details.now !== null
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Copy {
                            text: details.now ? Forecast.number(details.now.temperature_2m, details.store.config.fahrenheit ? "°F" : "°C") : ""
                            font.family: "Fraunces 72pt SuperSoft"
                            font.pointSize: Kirigami.Theme.defaultFont.pointSize * 3.6
                            font.weight: Font.Light
                        }
                        Copy { Layout.fillWidth: true; text: details.now ? details.describe(details.now.weather_code) : "" }
                        Copy {
                            Layout.fillWidth: true
                            color: details.dim
                            text: details.now ? i18n("Feels like %1 · Wind %2", Forecast.number(details.now.apparent_temperature, "°"),
                                Forecast.number(details.now.wind_speed_10m, " " + details.windUnit)) : ""
                        }
                    }
                    Sky {
                        size: Kirigami.Units.gridUnit * 4
                        code: details.now ? details.now.weather_code : 2
                        day: details.now ? details.now.is_day === 1 : true
                    }
                }

                Copy {
                    Layout.fillWidth: true
                    visible: details.store.stale || !details.now
                    text: details.store.problem || i18n("Looking at the sky…")
                }
                Copy {
                    Layout.fillWidth: true
                    visible: details.store.updated > 0
                    color: details.dim
                    text: i18n("Updated %1", Qt.formatDateTime(new Date(details.store.updated * 1000), "ddd HH:mm"))
                }

                RowLayout {
                    Layout.fillWidth: true
                    Copy {
                        Layout.fillWidth: true
                        text: details.selectedDay ? Qt.formatDate(new Date(details.selectedDay + "T12:00"), "dddd d MMM") : i18n("Next 24 hours")
                        font.weight: Font.DemiBold
                        Accessible.role: Accessible.Heading
                    }
                    PaintButton { id: nowButton; text: i18n("Now"); visible: details.selectedDay !== ""; onClicked: details.selectedDay = ""; onRevealRequested: item => details.reveal(item) }
                    PaintButton {
                        text: "‹"; Accessible.name: i18n("Earlier hours")
                        onRevealRequested: item => details.reveal(item)
                        enabled: details.firstHour > 0
                        onClicked: details.firstHour = Math.max(0, details.firstHour - details.pageSize)
                    }
                    PaintButton {
                        text: "›"; Accessible.name: i18n("Later hours")
                        onRevealRequested: item => details.reveal(item)
                        enabled: details.firstHour + details.pageSize < details.hours.length
                        onClicked: details.firstHour += details.pageSize
                    }
                }
                Copy {
                    Layout.fillWidth: true
                    visible: details.hours.length === 0
                    text: i18n("Hourly details are unavailable. Refresh to try again.")
                    color: details.dim
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Repeater {
                        model: details.hours.slice(details.firstHour, details.firstHour + details.pageSize)
                        Rectangle {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            implicitHeight: hourContents.implicitHeight + 16
                            radius: 12
                            color: Qt.rgba(0.5, 0.5, 0.5, 0.08)
                            Accessible.role: Accessible.StaticText
                            Accessible.name: i18n("%1, %2, %3, precipitation %4", modelData.time.replace("T", " "),
                                details.describe(modelData.code), Forecast.number(modelData.temperature, "°"), Forecast.number(modelData.rain, "%"))
                            ColumnLayout {
                                id: hourContents
                                anchors.centerIn: parent
                                width: parent.width - 4
                                spacing: 5
                                Copy { Layout.alignment: Qt.AlignHCenter; text: Forecast.clock(modelData.time); font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.9 }
                                Sky { Layout.alignment: Qt.AlignHCenter; size: 30; code: modelData.code === null ? 2 : modelData.code; day: modelData.day }
                                Copy { Layout.alignment: Qt.AlignHCenter; text: Forecast.number(modelData.temperature, "°"); font.weight: Font.DemiBold }
                                Copy { Layout.alignment: Qt.AlignHCenter; text: Forecast.number(modelData.rain, "%"); color: details.lily }
                            }
                        }
                    }
                }
                Copy {
                    Layout.fillWidth: true
                    visible: details.hours.length > 0
                    color: details.dim
                    text: i18n("Percentages show the chance of rain or snow. Times are local to %1.", details.store.config.place)
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.9
                }
                Copy {
                    text: i18n("This week")
                    font.weight: Font.DemiBold
                    Accessible.role: Accessible.Heading
                }
                Repeater {
                    model: details.days
                    T.AbstractButton {
                        id: dayButton
                        required property var modelData
                        Layout.fillWidth: true
                        implicitHeight: dayRow.implicitHeight + 18
                        activeFocusOnTab: true
                        onActiveFocusChanged: if (activeFocus) details.reveal(dayButton)
                        checked: details.selectedDay === modelData.time
                        Accessible.name: i18n("%1, %2, high %3, low %4, precipitation %5. Show hourly forecast.",
                            Qt.formatDate(new Date(modelData.time + "T12:00"), "dddd d MMM"), details.describe(modelData.code),
                            Forecast.number(modelData.high, "°"), Forecast.number(modelData.low, "°"), Forecast.number(modelData.rain, "%"))
                        onClicked: { details.selectedDay = modelData.time; scroll.contentItem.contentY = 0; nowButton.forceActiveFocus(); }
                        background: Rectangle {
                            radius: 10
                            color: dayButton.checked ? Qt.rgba(details.lily.r, details.lily.g, details.lily.b, 0.18)
                                : Qt.rgba(0.5, 0.5, 0.5, dayButton.hovered ? 0.14 : 0.06)
                            border.width: dayButton.visualFocus ? 2 : 0
                            border.color: details.lily
                        }
                        contentItem: RowLayout {
                            id: dayRow
                            spacing: 8
                            Copy {
                                Layout.leftMargin: 10
                                Layout.fillWidth: true
                                text: dayButton.modelData.time === details.today ? i18n("Today")
                                    : Qt.formatDate(new Date(dayButton.modelData.time + "T12:00"), "ddd d")
                            }
                            Sky { size: 28; code: dayButton.modelData.code === null ? 2 : dayButton.modelData.code }
                            Copy { Layout.preferredWidth: 48; text: Forecast.number(dayButton.modelData.rain, "%"); color: details.lily; horizontalAlignment: Text.AlignRight }
                            Copy { Layout.preferredWidth: 82; Layout.rightMargin: 10; text: Forecast.number(dayButton.modelData.low, "°") + " / " + Forecast.number(dayButton.modelData.high, "°"); horizontalAlignment: Text.AlignRight }
                        }
                    }
                }
                Copy {
                    Layout.fillWidth: true
                    text: i18n("%1 · Sunrise %2 · Sunset %3", details.selectedDay ? Qt.formatDate(new Date(details.selectedDay + "T12:00"), "ddd d") : i18n("Today"),
                        Forecast.clock(details.picked.sunrise), Forecast.clock(details.picked.sunset))
                    color: details.dim
                }
                RowLayout {
                    Layout.fillWidth: true
                    Copy { Layout.fillWidth: true; text: i18n("Forecast by Open-Meteo"); color: details.dim }
                    PaintButton {
                        text: details.store.inFlight ? i18n("Updating…") : i18n("Refresh")
                        onRevealRequested: item => details.reveal(item)
                        enabled: details.store.inFlight === ""
                        onClicked: details.store.retry()
                    }
                }
            }
        }
    }
}
