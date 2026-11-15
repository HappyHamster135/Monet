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

def patch_audio(applet):
    prepend(applet/'qml/PulseAudio.qml', '    signal streamsChanged()', '''    readonly property MonetAppVolume monetVolume: MonetAppVolume {
        normalVolume: pulseAudio.normalVolume
    }

''')
    prepend(applet/'qml/PulseAudio.qml', '            function mute(): void {', '''            // Browser players replace streams between tracks, often with an
            // explicit initial volume. Restore once, when the stream starts
            // playing, so pausing never undoes a change made in another mixer.
            property bool monetRestored: false
            property double monetRestoredAt: 0
            function monetRestore(again: bool): void {
                if ((monetRestored && !again) || !pulseAudio.monetVolume.restore(delegate)) return;
                monetRestored = true;
                monetRestoredAt = Date.now();
            }
            onCorkedChanged: if (!corked) Qt.callLater(() => delegate.monetRestore(false))
            Component.onCompleted: Qt.callLater(() => delegate.monetRestore(false))
            // Later changes from any mixer become the app's level. The short
            // wait skips a player setting its own level as it starts.
            onVolumeChanged: if (monetRestored && Date.now() - monetRestoredAt > 1000)
                pulseAudio.monetVolume.follow(delegate, pulseAudio.findStreamsFn(other => other.monetRestored))

''')
    prepend(applet/'qml/PulseAudio.qml', '            function mute(): void {', '''            // Client metadata can arrive after the stream was created or uncorked.
            readonly property string monetIdentity: pulseAudio.monetVolume.key(delegate)
            onMonetIdentityChanged: Qt.callLater(() => delegate.monetRestore(true))

''')
    replace(applet/'qml/ToolTipInstance.qml', '                    stream.model.Volume = v',
            '''                    pulseAudio.item.monetVolume.remember(stream, Math.max(from, value))
                    stream.model.Volume = v''')
    (applet/'qml/MonetAppVolume.qml').write_bytes(Path(__file__).with_name('MonetAppVolume.qml').read_bytes())

def apply(source):
    applet=source/'applets/taskmanager'
    patch_audio(applet)
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
            'text: configureAction ? i18nd("monet", "App behavior…") : ""')
    prepend(context, '    PlasmaExtras.MenuItem {\n        property PlasmaCore.Action configureAction:', '''    PlasmaExtras.MenuItem {
        text: i18nd("monet", "Task Manager")
        icon: "utilities-system-monitor"
        onClicked: backend.openMonetTaskManager()
    }

''')
    backend = applet/'backend.cpp'
    prepend(backend, 'void Backend::setActionGroup(QAction *action) const', '''void Backend::openMonetTaskManager() const
{
    const auto service = KService::serviceByStorageId(QStringLiteral("org.kde.plasma-systemmonitor.desktop"));
    if (!service) {
        return;
    }
    auto *job = new KIO::ApplicationLauncherJob(service);
    auto *delegate = new KNotificationJobUiDelegate;
    delegate->setAutoErrorHandlingEnabled(true);
    job->setUiDelegate(delegate);
    job->start();
}

''')
    prepend(applet/'backend.h', '    Q_INVOKABLE QRect globalRect',
            '    Q_INVOKABLE void openMonetTaskManager() const;\n')
    prepend(applet/'qml/main.qml', '    // For making a bottom to top layout', '''    Plasmoid.contextualActions: [
        PlasmaCore.Action {
            id: taskManagerAction
            text: i18nd("monet", "Task Manager")
            icon.name: "utilities-system-monitor"
            onTriggered: backend.openMonetTaskManager()
        }
    ]
    Plasmoid.onContextualActionsAboutToShow: {
        taskManagerAction.visible = !Plasmoid.containment?.internalAction("monet-task-manager")
    }

''')
    prepend(backend, '#include <QAction>\n',
            '#include <QCache>\n#include <QIcon>\n#include <QPainter>\n#include <QRegularExpression>\n')
    prepend(backend, 'QVector<Backend *> Backend::s_instances;',
            '#include "MonetTaskIcon.inc"\n\n')
    prepend(applet/'backend.h', '    Q_INVOKABLE QRect globalRect',
            '    Q_INVOKABLE QIcon monetTaskIcon(const QString &appId, const QIcon &decoration) const;\n\n')
    prepend(applet/'backend.h', '#include <QObject>\n', '#include <QIcon>\n')
    (applet/'MonetTaskIcon.inc').write_bytes(Path(__file__).with_name('MonetTaskIcon.inc').read_bytes())
    replace(applet/'qml/Task.qml', 'source: task.model.decoration',
            'source: task.monetIcon')
    replace(applet/'qml/Task.qml', 'mainItem.icon = Qt.binding(() => model.decoration);',
            'mainItem.icon = Qt.binding(() => task.monetIcon);')
    prepend(applet/'qml/Task.qml', '    readonly property bool isIcon:',
            '    readonly property var monetIcon: backend.monetTaskIcon(appId, model.decoration)\n')
    # Icon alignment is independent of the panel's alignment on the screen.
    prepend(applet/'main.xml', '    <entry name="iconSpacing" type="Int">', '''    <entry name="monetIconAlignment" type="String">
      <label>Place the app icons at the start or center of their available space.</label>
      <default>start</default>
    </entry>
''')
    replace(applet/'qml/main.qml', '''            anchors {
                left: parent.left
                top: parent.top
            }

            height: taskList.height''', '''            anchors {
                left: !tasks.vertical && Plasmoid.configuration.monetIconAlignment === "center" ? undefined : parent.left
                top: tasks.vertical && Plasmoid.configuration.monetIconAlignment === "center" ? undefined : parent.top
                horizontalCenter: !tasks.vertical && Plasmoid.configuration.monetIconAlignment === "center" ? parent.horizontalCenter : undefined
                verticalCenter: tasks.vertical && Plasmoid.configuration.monetIconAlignment === "center" ? parent.verticalCenter : undefined
            }

            height: taskList.height''')
    replace(context, 'text: editModeAction ? editModeAction.text : ""',
            'text: editModeAction ? i18nd("monet", "Customize Home Bar…") : ""')
    replace(applet/'CMakeLists.txt','        qml/Task.qml','        qml/Task.qml\n        qml/MonetDockMotion.qml\n        qml/MonetDockHover.qml\n        qml/MonetAppVolume.qml')
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
