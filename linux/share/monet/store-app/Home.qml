/*
 * The Store's front page, hung like a gallery: today's pick on its painting with a placard to
 * install it from, then a room for each of Monet's picks (a strip of the painting, the first
 * apps framed, the rest listed), the apps installed most this month, and Fresh paint: apps
 * people use with a release in the last few weeks.
 */
import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../games"

Flickable {
    id: home
    MouseScroll { view: home }
    property var tone
    // The Store's window: banner(), choose(), openApp(), working, rowWords.
    property var store
    // shop.home(): {rows, today, top, fresh}.
    property var shown: ({ rows: [], today: null, top: [], fresh: [] })
    // Cards across, in a list.
    property int columns: 2
    // Framed apps across.
    readonly property int hung: Math.max(1, Math.min(3, Math.floor((width - 40) / 280)))

    contentHeight: column.implicitHeight + 56
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    // A wheel's turn glides, as everywhere in Monet's apps.
    Kirigami.WheelHandler {
        target: home
        filterMouseEvents: !("acceptedButtons" in home)
        keyNavigationEnabled: true
        verticalStepSize: 96
    }

    function updated(app) {
        return app.released > 0 ? i18n("Updated %1", new Date(app.released * 1000).toLocaleDateString(Qt.locale(), Locale.ShortFormat)) : ""
    }

    Column {
        id: column
        x: 32
        y: 28
        width: home.width - 64
        spacing: 44

        // Today's pick: its screenshot hung on the painting, a placard beside it.
        Item {
            id: hero
            readonly property var app: home.shown.today
            readonly property bool wide: width > 760
            readonly property bool busy: app !== null && app !== undefined
                && (app.state === "working" || home.store.working[app.id] !== undefined)
            visible: app !== null && app !== undefined
            width: parent.width
            height: visible ? Math.round(Math.min(Math.max(width * 0.36, 300), 420)) : 0

            Rectangle {
                anchors.fill: parent
                radius: 20
                clip: true
                color: home.tone.wash2
                Image {
                    anchors.fill: parent
                    source: hero.app ? home.store.banner(hero.app.section) : ""
                    fillMode: Image.PreserveAspectCrop
                    sourceSize.width: 1800
                    asynchronous: true
                }
            }

            Item {
                id: heroShot
                visible: hero.wide
                anchors.right: parent.right
                anchors.rightMargin: 40
                anchors.verticalCenter: parent.verticalCenter
                height: parent.height - 72
                width: Math.min(Math.round(height * 1.6), Math.round(parent.width * 0.56))
                scale: hungMouse.containsMouse ? 1.01 : 1
                Behavior on scale { NumberAnimation { duration: Math.round(240 * home.tone.speed); easing.type: Easing.OutCubic } }
                Rectangle {
                    id: heroMat
                    anchors.fill: parent
                    radius: 8
                    color: home.tone.dark ? "#34322F" : "#FFFFFF"
                    visible: false
                }
                MultiEffect {
                    source: heroMat
                    anchors.fill: heroMat
                    shadowEnabled: true
                    shadowColor: "#000000"
                    shadowOpacity: 0.38
                    shadowBlur: 1.0
                    shadowVerticalOffset: 14
                }
                Image {
                    anchors.fill: parent
                    anchors.margins: 8
                    source: hero.app ? hero.app.picture : ""
                    fillMode: Image.PreserveAspectCrop
                    verticalAlignment: Image.AlignTop
                    sourceSize.width: 1280
                    asynchronous: true
                }
                MouseArea {
                    id: hungMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: home.store.openApp(hero.app.id)
                }
            }

            Rectangle {
                id: heroCardShape
                anchors.fill: heroCard
                radius: 14
                color: home.tone.paper
                visible: false
            }
            MultiEffect {
                source: heroCardShape
                anchors.fill: heroCardShape
                shadowEnabled: true
                shadowColor: "#000000"
                shadowOpacity: home.tone.dark ? 0.5 : 0.2
                shadowBlur: 0.8
                shadowVerticalOffset: 6
            }
            Rectangle {
                id: heroCard
                anchors.left: parent.left
                anchors.leftMargin: 32
                anchors.verticalCenter: parent.verticalCenter
                width: hero.wide ? Math.min(400, parent.width - heroShot.width - 40 - 32 - 32) : parent.width - 64
                height: heroColumn.implicitHeight + 48
                radius: 14
                color: home.tone.paper
                border.width: 1
                border.color: home.tone.line
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: home.store.openApp(hero.app.id)
                }
                ColumnLayout {
                    id: heroColumn
                    x: 24
                    y: 24
                    width: heroCard.width - 48
                    spacing: 6
                    RowLayout {
                        spacing: 10
                        Image {
                            Layout.preferredWidth: 40
                            Layout.preferredHeight: 40
                            source: hero.app ? hero.app.icon : ""
                            sourceSize: Qt.size(80, 80)
                            fillMode: Image.PreserveAspectFit
                            asynchronous: true
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            Layout.fillWidth: true
                            text: i18n("Today's pick")
                            color: home.tone.lily
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                            font.letterSpacing: 0.8
                            font.capitalization: Font.AllUppercase
                            elide: Text.ElideRight
                        }
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        Layout.topMargin: 4
                        text: hero.app ? hero.app.name : ""
                        textFormat: Text.PlainText
                        color: home.tone.ink
                        font.family: "Fraunces 72pt SuperSoft"
                        font.weight: Font.Light
                        font.pixelSize: 34
                        wrapMode: Text.Wrap
                        maximumLineCount: 2
                        elide: Text.ElideRight
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        text: hero.app ? hero.app.summary : ""
                        textFormat: Text.PlainText
                        color: home.tone.dim
                        font.pixelSize: 15
                        wrapMode: Text.Wrap
                        maximumLineCount: 3
                        elide: Text.ElideRight
                    }
                    RowLayout {
                        Layout.topMargin: 12
                        spacing: 10
                        SunButton {
                            visible: hero.app !== null && hero.app.state === "get" && !hero.busy
                            speed: home.tone.speed
                            size: 14
                            text: i18n("Install")
                            onClicked: shop.install(hero.app.id)
                        }
                        Pill {
                            visible: hero.app !== null && (hero.app.state === "installed" || hero.app.state === "built-in") && !hero.busy
                            tone: home.tone
                            kind: "lily"
                            text: i18n("Open")
                            onClicked: shop.open(hero.app.id)
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            visible: hero.busy
                            text: i18n("Working on it…")
                            color: home.tone.lily
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                    }
                }
            }
        }

        // A room for each of Monet's picks; the chart after the first, Fresh paint after the third.
        Repeater {
            model: home.shown.rows
            Column {
                id: room
                required property var modelData
                required property int index
                readonly property var hungApps: modelData.apps.slice(0, home.hung)
                readonly property var listed: modelData.apps.slice(home.hung)
                width: column.width
                spacing: 26

                Strip {
                    width: parent.width
                    tone: home.tone
                    picture: home.store.banner(room.modelData.id)
                    title: (home.store.rowWords[room.modelData.id] || [room.modelData.id])[0]
                    subtitle: (home.store.rowWords[room.modelData.id] || ["", ""])[1]
                }
                GridLayout {
                    width: parent.width
                    columns: home.hung
                    columnSpacing: 26
                    rowSpacing: 26
                    Repeater {
                        model: room.hungApps
                        Framed {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            Layout.alignment: Qt.AlignTop
                            tone: home.tone
                            app: modelData
                            painting: home.store.banner(room.modelData.id)
                            onChosen: home.store.choose(modelData, "flathub")
                        }
                    }
                }
                // The rest of the room: small works, side by side.
                GridLayout {
                    width: parent.width
                    visible: room.listed.length > 0
                    columns: Math.max(2, Math.floor((width + 12) / 138))
                    columnSpacing: 12
                    rowSpacing: 12
                    Repeater {
                        model: room.listed
                        Tile {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            tone: home.tone
                            app: modelData
                            onChosen: home.store.choose(modelData, "flathub")
                        }
                    }
                }

                // What people install most: numbered, as a chart is.
                Rectangle {
                    width: parent.width
                    visible: room.index === 0 && home.shown.top.length > 0
                    height: visible ? chart.implicitHeight + 52 : 0
                    radius: 20
                    color: home.tone.wash
                    border.width: 1
                    border.color: home.tone.line
                    ColumnLayout {
                        id: chart
                        x: 28
                        y: 26
                        width: parent.width - 56
                        spacing: 14
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            text: i18n("Most installed this month")
                            color: home.tone.ink
                            font.family: "Fraunces 72pt SuperSoft"
                            font.weight: Font.Light
                            font.pixelSize: 26
                        }
                        GridLayout {
                            id: ranks
                            Layout.fillWidth: true
                            columns: width > 640 ? 2 : 1
                            rows: Math.ceil(home.shown.top.length / columns)
                            flow: GridLayout.TopToBottom
                            columnSpacing: 28
                            rowSpacing: 2
                            Repeater {
                                model: home.shown.top
                                Rectangle {
                                    id: ranked
                                    required property var modelData
                                    required property int index
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    Layout.preferredHeight: 62
                                    radius: 12
                                    color: rankMouse.containsMouse ? home.tone.wash2 : "transparent"
                                    border.width: activeFocus ? 2 : 0
                                    border.color: home.tone.lily
                                    activeFocusOnTab: true
                                    Keys.onReturnPressed: home.store.choose(modelData, "flathub")
                                    Keys.onSpacePressed: home.store.choose(modelData, "flathub")
                                    Behavior on color { ColorAnimation { duration: Math.round(140 * home.tone.speed) } }
                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 6
                                        anchors.rightMargin: 12
                                        spacing: 14
                                        Text {
                                            Layout.preferredWidth: 40
                                            horizontalAlignment: Text.AlignRight
                                            text: (ranked.index + 1).toLocaleString(Qt.locale(), "f", 0)
                                            color: ranked.index < 3 ? home.tone.sun : home.tone.ochre
                                            font.family: "Fraunces 72pt SuperSoft"
                                            font.weight: Font.Light
                                            font.pixelSize: 32
                                            font.features: ({ "tnum": 1 })
                                        }
                                        Image {
                                            Layout.preferredWidth: 42
                                            Layout.preferredHeight: 42
                                            source: ranked.modelData.icon || ""
                                            sourceSize: Qt.size(84, 84)
                                            fillMode: Image.PreserveAspectFit
                                            asynchronous: true
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 1
                                            Text {
                                                horizontalAlignment: Text.AlignLeft
                                                Layout.fillWidth: true
                                                text: ranked.modelData.name
                                                textFormat: Text.PlainText
                                                color: home.tone.ink
                                                font.pixelSize: 14
                                                font.weight: Font.DemiBold
                                                elide: Text.ElideRight
                                            }
                                            Text {
                                                horizontalAlignment: Text.AlignLeft
                                                Layout.fillWidth: true
                                                text: ranked.modelData.state === "installed" ? i18n("Installed")
                                                    : ranked.modelData.state === "built-in" ? i18n("Part of Monet") : ranked.modelData.summary
                                                textFormat: Text.PlainText
                                                color: ranked.modelData.state === "get" ? home.tone.dim : home.tone.lily
                                                font.pixelSize: 12
                                                elide: Text.ElideRight
                                            }
                                        }
                                    }
                                    MouseArea {
                                        id: rankMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: home.store.choose(ranked.modelData, "flathub")
                                    }
                                    Accessible.role: Accessible.Button
                                    Accessible.name: (index + 1) + ". " + modelData.name
                                    Accessible.onPressAction: home.store.choose(modelData, "flathub")
                                }
                            }
                        }
                    }
                }

                // Fresh paint: on a band of brushstrokes.
                Rectangle {
                    width: parent.width
                    visible: room.index === 2 && home.shown.fresh.length > 0
                    height: visible ? freshColumn.implicitHeight + 56 : 0
                    radius: 20
                    clip: true
                    color: home.tone.wash
                    border.width: 1
                    border.color: home.tone.line
                    Image {
                        anchors.fill: parent
                        source: home.store.texture
                        fillMode: Image.Tile
                        opacity: home.tone.dark ? 0.08 : 0.14
                    }
                    ColumnLayout {
                        id: freshColumn
                        x: 28
                        y: 28
                        width: parent.width - 56
                        spacing: 4
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            text: i18n("Fresh paint")
                            color: home.tone.ink
                            font.family: "Fraunces 72pt SuperSoft"
                            font.weight: Font.Light
                            font.pixelSize: 26
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            Layout.fillWidth: true
                            Layout.bottomMargin: 18
                            text: i18n("Updated in the last few weeks.")
                            color: home.tone.dim
                            font.pixelSize: 13
                            wrapMode: Text.Wrap
                        }
                        GridLayout {
                            Layout.fillWidth: true
                            columns: home.hung
                            columnSpacing: 26
                            rowSpacing: 26
                            Repeater {
                                model: home.shown.fresh.slice(0, home.hung * 2)
                                Framed {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    Layout.preferredWidth: 1
                                    Layout.alignment: Qt.AlignTop
                                    tone: home.tone
                                    app: modelData
                                    note: home.updated(modelData)
                                    painting: home.store.banner(modelData.section)
                                    onChosen: home.store.choose(modelData, "flathub")
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
