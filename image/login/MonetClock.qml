// SPDX-License-Identifier: LGPL-2.0-or-later
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.clock as PlasmaClock
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: clock
    property bool spacious: false
    spacing: spacious ? 18 : 6

    RowLayout {
        Layout.alignment: Qt.AlignHCenter
        spacing: 9
        Rectangle { width: 9; height: 9; radius: 5; color: "#F2552C" }
        Text {
            text: "Monet"
            color: "#EFECE6"
            font.family: "Inter"
            font.pixelSize: 17
            font.letterSpacing: 1
        }
    }
    Text {
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignHCenter
        text: Qt.formatTime(timeSource.dateTime, Qt.locale(), Locale.ShortFormat)
        textFormat: Text.PlainText
        horizontalAlignment: Text.AlignHCenter
        color: "#EFECE6"
        font.family: "Fraunces 72pt SuperSoft"
        font.pointSize: Kirigami.Theme.defaultFont.pointSize * (clock.spacious ? 7.0 : 4.8)
        font.weight: Font.Light
        font.features: ({ "tnum": 1 })
        minimumPointSize: Kirigami.Theme.defaultFont.pointSize * 2
        fontSizeMode: Text.HorizontalFit
        renderType: Text.NativeRendering
    }
    Text {
        Layout.fillWidth: true
        text: Qt.formatDate(timeSource.dateTime, Qt.locale(), Locale.LongFormat)
        textFormat: Text.PlainText
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        color: "#B4AEA5"
        font.family: "Inter"
        font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.35
    }
    PlasmaClock.Clock {
        id: timeSource
        trackSeconds: Qt.locale().timeFormat(Locale.ShortFormat).includes("s")
    }
}
