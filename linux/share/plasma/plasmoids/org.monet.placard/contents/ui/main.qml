/*
 * Placard: the card next to a painting in a museum. It greets you by name,
 * shows the time in Fraunces, the date, and which painting and light are on the wall.
 */
import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.coreaddons as KCoreAddons

PlasmoidItem {
    id: root

    property date now: new Date()
    // Same hours as the wallpaper.
    readonly property string light: {
        const h = now.getHours()
        return h >= 5 && h < 10 ? "dawn" : h >= 10 && h < 17 ? "midday" : h >= 17 && h < 21 ? "dusk" : "night"
    }
    // The light's name, as the card says it: "Impression, dawn".
    readonly property string lightName: ({
        dawn: i18nc("the painting's light, as in Impression, dawn", "dawn"),
        midday: i18nc("the painting's light, as in Impression, midday", "midday"),
        dusk: i18nc("the painting's light, as in Impression, dusk", "dusk"),
        night: i18nc("the painting's light, as in Impression, night", "night")
    })[light]
    // Midday's sky is bright, so the text turns to ink.
    readonly property bool ink: light === "midday"
    readonly property color textColor: ink ? "#13202E" : "#FFFFFF"
    readonly property color shadowColor: ink ? "#B0FFFFFF" : "#9914102A"

    KCoreAddons.KUser {
        id: user
    }
    readonly property string firstName: (user.fullName || "").trim().split(" ")[0] || user.loginName
    readonly property string greeting: {
        const h = now.getHours()
        return h < 5 ? i18nc("greeting late at night, %1 is a first name", "Still up, %1?", firstName)
            : h < 12 ? i18nc("%1 is a first name", "Good morning, %1.", firstName)
            : h < 17 ? i18nc("%1 is a first name", "Good afternoon, %1.", firstName)
            : h < 22 ? i18nc("%1 is a first name", "Good evening, %1.", firstName)
            : i18nc("%1 is a first name", "Good night, %1.", firstName)
    }

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation

    Timer {
        // Tick on the minute.
        interval: (60 - root.now.getSeconds()) * 1000 + 50
        running: true
        repeat: true
        onTriggered: {
            root.now = new Date()
            interval = (60 - root.now.getSeconds()) * 1000 + 50
        }
    }

    fullRepresentation: Item {
        Layout.minimumWidth: card.implicitWidth
        Layout.minimumHeight: card.implicitHeight
        Layout.preferredWidth: card.implicitWidth
        Layout.preferredHeight: card.implicitHeight

        ColumnLayout {
            id: card
            anchors.left: parent.left
            anchors.top: parent.top
            spacing: 0
            layer.enabled: true
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowColor: root.shadowColor
                shadowBlur: 0.9
                shadowVerticalOffset: 2
            }

            Text {
                horizontalAlignment: Text.AlignLeft
                visible: root.firstName !== ""
                text: root.greeting
                color: root.textColor
                font.family: "Fraunces 72pt SuperSoft"
                font.italic: true
                font.pixelSize: 26
                Layout.bottomMargin: 6
            }

            Text {
                horizontalAlignment: Text.AlignLeft
                text: Qt.formatDate(root.now, "dddd, d MMMM")
                color: root.textColor
                opacity: 0.88
                font.pixelSize: 15
                font.weight: Font.Medium
                font.letterSpacing: 0.2
            }

            Text {
                horizontalAlignment: Text.AlignLeft
                text: Qt.formatTime(root.now, Qt.locale().timeFormat(Locale.ShortFormat))
                color: root.textColor
                font.family: "Fraunces 72pt SuperSoft"
                font.weight: Font.Light
                font.pixelSize: 132
                font.letterSpacing: -5
                Layout.leftMargin: -5
                Layout.topMargin: -6
                Layout.bottomMargin: -8
            }

            RowLayout {
                spacing: 12
                opacity: 0.9

                Item {
                    implicitWidth: 26
                    implicitHeight: 14
                    Rectangle { x: 9; y: 0; width: 8; height: 8; radius: 4; color: "#F2552C" }
                    Rectangle { x: 3; y: 10; width: 20; height: 2.4; radius: 1.2; color: "#F2552C"; opacity: 0.8 }
                }

                Text {
                    horizontalAlignment: Text.AlignLeft
                    text: Plasmoid.configuration.Series === "lilies"
                        ? i18nc("the wallpaper's name, after Monet's Water Lilies; %1 is the light", "Water Lilies, %1", root.lightName)
                        : Plasmoid.configuration.Series === "haystacks"
                        ? i18nc("the wallpaper's name, after Monet's Haystacks; %1 is the light", "Haystacks, %1", root.lightName)
                        : i18nc("the wallpaper's name, after Monet's Impression, soleil levant", "Impression, %1", root.lightName)
                    color: root.textColor
                    font.family: "Fraunces 72pt SuperSoft"
                    font.italic: true
                    font.pixelSize: 21
                }
            }
        }
    }
}
