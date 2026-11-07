#!/usr/bin/python3
"""Small, fail-closed patch to the native Plasma task applet."""
from pathlib import Path
import sys

def replace(path, old, new):
    text=path.read_text()
    if new in text: return
    if text.count(old)!=1:raise ValueError(f'Unsupported task applet source: {path.name}')
    path.write_text(text.replace(old,new))

def prepend(path, anchor, addition):
    # Later insertions may separate this text from its anchor. Match the
    # insertion itself so reapplying the patch cannot duplicate properties.
    if addition in path.read_text(): return
    replace(path, anchor, addition + anchor)

def apply(source):
    applet=source/'applets/taskmanager'
    # Plasma's internal task-manager model is the Home Bar in Monet. Keep the
    # actual System Monitor/Task Manager app distinct in user-facing menus.
    context = applet/'qml/ContextMenu.qml'
    old = 'i18nc("action:inmenu", "&Pin to Task Manager")'
    new = 'i18nd("monet", "Pin to Home Bar")'
    text = context.read_text()
    if new not in text:
        if text.count(old) != 2: raise ValueError('Unsupported dock pin actions')
        context.write_text(text.replace(old, new))
    replace(context, 'i18nc("action:inmenu", "Unpin from Task Manager")',
            'i18nd("monet", "Unpin from Home Bar")')
    replace(context, 'text: configureAction ? configureAction.text : ""',
            'text: configureAction ? i18nd("monet", "Configure Home Bar…") : ""')
    replace(applet/'CMakeLists.txt','        qml/Task.qml','        qml/Task.qml\n        qml/MonetDockMotion.qml\n        qml/MonetDockHover.qml')
    # Standalone build keeps the upstream generated settings in their original folder.
    replace(applet/'CMakeLists.txt','${CMAKE_SOURCE_DIR}/kcms/recentFiles/', '${UPSTREAM_SOURCE}/kcms/recentFiles/')
    prepend(applet/'qml/main.qml','    property Task toolTipOpenedByClick', '''    // Passive hover tracking never takes clicks or grabs away from task controls.
    readonly property bool monetMotionEnabled: iconsOnly && !vertical
        && Plasmoid.location === PlasmaCore.Types.BottomEdge
        && Plasmoid.configuration.taskHoverEffect && !Plasmoid.containment.corona.editMode
        && !dragSource && Kirigami.Units.shortDuration > 0
    readonly property QtObject monetHoverState: QtObject { property QtObject current: null }
    readonly property bool monetHoverActive: monetMotionEnabled && (monetHoverState.current?.hovered ?? false)
    readonly property point monetPointer: monetHoverState.current?.point.scenePosition ?? Qt.point(0, 0)

''')
    prepend(applet/'qml/main.qml', '    property Task toolTipOpenedByClick', '''    // One native launch coordinator is shared with Monet's menu. Older generic
    // installs retain Plasma's normal launch path when the module is absent.
    readonly property QtObject monetLauncher: QtObject {
        id: monetLaunchBridge
        property var client: null
        readonly property var states: client ? client.states : ({})
        function openForLauncher(url, source, newWindow) {
            const id = client ? client.key(String(url)) : "";
            if (!id) return false;
            client.open(id, source, !!newWindow);
            return true;
        }
        Component.onCompleted: {
            try { client = Qt.createQmlObject('import org.monet.launcher 1.0; Launcher {}', monetLaunchBridge, "MonetDockLauncher"); }
            catch (error) { client = null; }
        }
    }

''')
    replace(applet/'qml/code/TaskTools.js',
        'function activateTask(index, model, modifiers, task, plasmoid, tasks, windowViewAvailable) {',
        '''function activateTask(index, model, modifiers, task, plasmoid, tasks, windowViewAvailable) {
    if (tasks.monetLauncher && (model.IsLauncher || model.IsStartup || (modifiers & Qt.ShiftModifier))
            && tasks.monetLauncher.openForLauncher(model.LauncherUrlWithoutIcon, task, !!(modifiers & Qt.ShiftModifier))) {
        return;
    }''')
    replace(applet/'qml/Task.qml', '    id: task\n', '''    id: task

    MonetDockHover {
        id: monetTaskHover
        objectName: "monetTaskHover"
        coordinator: task.tasksRoot.monetHoverState
        trackingEnabled: !task.inPopup && task.tasksRoot.monetMotionEnabled && taskList.rows === 1
    }
''')
    replace(applet/'qml/Task.qml', '    readonly property int pid: model.AppPid', '''    readonly property bool monetOpening: {
        const bridge = task.tasksRoot.monetLauncher;
        const id = bridge.client ? bridge.client.key(String(model.LauncherUrlWithoutIcon)) : "";
        return !!(id && bridge.states[id] && bridge.states[id].state === "starting");
    }
    readonly property int pid: model.AppPid''')
    replace(applet/'qml/Task.qml', 'active: task.model.IsStartup', 'active: task.model.IsStartup || task.monetOpening')
    replace(applet/'qml/Task.qml', '    Accessible.description: {', '''    Accessible.description: {
        if (task.monetOpening) return i18nd("monet", "Starting %1…", model.display);''')
    replace(applet/'qml/Task.qml', '                    tasksModel.requestNewInstance(modelIndex());',
        '''                    if (!task.tasksRoot.monetLauncher.openForLauncher(model.LauncherUrlWithoutIcon, task, true)) {
                        tasksModel.requestNewInstance(modelIndex());
                    }''')
    replace(applet/'qml/ContextMenu.qml', '        onClicked: tasksModel.requestNewInstance(menu.modelIndex)',
        '''        onClicked: {
            const task = menu.visualParent;
            if (!task || !task.tasksRoot.monetLauncher.openForLauncher(menu.get(TaskManager.AbstractTasksModel.LauncherUrlWithoutIcon), task, true)) {
                tasksModel.requestNewInstance(menu.modelIndex);
            }
        }''')
    replace(applet/'qml/Task.qml','        id: iconBox\n', '''        id: iconBox

        MonetDockMotion {
            id: monetMotion
            objectName: "monetDockMotion"
            motionEnabled: !task.inPopup && task.tasksRoot.monetMotionEnabled && taskList.rows === 1
            hovering: task.tasksRoot.monetHoverActive
            duration: Kirigami.Units.shortDuration
            iconHeight: iconBox.height
            distance: {
                // Track native relayout transforms as well as the pointer.
                const layoutX = task.x;
                const movingX = translateTransform.x;
                const center = task.mapToItem(null, task.width / 2, task.height / 2);
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
    (applet/'qml/MonetDockHover.qml').write_bytes(Path(__file__).with_name('MonetDockHover.qml').read_bytes())
    trash = source/'applets/trash'
    replace(trash/'CMakeLists.txt', '        main.qml', '        main.qml\n        MonetDockMotion.qml\n        MonetDockHover.qml')
    replace(trash/'main.qml', 'import QtQuick\n', 'import QtQuick\nimport QtQuick.Layouts\n')
    replace(trash/'main.qml', '    property bool containsAcceptableDrag: false', '''    readonly property bool monetBottomDock: Plasmoid.location === PlasmaCore.Types.BottomEdge
    readonly property bool monetDockMotionEnabled: monetBottomDock
        && !Plasmoid.containment.corona.editMode && !containsAcceptableDrag
        && Kirigami.Units.shortDuration > 0

    property bool containsAcceptableDrag: false''')
    replace(trash/'main.qml', '        activeFocusOnTab: true', '''        // Use the painted full-size icon on the bottom dock, not a 16px action icon.
        Layout.minimumWidth: root.monetBottomDock ? Kirigami.Units.iconSizes.large : 0
        activeFocusOnTab: true''')
    replace(trash/'main.qml', '        PlasmaCore.ToolTipArea {\n', '''        PlasmaCore.ToolTipArea {
            MonetDockHover {
                id: monetTrashHover
                objectName: "monetTrashHover"
                trackingEnabled: root.monetDockMotionEnabled
            }
''')
    replace(trash/'main.qml', '        Kirigami.Icon {\n            source: Plasmoid.icon', '''        Kirigami.Icon {
            id: trashIcon
            roundToIconSize: !root.monetBottomDock
            source: root.monetBottomDock ? (root.hasContents ? "user-trash-full" : "user-trash") : Plasmoid.icon
            MonetDockMotion {
                id: monetMotion
                objectName: "monetDockMotion"
                motionEnabled: root.monetDockMotionEnabled
                hovering: monetTrashHover.hovering
                duration: Kirigami.Units.shortDuration
                iconHeight: Math.min(trashIcon.width, trashIcon.height)
                distance: (monetTrashHover.position.x - mouseArea.width / 2) / Math.max(1, mouseArea.width)
            }
            transform: [
                Scale { origin.x: trashIcon.width / 2; origin.y: trashIcon.height / 2;
                    xScale: monetMotion.iconScale; yScale: monetMotion.iconScale },
                Translate { y: -monetMotion.lift }
            ]''')
    (trash/'MonetDockMotion.qml').write_bytes(Path(__file__).with_name('MonetDockMotion.qml').read_bytes())
    (trash/'MonetDockHover.qml').write_bytes(Path(__file__).with_name('MonetDockHover.qml').read_bytes())

if __name__=='__main__':apply(Path(sys.argv[1]))
