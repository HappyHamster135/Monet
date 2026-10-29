/*
 * A game's own page in Games: its wide picture with its name on it, Play, where it plays,
 * when it was last played, how long it's been played and how much room it takes, and what
 * else there is to do with it (the star, and its menu).
 */
import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Flickable {
    id: page
    MouseScroll { view: page }
    // Games' window, for what it does (play, the menu, favorites) and its words for times.
    property var app
    property var tone
    property var game: ({})
    readonly property bool both: game.plays === "monet" && game.windows !== ""
    // What's worth knowing about where it plays, or how its download is going.
    readonly property string note: typeof game.progress === "number" ? i18n("Steam is downloading it: %1%.", game.progress)
        : game.move && game.why === "reports"
            ? i18n("Players report it doesn't run in Monet, so it plays in Windows. In Steam, move it to Windows games (Properties, Installed Files, Move install folder), and Play starts it there, with nothing to download.")
        : game.move
            ? i18n("Its anti-cheat only lets it play in Windows. In Steam, move it to Windows games (Properties, Installed Files, Move install folder), and Play starts it there, with nothing to download.")
        : game.plays === "windows" && game.windows === "" && game.why === "reports"
            ? i18n("Players report it doesn't run in Monet, and it isn't installed in Windows yet. Restart in Windows and install it with %1.", app.storeName(game.store))
        : game.plays === "windows" && game.windows === ""
            ? i18n("Its anti-cheat only lets it play in Windows, and it isn't installed there yet. Restart in Windows and install it with %1.", app.storeName(game.store))
        : both && game.shared ? i18n("Installed once, in Windows' Games folder: it plays here and in Windows.")
        : game.plays === "windows" && game.why === "reports"
            ? i18n("Players report it doesn't run in Monet: Play restarts your PC in Windows and opens it.")
        : game.plays === "windows" && game.why === "anticheat"
            ? i18n("Its anti-cheat only lets it play in Windows: Play restarts your PC in Windows and opens it.")
        : game.plays === "windows"
            ? i18n("It's installed in Windows: Play restarts your PC in Windows and opens it, and when you quit, you're back here.")
        : ""
    readonly property var stats: [
        [i18n("Plays on"), both ? i18n("Monet and Windows") : game.plays === "monet" ? "Monet" : "Windows"],
        [i18n("Last played"), app.lastText(game.last)],
        [i18n("Play time"), app.timeText(game.minutes)],
        [i18n("Size on disk"), app.sizeText(game.size)]
    ].filter(s => s[1] !== "")

    signal back()
    function focusPlay() {
        play.forceActiveFocus()
    }

    contentHeight: column.implicitHeight + 36
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    // A wheel's turn glides, as in the Store.
    Kirigami.WheelHandler {
        target: page
        filterMouseEvents: !("acceptedButtons" in page)
        keyNavigationEnabled: true
        verticalStepSize: 96
    }
    Keys.onEscapePressed: page.back()
    Keys.onBackPressed: page.back()

    Column {
        id: column
        width: page.width
        spacing: 0

        // The picture, the name on it, and the way back. Its top corners follow the page's.
        Item {
            id: hero
            width: parent.width
            height: Math.round(Math.min(Math.max(page.width * 0.36, 220), 380))
            layer.enabled: true
            layer.effect: MultiEffect {
                maskEnabled: true
                maskSource: heroShapeBox
                maskThresholdMin: 0.5
                maskSpreadAtMin: 1.0
            }

            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: page.app.glaze(page.game.name || "")[0] }
                    GradientStop { position: 1; color: page.app.glaze(page.game.name || "")[1] }
                }
                Image {
                    anchors.fill: parent
                    source: page.app.texture
                    fillMode: Image.PreserveAspectCrop
                    opacity: 0.9
                }
            }
            // Its banner, and over it its wide picture when there's one (Steam's, say).
            Image {
                anchors.fill: parent
                source: page.game.art || ""
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                sourceSize.width: 920
                visible: status === Image.Ready
            }
            Image {
                anchors.fill: parent
                source: page.game.hero || ""
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                sourceSize.width: 1800
                visible: status === Image.Ready
            }
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: parent.height * 0.62
                gradient: Gradient {
                    GradientStop { position: 0; color: "transparent" }
                    GradientStop { position: 1; color: Qt.rgba(0, 0, 0, 0.66) }
                }
            }

            ColumnLayout {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.leftMargin: 36
                anchors.rightMargin: 36
                anchors.bottomMargin: 24
                spacing: 2
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: page.app.storeName(page.game.store || "")
                    color: Qt.rgba(1, 1, 1, 0.8)
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.8
                    font.capitalization: Font.AllUppercase
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: page.game.name || ""
                    color: "#FFFFFF"
                    elide: Text.ElideRight
                    font.family: "Fraunces 72pt SuperSoft"
                    font.weight: Font.Light
                    font.pixelSize: Math.round(Math.min(48, Math.max(30, page.width / 22)))
                    font.letterSpacing: -0.6
                    layer.enabled: true
                    layer.effect: MultiEffect {
                        shadowEnabled: true
                        shadowColor: Qt.rgba(0, 0, 0, 0.5)
                        shadowBlur: 0.6
                        shadowVerticalOffset: 1
                    }
                }
            }

            // Back to every game.
            Rectangle {
                id: backButton
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.margins: 16
                width: 38
                height: 38
                radius: 19
                color: backMouse.containsMouse ? Qt.rgba(0, 0, 0, 0.55) : Qt.rgba(0, 0, 0, 0.36)
                border.width: activeFocus ? 2 : 0
                border.color: "#FFFFFF"
                activeFocusOnTab: true
                Keys.onReturnPressed: page.back()
                Keys.onSpacePressed: page.back()
                Glyph {
                    anchors.centerIn: parent
                    width: 18
                    height: 18
                    path: Qt.application.layoutDirection === Qt.RightToLeft ? "M9.5 5.5L16 12l-6.5 6.5" : "M14.5 5.5L8 12l6.5 6.5"
                }
                MouseArea {
                    id: backMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: page.back()
                }
                Accessible.role: Accessible.Button
                Accessible.name: i18n("Back")
                Accessible.onPressAction: page.back()
            }
        }

        // Play, the star and the menu; then what's worth knowing at a glance.
        ColumnLayout {
            x: 36
            width: parent.width - 72
            spacing: 22

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 24
                spacing: 10
                SunButton {
                    id: play
                    size: 17
                    speed: page.tone.speed
                    text: page.game.plays === "windows" && page.game.windows !== "" ? i18n("Play on Windows") : i18n("Play")
                    onClicked: page.app.play(page.game)
                }
                Item { Layout.fillWidth: true }
                Pill {
                    tone: page.tone
                    glyph: "M12 3.8l2.5 5.1 5.6.8-4 3.9.9 5.6-5-2.6-5 2.6.9-5.6-4-3.9 5.6-.8z"
                    glyphFilled: page.game.favorite === true
                    text: page.game.favorite ? i18n("Favorite") : i18n("Add to favorites")
                    onClicked: page.app.setFavorite(page.game, !page.game.favorite)
                }
                Pill {
                    id: more
                    tone: page.tone
                    glyph: "M5.5 12h.01M12 12h.01M18.5 12h.01"
                    Accessible.name: i18n("More")
                    onClicked: page.app.showMenu(page.game, more, true)
                }
            }

            Flow {
                Layout.fillWidth: true
                spacing: 40
                Repeater {
                    model: page.stats
                    Column {
                        required property var modelData
                        spacing: 3
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            text: modelData[0]
                            color: page.tone.dim
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                            font.letterSpacing: 0.7
                            font.capitalization: Font.AllUppercase
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            text: modelData[1]
                            color: page.tone.ink
                            font.pixelSize: 16
                            font.weight: Font.Medium
                        }
                    }
                }
            }

            // Where it plays, or its download: a note on the paper.
            Rectangle {
                Layout.fillWidth: true
                visible: page.note !== ""
                implicitHeight: noteText.implicitHeight + 28
                radius: 14
                color: page.tone.wash
                border.width: 1
                border.color: page.tone.line
                Text {
                    id: noteText
                    horizontalAlignment: Text.AlignLeft
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 18
                    anchors.rightMargin: 18
                    text: page.note
                    color: page.tone.ink
                    opacity: 0.85
                    wrapMode: Text.Wrap
                    font.pixelSize: 14
                    lineHeight: 1.15
                }
            }
        }
    }

    Item {
        id: heroShapeBox
        width: hero.width
        height: hero.height
        visible: false
        layer.enabled: true
        Rectangle {
            width: parent.width
            // Square at the bottom, where the picture meets the paper.
            height: parent.height + radius
            radius: 14
        }
    }
}
