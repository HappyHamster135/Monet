/*
 * A room of the Store: a section's apps (or yours, or your Windows'), under its own strip of
 * Monet's painting. They're in the order asked (the most installed, the newest release, or by
 * name), of one kind or all, only the ones Flathub checked if asked; in the most installed
 * order the first three are hung on a podium, numbered.
 */
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../games"

GridView {
    id: shelf
    MouseScroll { view: shelf }
    property var tone
    // The Store's window: banner(), choose(), kindWords, order, kind, checkedOnly.
    property var store
    property string section: ""
    property string name: ""
    property string subtitle: ""
    // Cards, and the kinds there are: [[kind, how many]].
    property var apps: []
    property var kinds: []
    property int columns: 2
    readonly property bool sortable: section !== "windows"
    readonly property bool podium: sortable && section !== "installed" && store.order === "popular"
        && store.kind === "" && apps.length >= 6

    model: podium ? apps.slice(3) : apps
    cellWidth: Math.floor(width / columns)
    cellHeight: 104
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    Kirigami.WheelHandler {
        target: shelf
        filterMouseEvents: !("acceptedButtons" in shelf)
        keyNavigationEnabled: true
        verticalStepSize: 96
    }

    function updated(app) {
        return app.released > 0 ? i18n("Updated %1", new Date(app.released * 1000).toLocaleDateString(Qt.locale(), Locale.ShortFormat)) : ""
    }

    header: Column {
        width: shelf.width - 12
        spacing: 20
        Item { width: 1; height: 8 }
        Strip {
            width: parent.width
            tone: shelf.tone
            picture: shelf.visible ? shelf.store.banner(shelf.section) : ""
            title: shelf.name
            subtitle: shelf.subtitle
        }

        // The order, and only the checked ones: pebbles, as Settings' choices are.
        Flow {
            width: parent.width
            visible: shelf.sortable
            spacing: 10
            Rectangle {
                implicitWidth: orderRow.implicitWidth + 6
                implicitHeight: 36
                width: implicitWidth
                height: implicitHeight
                radius: 18
                color: shelf.tone.wash2
                Accessible.role: Accessible.Grouping
                Accessible.name: i18n("Sort by")
                Row {
                    id: orderRow
                    anchors.centerIn: parent
                    spacing: 2
                    Repeater {
                        model: [["popular", i18n("Popular")], ["updated", i18n("Recently updated")], ["name", i18n("Name")]]
                        Pebble {
                            required property var modelData
                            tone: shelf.tone
                            text: modelData[1]
                            chosen: shelf.store.order === modelData[0]
                            onClicked: shelf.store.order = modelData[0]
                        }
                    }
                }
            }
            Rectangle {
                implicitWidth: checkedRow.implicitWidth + 28
                implicitHeight: 36
                width: implicitWidth
                height: implicitHeight
                radius: 18
                color: shelf.store.checkedOnly ? Qt.rgba(0.302, 0.706, 0.627, shelf.tone.dark ? 0.22 : 0.16)
                    : checkedMouse.containsMouse ? shelf.tone.press : shelf.tone.wash2
                border.width: activeFocus ? 2 : shelf.store.checkedOnly ? 1 : 0
                border.color: shelf.tone.lily
                activeFocusOnTab: true
                Keys.onReturnPressed: shelf.store.checkedOnly = !shelf.store.checkedOnly
                Keys.onSpacePressed: shelf.store.checkedOnly = !shelf.store.checkedOnly
                Behavior on color { ColorAnimation { duration: Math.round(140 * shelf.tone.speed) } }
                Row {
                    id: checkedRow
                    anchors.centerIn: parent
                    spacing: 7
                    Glyph {
                        width: 15
                        height: 15
                        anchors.verticalCenter: parent.verticalCenter
                        path: "M12 3l2.4 1.8 3-.2.9 2.9 2.4 1.8-1 2.8 1 2.8-2.4 1.8-.9 2.9-3-.2L12 21l-2.4-1.8-3 .2-.9-2.9-2.4-1.8 1-2.8-1-2.8 2.4-1.8.9-2.9 3 .2zM8.5 12.2l2.3 2.3 4.7-4.7"
                        color: shelf.tone.lily
                        stroke: 1.8
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        anchors.verticalCenter: parent.verticalCenter
                        text: i18n("Checked by Flathub")
                        color: shelf.tone.ink
                        font.pixelSize: 13
                        font.weight: shelf.store.checkedOnly ? Font.DemiBold : Font.Normal
                    }
                }
                MouseArea {
                    id: checkedMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: shelf.store.checkedOnly = !shelf.store.checkedOnly
                }
                Accessible.role: Accessible.CheckBox
                Accessible.name: i18n("Checked by Flathub")
                Accessible.checked: shelf.store.checkedOnly
                Accessible.onPressAction: shelf.store.checkedOnly = !shelf.store.checkedOnly
            }
        }

        // What kind: all, or one.
        Flow {
            width: parent.width
            visible: shelf.sortable && shelf.kinds.length > 0
            spacing: 6
            Pebble {
                tone: shelf.tone
                plain: true
                text: i18nc("every kind of app, a filter in the Store", "All")
                chosen: shelf.store.kind === ""
                onClicked: shelf.store.kind = ""
            }
            Repeater {
                model: shelf.kinds
                Pebble {
                    required property var modelData
                    tone: shelf.tone
                    plain: true
                    text: shelf.store.kindWords[modelData[0]] || modelData[0]
                    count: modelData[1]
                    chosen: shelf.store.kind === modelData[0]
                    onClicked: shelf.store.kind = shelf.store.kind === modelData[0] ? "" : modelData[0]
                }
            }
        }

        // The three most installed, hung and numbered.
        GridLayout {
            width: parent.width
            visible: shelf.podium
            columns: 3
            columnSpacing: 26
            Repeater {
                model: shelf.podium ? shelf.apps.slice(0, 3) : []
                Framed {
                    required property var modelData
                    required property int index
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.alignment: Qt.AlignTop
                    tone: shelf.tone
                    app: modelData
                    rank: index + 1
                    painting: shelf.store.banner(shelf.section)
                    onChosen: shelf.store.choose(modelData, "flathub")
                }
            }
        }
        Item { width: 1; height: 2 }
    }

    delegate: Item {
        required property var modelData
        width: shelf.cellWidth
        height: shelf.cellHeight
        AppCard {
            anchors.fill: parent
            anchors.rightMargin: 12
            anchors.bottomMargin: 12
            tone: shelf.tone
            kind: shelf.section === "windows" ? "windows" : "flathub"
            app: modelData
            note: shelf.store.order === "updated" ? shelf.updated(modelData) : ""
            onChosen: shelf.store.choose(modelData, kind)
        }
    }

    footer: Item {
        width: shelf.width - 12
        height: shelf.count === 0 && !shelf.podium ? 120 : 32
        Text {
            anchors.centerIn: parent
            visible: shelf.count === 0 && !shelf.podium && shelf.section !== "installed"
            text: i18n("No apps here yet.")
            color: shelf.tone.dim
            font.pixelSize: 14
        }
    }
}
