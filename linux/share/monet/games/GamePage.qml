/*
 * A game's own page in Games: its wide picture with its name on it, Play (Install for one you
 * own but haven't installed, its downloads for one on its way), where it plays,
 * when it was last played, how long it's been played and how much room it takes, and what
 * else there is to do with it (the star, and its menu). Counter-Strike 2's has FACEIT too,
 * whose matches and anti-cheat only run in Windows: whether it's set up there, what it needs,
 * and Set up FACEIT or Play on FACEIT.
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
    // Owned, not installed: Install opens its launcher's installer.
    readonly property bool toInstall: game.state === "owned" && !!game.install
    // What's worth knowing about where it plays, how its download is going, or how to get it.
    readonly property string note: game.state === "paused" ? i18n("Its download is paused in %1.", app.launcherName(game))
        : game.state === "waiting" ? i18n("It's waiting its turn in %1's downloads.", app.launcherName(game))
        : typeof game.progress === "number" ? i18n("Steam is downloading it: %1%.", game.progress)
        : game.state === "downloading" ? i18n("%1 is downloading it.", app.launcherName(game))
        : toInstall ? i18n("You own it, and it isn't installed yet. Install opens %1, which downloads it.", app.launcherName(game))
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
        [game.state === "owned" ? i18n("Size once installed") : i18n("Size on disk"), app.sizeText(game.size)]
    ].filter(s => s[1] !== "")

    // FACEIT, on Counter-Strike 2's page when there's a Windows to play it in (Games' faceit).
    readonly property bool faceitHere: game.id === app.faceitGame && app.windowsHere
    readonly property var faceit: app.faceit || ({})
    readonly property bool faceitReady: faceit.ready === true
    readonly property string faceitText: {
        const last = faceit.problem === "no-download" ? i18n("Last time, FACEIT couldn't be downloaded in Windows. Check the internet connection, then try again.")
            : faceit.problem === "not-signed" ? i18n("Last time, Windows couldn't confirm that FACEIT made its installer, so Monet didn't run it. Try again later.")
            : faceit.problem === "not-finished" ? i18n("Last time, FACEIT's installer closed before it finished. Try again whenever you like.")
            : faceit.problem === "stopped" ? i18n("Last time, you came back before FACEIT was set up.")
            : ""
        const about = faceitReady
            ? i18n("Play on FACEIT restarts your PC in Windows and opens FACEIT, then %1. Play still plays it here, as ever.", game.name || "")
              + (game.windows === "" ? " " + i18n("Steam in Windows installs it the first time.") : "")
            : i18n("%1 plays here, but FACEIT's matches and anti-cheat only run in Windows. Monet can set FACEIT up there once, with FACEIT's own installers.", game.name || "")
        const unseen = faceit.looked === false && !faceitReady
            ? " " + i18n("Monet couldn't look in Windows at this start, so setting up checks what's there first.") : ""
        return (last !== "" ? last + " " : "") + about + unseen
    }
    // What FACEIT asks of the PC, as far as Monet can tell: [name, true/false/null, what to do].
    readonly property var faceitNeeds: {
        const needs = []
        const boot = faceit.secureBoot
        needs.push([i18n("Secure Boot"), boot === "on" ? true : boot === "off" ? false : null,
                    boot === "on" ? i18nc("a protection is", "On")
                    : boot === "off" ? i18n("Off. FACEIT needs it on: Settings, Security shows how, so Monet still starts.")
                    : boot === "unavailable" ? i18n("This PC didn't start in UEFI mode, so Secure Boot can't be on.")
                    : i18n("Couldn't check.")])
        const windows = faceit.windows || null
        const tpm = faceit.tpm === true || (windows !== null && String(windows.tpm || "").startsWith("2"))
        needs.push([i18n("TPM 2.0"), tpm, tpm ? i18nc("a protection is", "On")
                    : i18n("Not found. FACEIT needs one: most PCs have it in the processor, turned on in the firmware settings (Intel PTT or AMD fTPM).")])
        if (windows !== null && typeof windows.vbs === "boolean")
            needs.push([i18n("Virtualization-based security"), windows.vbs, windows.vbs ? i18n("On in Windows")
                        : i18n("Off in Windows. FACEIT asks some players for it: turn on virtualization and IOMMU in the firmware settings, then Memory integrity in Windows Security.")])
        return needs
    }

    signal back()
    // What the keys reach below the fold (FACEIT's buttons) comes into view.
    function reveal(item) {
        const top = item.mapToItem(column, 0, 0).y
        if (top < contentY)
            contentY = Math.max(0, top - 24)
        else if (top + item.height > contentY + height)
            contentY = Math.max(0, Math.min(contentHeight - height, top + item.height + 24 - height))
    }
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
            objectName: "gameHero"
            width: parent.width
            height: Math.round(Math.min(Math.max(page.width * 0.36, 220), 380))
            layer.enabled: GraphicsInfo.api !== GraphicsInfo.Software
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
                    layer.enabled: GraphicsInfo.api !== GraphicsInfo.Software
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
                    text: page.toInstall ? i18n("Install with %1", page.app.launcherName(page.game))
                        : page.app.busy(page.game) && page.game.launcher ? i18n("Show downloads")
                        : page.game.plays === "windows" ? i18n("Play on Windows") : i18n("Play in Monet")
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

            // FACEIT: whether it's in Windows, what it needs, and the one thing to do.
            Rectangle {
                id: faceitCard
                objectName: "faceit"
                Layout.fillWidth: true
                Layout.bottomMargin: 8
                visible: page.faceitHere
                implicitHeight: faceitColumn.implicitHeight + 36
                radius: 14
                color: page.tone.wash
                border.width: 1
                border.color: page.tone.line

                ColumnLayout {
                    id: faceitColumn
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 18
                    spacing: 10
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        text: "FACEIT"
                        color: page.tone.dim
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        font.letterSpacing: 0.7
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        text: page.faceitReady ? i18n("Ready in Windows") : i18n("Not set up in Windows yet")
                        color: page.tone.ink
                        wrapMode: Text.Wrap
                        font.pixelSize: 17
                        font.weight: Font.Medium
                    }
                    Text {
                        objectName: "faceitText"
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        text: page.faceitText
                        color: page.tone.ink
                        opacity: 0.85
                        wrapMode: Text.Wrap
                        font.pixelSize: 14
                        lineHeight: 1.15
                    }
                    Repeater {
                        model: page.faceitNeeds
                        RowLayout {
                            id: need
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 10
                            // On, off, or couldn't tell.
                            Glyph {
                                Layout.alignment: Qt.AlignTop
                                Layout.topMargin: 2
                                Layout.preferredWidth: 16
                                Layout.preferredHeight: 16
                                stroke: 2.2
                                path: need.modelData[1] === true ? "M5 12.5l4.5 4.5L19 7.5"
                                    : need.modelData[1] === false ? "M12 7v6M12 17h.01" : "M8 12h8"
                                color: need.modelData[1] === true ? page.tone.lily
                                    : need.modelData[1] === false ? (page.tone.dark ? "#FF8A6B" : "#C2410C") : page.tone.dim
                            }
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                textFormat: Text.PlainText
                                text: need.modelData[0] + "  ·  " + need.modelData[2]
                                color: page.tone.ink
                                wrapMode: Text.Wrap
                                font.pixelSize: 13
                            }
                            Accessible.role: Accessible.StaticText
                            Accessible.name: need.modelData[0] + ": " + need.modelData[2]
                        }
                    }
                    RowLayout {
                        Layout.topMargin: 4
                        spacing: 8
                        Pill {
                            id: faceitAction
                            objectName: "faceitAction"
                            tone: page.tone
                            kind: "lily"
                            text: page.faceitReady ? i18n("Play on FACEIT") : i18n("Set up FACEIT")
                            onClicked: page.faceitReady ? page.app.playOnFaceit(page.game) : page.app.setUpFaceit(page.game)
                            onActiveFocusChanged: if (activeFocus) page.reveal(this)
                        }
                        Pill {
                            objectName: "faceitSecurity"
                            tone: page.tone
                            visible: page.faceit.secureBoot === "off"
                            text: i18n("Security settings")
                            onClicked: page.app.openSecurity()
                            onActiveFocusChanged: if (activeFocus) page.reveal(this)
                        }
                    }
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
