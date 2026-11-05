import QtQuick
import QtQuick.Window
import org.kde.plasma.core as PlasmaCore
import "../../image/dock" as Monet

Window {
    id: window
    width: 520; height: 240; visible: true
    property bool motionEnabled: true
    property bool dragging: false
    property int clicks: 0
    property int menus: 0
    property int dragStarts: 0
    property int duration: 30
    property int taskCount: 5
    readonly property bool tracking: pointer.current?.hovered ?? false

    Item {
        id: dock
        x: 48; y: 100; width: 320; height: 64
        QtObject {
            id: pointer
            property QtObject current: null
        }
        Repeater {
            model: window.taskCount
            PlasmaCore.ToolTipArea {
                id: task
                required property int index
                objectName: "task" + index
                x: index * 64; width: 64; height: 64
                mainText: "Synthetic application"
                active: true
                Monet.MonetDockHover {
                    id: taskPointer
                    coordinator: pointer
                    trackingEnabled: window.motionEnabled && !window.dragging
                }
                Rectangle {
                    x: 12; y: 12; width: 40; height: 40
                    color: "#357f72"
                    scale: motion.iconScale
                    transform: Translate { y: -motion.lift }
                }
                Monet.MonetDockMotion {
                    id: motion
                    objectName: "motion" + index
                    motionEnabled: window.motionEnabled && !window.dragging
                    hovering: window.tracking
                    duration: window.duration
                    distance: ((pointer.current?.point.scenePosition.x ?? 0)
                        - task.mapToItem(null, task.width / 2, 0).x) / task.width
                }
                TapHandler { onTapped: window.clicks++ }
                TapHandler { acceptedButtons: Qt.RightButton; onTapped: window.menus++ }
                DragHandler {
                    target: null
                    onActiveChanged: {
                        window.dragging = active
                        if (active) window.dragStarts++
                    }
                }
            }
        }
    }
    // Trash has a MouseArea and a tooltip layered above its icon, unlike tasks.
    MouseArea {
        id: trash
        objectName: "trash"
        x: 368; y: 100; width: 64; height: 64
        hoverEnabled: true
        onClicked: window.clicks++
        Rectangle {
            x: 12; y: 12; width: 40; height: 40
            color: "#9275a5"
            scale: trashMotion.iconScale
            transform: Translate { y: -trashMotion.lift }
        }
        Monet.MonetDockMotion {
            id: trashMotion
            objectName: "trashMotion"
            motionEnabled: window.motionEnabled && !window.dragging
            hovering: trashPointer.hovering
            duration: window.duration
            distance: (trashPointer.position.x - trash.width / 2) / trash.width
        }
        PlasmaCore.ToolTipArea {
            anchors.fill: parent; mainText: "Synthetic Trash"
            Monet.MonetDockHover {
                id: trashPointer
                objectName: "trashPointer"
                trackingEnabled: window.motionEnabled && !window.dragging
            }
        }
    }
}
