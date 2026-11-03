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

if __name__=='__main__':apply(Path(sys.argv[1]))
