/*
 * Monet's edit mode: when you add, move or remove widgets, the desktop steps
 * back into a frame of paper (or smoke) on a wash of mist (or smoke), with Add
 * widgets and Done above it. KDE's blurs the whole desktop behind the frame
 * at every change, which is slow wherever the processor draws the screen.
 *
 * Loaded by DesktopEditMode.qml in Plasma's desktop shell. Desktop.qml around
 * it gives root, containment, containmentParent, editModeRect and sidePanel,
 * and reads centerX and centerY to place the desktop it shrinks.
 */
import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Templates as T
import org.kde.kirigami as Kirigami
import org.kde.plasma.extras as PlasmaExtras

Item {
    id: editModeItem

    property real centerX: Math.round(editModeUi.x + editModeUi.width / 2)
    property real centerY: Math.round(editModeUi.y + editModeUi.height / 2)
    property real roundedRootWidth: Math.round(root.width)
    property real roundedRootHeight: Math.round(root.height)
    property bool open: false

    readonly property real speed: Kirigami.Units.longDuration / 200
    // Mist or smoke, the way monet-light set the colors.
    readonly property bool smoke: Kirigami.Theme.backgroundColor.hslLightness < 0.5
    readonly property color ink: smoke ? "#EFECE6" : "#1C1B19"
    readonly property color dim: smoke ? "#B4AEA5" : "#6B665E"
    readonly property color paper: smoke ? "#242321" : "#F3F1EC"
    readonly property color pebble: smoke ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0.11, 0.106, 0.098, 0.06)
    readonly property color hairline: smoke ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(0, 0, 0, 0.09)
    readonly property color lily: smoke ? "#4DB4A0" : "#357F72"

    Component.onCompleted: {
        open = Qt.binding(() => containment.plasmoid.corona.editMode)
    }

    // A wash of mist or smoke over everything.
    Rectangle {
        anchors.fill: parent
        color: editModeItem.smoke ? "#14131A" : "#E6E3DC"
        opacity: editModeItem.open ? 0.86 : 0
        Behavior on opacity { NumberAnimation { duration: Kirigami.Units.longDuration } }
    }

    Item {
        id: editModeUi
        visible: editModeItem.open || xAnim.running
        x: Math.round(editModeItem.open ? editModeRect.x + editModeRect.width / 2 - zoomedWidth / 2 : 0)
        y: Math.round(editModeItem.open ? editModeRect.y + editModeRect.height / 2 - zoomedHeight / 2 + toolBar.height / 2 : 0)
        width: editModeItem.open ? zoomedWidth : editModeItem.roundedRootWidth
        height: editModeItem.open ? zoomedHeight : editModeItem.roundedRootHeight
        property real zoomedWidth: Math.round(root.width * containmentParent.scaleFactor)
        property real zoomedHeight: Math.round(root.height * containmentParent.scaleFactor)

        // The frame: paper or smoke around the desktop, with the bar above it.
        Rectangle {
            id: frame
            x: -10
            y: -toolBar.height - 14
            width: Math.round(parent.width + 20)
            height: Math.round(parent.height + toolBar.height + 24)
            radius: editModeItem.open ? 18 : 0
            color: editModeItem.paper
            border.width: 1
            border.color: editModeItem.hairline
            Behavior on radius { NumberAnimation { duration: Kirigami.Units.longDuration } }

            // The bar's clicks stay on it; the desktop under the frame stays live.
            MouseArea {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: toolBar.height + 14
            }

            RowLayout {
                id: toolBar
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.leftMargin: 16
                anchors.rightMargin: 12
                anchors.topMargin: 8
                spacing: Kirigami.Units.smallSpacing * 2
                opacity: editModeItem.open ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: Kirigami.Units.longDuration } }

                Text {
                    Layout.fillWidth: true
                    text: i18n("Drag a widget to move it. Point at one to resize or remove it.")
                    color: editModeItem.dim
                    elide: Text.ElideRight
                    font.family: "Inter"
                    font.pixelSize: 13
                }
                Pill {
                    id: moreButton
                    text: i18n("More")
                    ink: editModeItem.ink
                    tint: editModeItem.pebble
                    ring: editModeItem.lily
                    speed: editModeItem.speed
                    onClicked: moreMenu.openRelative()
                }
                Pill {
                    visible: !sidePanel.visible
                    text: i18n("Add widgets")
                    ink: editModeItem.ink
                    tint: editModeItem.pebble
                    ring: editModeItem.lily
                    speed: editModeItem.speed
                    onClicked: {
                        const add = containment.plasmoid.internalAction("add widgets")
                        if (add) {
                            add.trigger()
                        }
                    }
                }
                Pill {
                    // The gallery has its own Done while it's open.
                    visible: !sidePanel.visible
                    text: i18n("Done")
                    ink: editModeItem.paper
                    tint: editModeItem.ink
                    ring: editModeItem.lily
                    speed: editModeItem.speed
                    onClicked: containment.plasmoid.corona.editMode = false
                }
            }
        }

        // The rest of what KDE's edit mode offers: panels and desktops.
        PlasmaExtras.Menu {
            id: moreMenu
            visualParent: moreButton
            placement: PlasmaExtras.Menu.BottomPosedLeftAlignedPopup

            PlasmaExtras.MenuItem {
                text: i18n("Add a bar…")
                icon: "list-add"
                onClicked: containment.plasmoid.corona.showAddPanelContextMenu(moreButton.mapToGlobal(0, moreButton.height))
            }
            PlasmaExtras.MenuItem {
                readonly property QtObject manage: containment ? containment.plasmoid.corona.action("manage-containments") : null
                text: i18n("Manage desktops and bars")
                icon: "configure"
                visible: manage ? manage.visible : false
                onClicked: manage.trigger()
            }
        }

        Behavior on x {
            NumberAnimation {
                id: xAnim
                duration: Kirigami.Units.longDuration
                easing.type: Easing.InOutQuad
            }
        }
        Behavior on y {
            NumberAnimation {
                duration: Kirigami.Units.longDuration
                easing.type: Easing.InOutQuad
            }
        }
        Behavior on width {
            NumberAnimation {
                duration: Kirigami.Units.longDuration
                easing.type: Easing.InOutQuad
            }
        }
        Behavior on height {
            NumberAnimation {
                duration: Kirigami.Units.longDuration
                easing.type: Easing.InOutQuad
            }
        }

        // The desktop itself, its corners rounded like the frame's. Clicks go
        // through to the real one Desktop.qml shrinks underneath.
        MultiEffect {
            anchors.fill: parent
            source: containment
            layer.enabled: true
            layer.smooth: true
            layer.effect: Kirigami.ShadowedTexture {
                width: editModeItem.roundedRootWidth
                height: editModeItem.roundedRootHeight
                color: "transparent"
                radius: editModeItem.open ? 12 : 0
                Behavior on radius {
                    NumberAnimation {
                        duration: Kirigami.Units.longDuration
                        easing.type: Easing.InOutQuad
                    }
                }
            }
        }
    }

    // A pill: Monet's buttons, on a pebble of glass, or Done in ink.
    component Pill: T.AbstractButton {
        id: pill
        property color ink
        property color tint
        property color ring
        property real speed: 1
        implicitWidth: label.implicitWidth + 32
        implicitHeight: 34
        activeFocusOnTab: true
        Accessible.name: text
        Keys.onEnterPressed: clicked()
        Keys.onReturnPressed: clicked()
        scale: down ? 0.95 : hovered ? 1.04 : 1
        Behavior on scale { NumberAnimation { duration: Math.round(160 * pill.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }
        background: Rectangle {
            radius: height / 2
            color: pill.tint
            border.width: pill.visualFocus ? 2 : 0
            border.color: pill.ring
        }
        contentItem: Text {
            id: label
            text: pill.text
            color: pill.ink
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.family: "Inter"
            font.pixelSize: 14
            font.weight: Font.DemiBold
        }
    }
}
