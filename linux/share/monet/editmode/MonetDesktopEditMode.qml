import QtQuick
import QtQuick.Layouts
import QtQuick.Templates as T
import org.kde.kirigami as Kirigami
import org.kde.plasma.extras as PlasmaExtras

Item {
    id: editModeItem
    LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
    LayoutMirroring.childrenInherit: true

    property real centerX: root.width / 2
    property real centerY: root.height / 2
    property real roundedRootWidth: Math.round(root.width)
    property real roundedRootHeight: Math.round(root.height)
    property bool open: false
    readonly property bool editingPanel: !!containment?.plasmoid.corona.panelBeingConfigured
        && containment.plasmoid.corona.panelBeingConfigured.screenToFollow === desktop.screenToFollow
    readonly property bool floatingEditorOpen: editingPanel || (sidePanel.visible && !!sidePanel.mainItem?.item?.floatingEditor)
    readonly property bool showToolbar: !editingPanel && !sidePanel.visible

    // Never scale the containment, including between editor windows.
    Binding {
        target: containmentParent
        property: "scaleFactor"
        value: 1
        restoreMode: Binding.RestoreBindingOrValue
    }

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

    // Editing happens on the live, full-size desktop. Only this small toolbar
    // covers it; editor applications never reserve a strip of the screen.
    Item {
        id: editModeUi
        anchors.fill: parent
        Rectangle {
            id: frame
            visible: editModeItem.open && editModeItem.showToolbar
            x: Math.round((parent.width - width) / 2)
            y: 64
            width: Math.min(760, parent.width - 32)
            height: toolBar.implicitHeight + 16
            radius: 16
            color: editModeItem.paper
            border.width: 1
            border.color: editModeItem.hairline
            MouseArea { anchors.fill: parent }
            Flow {
                id: toolBar
                visible: editModeItem.showToolbar
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.leftMargin: 16
                anchors.rightMargin: 12
                anchors.topMargin: 8
                spacing: Kirigami.Units.smallSpacing
                opacity: editModeItem.open ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: Kirigami.Units.longDuration } }

                Text {
                    visible: toolBar.width >= 640
                    horizontalAlignment: Text.AlignLeft
                    width: Math.max(0,toolBar.width - 455); height: 34; verticalAlignment: Text.AlignVCenter
                    text: i18nd("monet", "Drag a widget to move it. Point at one to resize or remove it.")
                    color: editModeItem.dim
                    elide: Text.ElideRight
                    font.family: "Inter"
                    font.pixelSize: 13
                }
                Pill {
                    id: addPanelButton
                    visible: !sidePanel.visible
                    text: i18nd("monet", "Add panel")
                    ink: editModeItem.ink; tint: editModeItem.pebble; ring: editModeItem.lily
                    onClicked: containment.plasmoid.corona.showAddPanelContextMenu(mapToGlobal(0,height))
                }
                Pill {
                    id: moreButton
                    text: i18nd("monet", "More")
                    ink: editModeItem.ink
                    tint: editModeItem.pebble
                    ring: editModeItem.lily
                    speed: editModeItem.speed
                    onClicked: moreMenu.openRelative()
                }
                Pill {
                    visible: !sidePanel.visible
                    text: i18nd("monet", "Add widgets")
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
                    text: i18nd("monet", "Done")
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
                readonly property QtObject manage: containment ? containment.plasmoid.corona.action("manage-containments") : null
                text: i18nd("monet", "Manage desktops and bars")
                icon: "configure"
                visible: manage ? manage.visible : false
                enabled: manage?.enabled ?? false
                onClicked: manage?.trigger()
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
        scale: down ? 0.98 : 1
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
