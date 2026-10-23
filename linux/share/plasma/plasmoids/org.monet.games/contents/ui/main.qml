/*
 * Windows Games: the games that need Windows, as a gallery of covers. Play
 * asks once, then the sun sets and the PC restarts in Windows with the game.
 * All the work is done by the `monet` command.
 */
import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Window
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    property var games: []
    property bool loaded: false
    // Steam ids of the games that play in Monet too (no anti-cheat that wants Windows).
    property var marks: ({})
    // The game the sheet asks about; null for "just open Windows".
    property var asking: null
    property bool sheetOpen: false
    property string problem: ""
    readonly property string monet: "@BINDIR@/monet"
    readonly property string helper: "@LIBEXECDIR@/monet-quick"
    readonly property string texture: "file://@DATADIR@/monet/textures/brush.png"
    readonly property color sun: "#F2552C"
    // Animations follow the desktop's speed, and stop when it's set to instant.
    readonly property real speed: Kirigami.Units.longDuration / 200

    Plasmoid.icon: "monet-windows"
    toolTipMainText: i18n("Windows Games")
    toolTipSubText: games.length > 0
        ? i18np("%1 game ready to play", "%1 games ready to play", games.length)
        : i18n("Play Windows games with one click")

    P5Support.DataSource {
        id: runner
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source)
            if (source.indexOf(" game-marks") !== -1) {
                try {
                    root.marks = JSON.parse(data["stdout"]).marks || {}
                } catch (e) {
                    root.marks = {}
                }
            } else if (source.indexOf(" games --json") !== -1) {
                try {
                    root.games = JSON.parse(data["stdout"])
                } catch (e) {
                    root.games = []
                }
                root.loaded = true
            } else if (data["exit code"] !== 0) {
                // Switching didn't happen: bring the desktop back and say why.
                sunset.close()
                root.expanded = true
                // The plain first part; the technical rest is for monet's own log.
                root.problem = (data["stderr"] || "").trim().split("\n\n")[0] || i18n("Monet couldn't switch to Windows.")
                root.sheetOpen = true
            }
        }
    }

    function refresh() {
        runner.connectSource(monet + " games --json")
        runner.connectSource(helper + " game-marks")
    }

    function playsHere(id) {
        return id.indexOf("steam:") === 0 && marks[id.slice(6)] === "here"
    }

    function ask(game) {
        problem = ""
        asking = game
        sheetOpen = true
    }

    // Game ids only contain letters, digits, ":", ".", "_" and "-".
    function go() {
        const game = asking
        sheetOpen = false
        expanded = false
        sunset.begin(game ? game.name : "")
        const command = game ? monet + " play '" + game.id + "'" : monet + " windows"
        launch.command = command
        launch.start()
    }

    // Let the sun start setting before the PC goes.
    Timer {
        id: launch
        property string command
        interval: Math.round(900 * root.speed) + 100
        onTriggered: runner.connectSource(command)
    }

    Component.onCompleted: refresh()
    onExpandedChanged: {
        if (expanded) {
            refresh()
        } else {
            sheetOpen = false
        }
    }

    // A painted cover for games without artwork: a glaze from the paintings,
    // brushstrokes of light, and the name.
    readonly property var glazes: [
        ["#E2603A", "#5B2350"], ["#3F9A89", "#1C3556"], ["#9C7BC0", "#2B2547"],
        ["#5C88D0", "#1B2546"], ["#F0A048", "#7A3326"], ["#D46A8C", "#2E2A55"]
    ]
    function glaze(name) {
        let h = 0
        for (let i = 0; i < name.length; i++) {
            h = (Math.imul(h, 31) + name.charCodeAt(i)) >>> 0
        }
        return glazes[h % glazes.length]
    }
    function artwork(id) {
        return id.indexOf("steam:") === 0
            ? "https://cdn.cloudflare.steamstatic.com/steam/apps/" + id.slice(6) + "/header.jpg"
            : ""
    }
    function storeName(id) {
        const store = id.split(":")[0]
        return { steam: "Steam", epic: "Epic", riot: "Riot", custom: i18n("Windows") }[store] || store
    }

    // Inline components can't see this file's ids, so everything they need
    // comes in through properties.
    component Cover: Item {
        id: cover
        property string name
        property string artwork
        property var glaze: ["#5C88D0", "#1B2546"]
        property string texture
        property real radius: 12
        implicitHeight: width * 215 / 460

        Item {
            id: art
            anchors.fill: parent
            layer.enabled: true
            layer.effect: MultiEffect {
                maskEnabled: true
                maskSource: shape
                maskThresholdMin: 0.5
                maskSpreadAtMin: 1.0
            }

            Rectangle {
                anchors.fill: parent
                visible: picture.status !== Image.Ready
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: cover.glaze[0] }
                    GradientStop { position: 1; color: cover.glaze[1] }
                }
                Image {
                    anchors.fill: parent
                    source: cover.texture
                    fillMode: Image.PreserveAspectCrop
                    opacity: 0.9
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: Math.round(parent.height * 0.1)
                    text: cover.name
                    color: "#FFFFFF"
                    elide: Text.ElideRight
                    font.family: "Fraunces 72pt SuperSoft"
                    font.pixelSize: Math.max(12, Math.round(parent.height * 0.17))
                }
            }

            Image {
                id: picture
                anchors.fill: parent
                source: cover.artwork
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                visible: status === Image.Ready
            }
        }

        Rectangle {
            id: shape
            anchors.fill: parent
            radius: cover.radius
            visible: false
            layer.enabled: true
        }
    }

    // The one bright thing: Play.
    component SunButton: Rectangle {
        id: button
        property alias text: label.text
        property real speed: 1
        signal clicked()
        implicitWidth: label.implicitWidth + Kirigami.Units.gridUnit * 1.6
        implicitHeight: Kirigami.Units.gridUnit * 1.7
        radius: height / 2
        color: hover.hovered ? "#FF6A42" : "#F2552C"
        scale: tap.pressed ? 0.95 : hover.hovered ? 1.05 : 1
        Behavior on scale {
            NumberAnimation { duration: Math.round(160 * button.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] }
        }
        Behavior on color { ColorAnimation { duration: Math.round(140 * button.speed) } }

        Text {
            horizontalAlignment: Text.AlignLeft
            id: label
            anchors.centerIn: parent
            color: "#FFFFFF"
            font.weight: Font.DemiBold
            font.pixelSize: Kirigami.Theme.defaultFont.pixelSize
        }
        HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
        TapHandler { id: tap; onTapped: button.clicked() }
        Accessible.role: Accessible.Button
        Accessible.name: label.text
        Accessible.onPressAction: button.clicked()
    }

    fullRepresentation: PlasmaExtras.Representation {
        id: popup
        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true
        Layout.preferredWidth: Kirigami.Units.gridUnit * 25
        Layout.preferredHeight: Kirigami.Units.gridUnit * 29
        Layout.minimumWidth: Kirigami.Units.gridUnit * 20
        Layout.minimumHeight: Kirigami.Units.gridUnit * 20
        collapseMarginsHint: true

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.largeSpacing

            ColumnLayout {
                spacing: 2
                Layout.leftMargin: Kirigami.Units.smallSpacing
                Text {
                    horizontalAlignment: Text.AlignLeft
                    text: i18n("Windows Games")
                    color: Kirigami.Theme.textColor
                    font.family: "Fraunces 72pt SuperSoft"
                    font.pixelSize: 26
                }
                PlasmaComponents.Label {
                    text: i18n("Opens in Windows. Quit to come back.")
                    opacity: 0.7
                }
            }

            GridView {
                id: grid
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: root.games
                cellWidth: Math.floor(width / 2)
                cellHeight: cellWidth * 215 / 460 + Kirigami.Units.gridUnit * 3.2
                boundsBehavior: Flickable.StopAtBounds

                delegate: Item {
                    width: grid.cellWidth
                    height: grid.cellHeight

                    Rectangle {
                        id: card
                        anchors.fill: parent
                        anchors.margins: 3
                        radius: 16
                        color: Kirigami.Theme.textColor
                        opacity: cardHover.hovered ? 0.07 : 0
                        Behavior on opacity { NumberAnimation { duration: Math.round(140 * root.speed) } }
                    }
                    HoverHandler { id: cardHover }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8

                        Cover {
                            name: modelData.name
                            artwork: root.artwork(modelData.id)
                            glaze: root.glaze(modelData.name)
                            texture: root.texture
                            Layout.fillWidth: true
                            Layout.preferredHeight: implicitHeight
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Kirigami.Units.smallSpacing
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                PlasmaComponents.Label {
                                    Layout.fillWidth: true
                                    text: modelData.name
                                    elide: Text.ElideRight
                                    font.weight: Font.DemiBold
                                }
                                PlasmaComponents.Label {
                                    text: root.playsHere(modelData.id) ? i18n("%1 · plays here too", root.storeName(modelData.id))
                                        : root.storeName(modelData.id)
                                    opacity: 0.66
                                    font: Kirigami.Theme.smallFont
                                }
                            }
                            SunButton {
                                speed: root.speed
                                text: i18n("Play")
                                onClicked: root.ask(modelData)
                            }
                        }
                    }
                }

                PlasmaExtras.PlaceholderMessage {
                    anchors.centerIn: parent
                    width: parent.width - Kirigami.Units.gridUnit * 4
                    visible: root.loaded && grid.count === 0
                    iconName: "monet-windows"
                    text: i18n("No Windows games yet")
                    explanation: i18n("Start Windows once and install your games there. They show up here by themselves.")
                }
            }

            RowLayout {
                Layout.fillWidth: true
                PlasmaComponents.Button {
                    icon.name: "system-reboot"
                    text: i18n("Open Windows")
                    onClicked: root.ask(null)
                }
                Item { Layout.fillWidth: true }
                PlasmaComponents.Label {
                    visible: grid.count > 0
                    text: i18np("%1 game", "%1 games", grid.count)
                    opacity: 0.66
                }
            }
        }

        // The question, rising over the gallery.
        Rectangle {
            id: veil
            anchors.fill: parent
            color: "#000000"
            radius: Kirigami.Units.cornerRadius
            opacity: root.sheetOpen ? 0.28 : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: Math.round(240 * root.speed) } }
            TapHandler { onTapped: root.sheetOpen = false }
        }

        Rectangle {
            id: sheet
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: Kirigami.Units.largeSpacing + (root.sheetOpen ? 0 : -16)
            width: parent.width - Kirigami.Units.largeSpacing * 2
            height: sheetColumn.implicitHeight + 36
            radius: 22
            color: Qt.rgba(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.94)
            border.color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.1)
            opacity: root.sheetOpen ? 1 : 0
            scale: root.sheetOpen ? 1 : 0.96
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: Math.round((root.sheetOpen ? 380 : 200) * root.speed) } }
            Behavior on scale {
                NumberAnimation { duration: Math.round(380 * root.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] }
            }
            Behavior on anchors.bottomMargin {
                NumberAnimation { duration: Math.round(380 * root.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] }
            }

            ColumnLayout {
                id: sheetColumn
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 18
                spacing: 14

                Cover {
                    visible: root.asking !== null
                    name: root.asking ? root.asking.name : ""
                    artwork: root.asking ? root.artwork(root.asking.id) : ""
                    glaze: root.glaze(name)
                    texture: root.texture
                    radius: 14
                    Layout.fillWidth: true
                    Layout.preferredHeight: visible ? implicitHeight : 0
                }

                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    color: Kirigami.Theme.textColor
                    font.family: "Fraunces 72pt SuperSoft"
                    font.pixelSize: 24
                    text: root.problem !== "" ? i18n("Couldn't open Windows")
                        : root.asking ? i18n("Play %1?", root.asking.name)
                        : i18n("Restart in Windows?")
                }

                PlasmaComponents.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    opacity: root.problem !== "" ? 1 : 0.75
                    text: root.problem !== "" ? root.problem
                        : root.asking ? i18n("Your PC restarts in Windows and opens the game. When you quit, you're back here. Save your work first.")
                        : i18n("Your PC restarts in Windows. Open apps close, so save your work first.")
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Item { Layout.fillWidth: true }
                    PlasmaComponents.Button {
                        text: root.problem !== "" ? i18n("Close") : i18n("Cancel")
                        onClicked: root.sheetOpen = false
                    }
                    SunButton {
                        speed: root.speed
                        visible: root.problem === ""
                        text: root.asking ? i18n("Restart & Play") : i18n("Restart")
                        onClicked: root.go()
                    }
                }
            }
        }
    }

    // The sun sets: the whole screen fades to night while the PC switches.
    Window {
        id: sunset
        flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        color: "transparent"
        visible: false
        property string title: ""

        function begin(name) {
            title = name
            night.opacity = 0
            disc.y = 17
            showFullScreen()
            fall.restart()
            // If the PC is still here after a while, something is holding it up.
            giveUp.restart()
        }

        Timer {
            id: giveUp
            interval: 45000
            onTriggered: sunset.close()
        }

        Rectangle {
            id: night
            anchors.fill: parent
            color: "#05070E"
            opacity: 0

            Item {
                id: mark
                width: 128
                height: 128
                anchors.centerIn: parent
                anchors.verticalCenterOffset: -40

                Rectangle {
                    id: disc
                    x: 37
                    y: 17
                    width: 54
                    height: 54
                    radius: 27
                    gradient: Gradient {
                        GradientStop { position: 0; color: "#FF8456" }
                        GradientStop { position: 1; color: "#E8431F" }
                    }
                }
                Repeater {
                    model: [[26, 80, 76, 10, 0.9], [35, 95, 54, 8, 0.66], [51, 108, 30, 6.5, 0.42]]
                    Rectangle {
                        x: modelData[0]
                        y: modelData[1]
                        width: modelData[2]
                        height: modelData[3]
                        radius: height / 2
                        color: root.sun
                        opacity: modelData[4]
                        SequentialAnimation on scale {
                            loops: Animation.Infinite
                            running: sunset.visible
                            PauseAnimation { duration: index * 180 }
                            NumberAnimation { to: 1.16; duration: 800; easing.type: Easing.InOutSine }
                            NumberAnimation { to: 1; duration: 800; easing.type: Easing.InOutSine }
                        }
                    }
                }
            }

            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: mark.bottom
                anchors.topMargin: 30
                spacing: 10
                Text {
                    horizontalAlignment: Text.AlignLeft
                    anchors.horizontalCenter: parent.horizontalCenter
                    color: "#FFFFFF"
                    font.family: "Fraunces 72pt SuperSoft"
                    font.weight: Font.Light
                    font.pixelSize: 34
                    text: sunset.title !== "" ? i18n("Opening %1", sunset.title) : i18n("Opening Windows")
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    anchors.horizontalCenter: parent.horizontalCenter
                    color: "#A8FFFFFF"
                    font.pixelSize: 15
                    text: i18n("Restarting in Windows")
                }
            }

            TapHandler { onTapped: sunset.close() }
        }

        ParallelAnimation {
            id: fall
            NumberAnimation { target: night; property: "opacity"; to: 1; duration: Math.round(900 * root.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.4, 0, 0.2, 1, 1, 1] }
            NumberAnimation { target: disc; property: "y"; to: 40; duration: Math.round(1800 * root.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.4, 0, 0.2, 1, 1, 1] }
        }
    }
}
