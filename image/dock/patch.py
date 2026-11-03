#!/usr/bin/python3
"""Small, fail-closed patch to the native Plasma task applet."""
from pathlib import Path
import sys

def replace(path, old, new):
    text=path.read_text()
    if new in text: return
    if text.count(old)!=1:raise ValueError(f'Unsupported task applet source: {path.name}')
    path.write_text(text.replace(old,new))

def apply(source):
    applet=source/'applets/taskmanager'
    replace(applet/'CMakeLists.txt','        qml/Task.qml','        qml/Task.qml\n        qml/MonetDockMotion.qml')
    # Standalone build keeps the upstream generated settings in their original folder.
    replace(applet/'CMakeLists.txt','${CMAKE_SOURCE_DIR}/kcms/recentFiles/', '${UPSTREAM_SOURCE}/kcms/recentFiles/')
    replace(applet/'qml/main.qml','    property Task toolTipOpenedByClick', '''    // Passive hover tracking never takes clicks or grabs away from task controls.
    readonly property bool monetMotionEnabled: iconsOnly && !vertical
        && Plasmoid.location === PlasmaCore.Types.BottomEdge
        && Plasmoid.configuration.taskHoverEffect && !Plasmoid.containment.corona.editMode
        && !dragSource && Kirigami.Units.shortDuration > 0
    readonly property bool monetHoverActive: monetDockHover.hovered
    readonly property point monetPointer: monetDockHover.point.position
    HoverHandler {
        id: monetDockHover
        enabled: tasks.monetMotionEnabled
        blocking: false
    }

    property Task toolTipOpenedByClick''')
    replace(applet/'qml/Task.qml','        id: iconBox\n', '''        id: iconBox

        MonetDockMotion {
            id: monetMotion
            motionEnabled: !task.inPopup && task.tasksRoot.monetMotionEnabled && taskList.rows === 1
            hovering: task.tasksRoot.monetHoverActive
            duration: Kirigami.Units.shortDuration
            iconHeight: iconBox.height
            distance: {
                // Read x and width so relayouts also update the mapped center.
                const layoutX = task.x;
                const center = task.mapToItem(task.tasksRoot, task.width / 2, task.height / 2);
                return (task.tasksRoot.monetPointer.x - center.x) / Math.max(1, task.width);
            }
        }
        transform: [
            Scale { origin.x: iconBox.width / 2; origin.y: iconBox.height / 2;
                xScale: monetMotion.iconScale; yScale: monetMotion.iconScale },
            Translate { y: -monetMotion.lift }
        ]
''')
    (applet/'qml/MonetDockMotion.qml').write_bytes(Path(__file__).with_name('MonetDockMotion.qml').read_bytes())
    trash = source/'applets/trash'
    replace(trash/'CMakeLists.txt', '        main.qml', '        main.qml\n        MonetDockMotion.qml')
    replace(trash/'main.qml', 'import QtQuick\n', 'import QtQuick\nimport QtQuick.Layouts\n')
    replace(trash/'main.qml', '    property bool containsAcceptableDrag: false', '''    readonly property bool monetBottomDock: Plasmoid.location === PlasmaCore.Types.BottomEdge
    readonly property bool monetDockMotionEnabled: monetBottomDock
        && !Plasmoid.containment.corona.editMode && !containsAcceptableDrag
        && Kirigami.Units.shortDuration > 0

    property bool containsAcceptableDrag: false''')
    replace(trash/'main.qml', '        activeFocusOnTab: true', '''        // Use the painted full-size icon on the bottom dock, not a 16px action icon.
        Layout.minimumWidth: root.monetBottomDock ? Kirigami.Units.iconSizes.large : 0
        activeFocusOnTab: true''')
    replace(trash/'main.qml', '        Kirigami.Icon {\n            source: Plasmoid.icon', '''        Kirigami.Icon {
            id: trashIcon
            roundToIconSize: !root.monetBottomDock
            source: root.monetBottomDock ? (root.hasContents ? "user-trash-full" : "user-trash") : Plasmoid.icon
            MonetDockMotion {
                id: monetMotion
                motionEnabled: root.monetDockMotionEnabled
                hovering: mouseArea.containsMouse
                duration: Kirigami.Units.shortDuration
                iconHeight: Math.min(trashIcon.width, trashIcon.height)
                distance: (mouseArea.mouseX - mouseArea.width / 2) / Math.max(1, mouseArea.width)
            }
            transform: [
                Scale { origin.x: trashIcon.width / 2; origin.y: trashIcon.height / 2;
                    xScale: monetMotion.iconScale; yScale: monetMotion.iconScale },
                Translate { y: -monetMotion.lift }
            ]''')
    (trash/'MonetDockMotion.qml').write_bytes(Path(__file__).with_name('MonetDockMotion.qml').read_bytes())

if __name__=='__main__':apply(Path(sys.argv[1]))
