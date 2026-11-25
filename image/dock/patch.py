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
    pulse = applet/'qml/PulseAudio.qml'
    prepend(pulse, '    signal streamsChanged()', '''    readonly property MonetAppVolume monetVolume: MonetAppVolume {
        normalVolume: pulseAudio.normalVolume
        // The Home Bar's open windows, for a window's own level.
        windows: () => typeof tasks !== "undefined" && tasks.monetWindows ? tasks.monetWindows() : []
        parentOf: pid => typeof backend !== "undefined" ? backend.parentPid(pid) : -1
    }

    // A group tooltip's windows with the streams each plays ({window id:
    // [streams]}), or null when the app's sound can't be told apart by window.
    function monetByWindow(streams: var, ids: var): var {
        const all = monetVolume.openWindows();
        const pids = all.filter(window => ids.includes(window.id)).map(window => window.pid);
        // Plasma looks for a group's streams by its first window's process.
        // The other windows' own processes play too.
        const more = findStreamsFn(stream => !stream.portalAppId && stream.pid > 0
            && pids.includes(stream.pid) && !streams.includes(stream));
        return monetVolume.byWindow(streams.concat(more), ids, all);
    }

''')
    prepend(pulse, '            function mute(): void {', '''            // Browser players replace streams between tracks, often with an
            // explicit initial volume. Restore once, when the stream starts
            // playing, so pausing never undoes a change made in another mixer.
            property bool monetRestored: false
            property double monetRestoredAt: 0
            // The window whose own level the stream has ("": the app's).
            property string monetWindow: ""
            function monetRestore(again: bool): void {
                if (monetRestored && !again) return;
                const before = volume;
                const level = pulseAudio.monetVolume.level(delegate);
                if (!pulseAudio.monetVolume.restore(delegate, level)) return;
                if (level >= 0 && Math.abs(Math.round(level * pulseAudio.normalVolume) - before) >= 2)
                    monetSeen(before);
                monetRestored = true;
                monetRestoredAt = Date.now();
                monetWindow = pulseAudio.monetVolume.windowOf(delegate)?.id ?? "";
                monetRetries = 0;
            }
            onCorkedChanged: if (!corked) Qt.callLater(() => delegate.monetRestored ? delegate.monetTrackChanged() : delegate.monetRestore(false))
            Component.onCompleted: Qt.callLater(() => delegate.monetRestore(false))
            // Later changes from any mixer become the level the Home Bar
            // keeps; the player's own changes don't. As it starts, a player
            // sets its own level, which the sound server applies only once
            // the stream is set up, sometimes after the restore above. And
            // players that keep one stream for every track (Spotify) put
            // their own level back on it when the next track starts. Both
            // times, put the kept level back (a few times at most). Another
            // mixer's change waits a moment first, in case the player says
            // only afterwards that a new track started.
            property int monetRetries: 0
            property double monetTrackAt: 0
            // Levels the stream had besides the Home Bar's: the player's own
            // and other mixers'. A player only goes back to one of those. A
            // new stream can show 0 until the sound server says its level.
            property var monetSeenLevels: []
            function monetSeen(level: int): void {
                if (level > 0 && !monetSeenLevels.some(seen => Math.abs(seen - level) < 2))
                    monetSeenLevels = monetSeenLevels.concat([level]).slice(-6);
            }
            // The player started another track, or played again after a pause.
            function monetTrackChanged(): void {
                if (!monetRestored) return;
                monetTrackAt = Date.now();
                monetRetries = 0;
                if (monetFollowLater.running) {
                    monetFollowLater.stop();
                    monetJudge();
                }
            }
            function monetPutBack(): void {
                if (monetRetries >= 5) return;
                monetRetries++;
                monetSeen(volume);
                Qt.callLater(() => pulseAudio.monetVolume.restore(delegate));
            }
            function monetJudge(): void {
                if (!pulseAudio.monetVolume.moved(delegate)) return;
                if (Date.now() - monetTrackAt <= 3000
                        && (!monetSeenLevels.length || monetSeenLevels.some(seen => Math.abs(seen - volume) < 2))) {
                    monetPutBack();
                } else {
                    monetSeen(volume);
                    pulseAudio.monetVolume.follow(delegate, pulseAudio.findStreamsFn(other => other.monetRestored));
                }
            }
            readonly property Timer monetFollowLater: Timer {
                interval: 1500
                onTriggered: delegate.monetJudge()
            }
            onVolumeChanged: {
                if (!monetRestored) return;
                if (!pulseAudio.monetVolume.moved(delegate)) {
                    monetFollowLater.stop();
                } else if (Date.now() - monetRestoredAt <= 1000) {
                    monetPutBack();
                } else if (Date.now() - monetTrackAt <= 3000) {
                    monetJudge();
                } else {
                    monetFollowLater.restart();
                }
            }

''')
    prepend(pulse, '            function mute(): void {', '''            // Client metadata can arrive after the stream was created or uncorked.
            readonly property string monetIdentity: pulseAudio.monetVolume.key(delegate)
            onMonetIdentityChanged: Qt.callLater(() => delegate.monetRestore(true))
            // A browser names a tab's stream after the page, which can tell
            // only then which window it plays for.
            readonly property string monetName: model.Name ?? ""
            onMonetNameChanged: if (monetRestored) Qt.callLater(() => {
                if ((pulseAudio.monetVolume.windowOf(delegate)?.id ?? "") !== delegate.monetWindow) delegate.monetRestore(true);
            })

''')
    # The open windows, for a window's own level.
    prepend(applet/'qml/main.qml', '    property Task toolTipOpenedByClick', '''    // Every open window, for a window's own Home Bar volume: [{id, pid, appId, title}].
    function monetWindows(): var {
        const found = [];
        const add = index => {
            if (!tasksModel.data(index, TaskManager.AbstractTasksModel.IsWindow)) return;
            const ids = tasksModel.data(index, TaskManager.AbstractTasksModel.WinIdList) ?? [];
            found.push({
                id: String(ids[0] ?? ""),
                pid: Number(tasksModel.data(index, TaskManager.AbstractTasksModel.AppPid) ?? 0),
                appId: String(tasksModel.data(index, TaskManager.AbstractTasksModel.AppId) ?? "").replace(/\\.desktop$/, ""),
                title: String(tasksModel.data(index, Qt.DisplayRole) ?? ""),
            });
        };
        for (let row = 0; row < tasksModel.count; ++row) {
            const index = tasksModel.makeModelIndex(row);
            const children = tasksModel.rowCount(index);
            if (children > 0) {
                for (let child = 0; child < children; ++child) add(tasksModel.makeModelIndex(row, child));
            } else {
                add(index);
            }
        }
        return found;
    }

''')
    # A new track on a player that keeps its stream.
    prepend(applet/'qml/Task.qml', '    function toggleMuted(): void {', '''    // Players that keep one stream for every track (Spotify) put their own
    // level back on it when the next track starts. Tell the app's streams,
    // so the Home Bar keeps its level.
    property int monetPlayers: 0
    readonly property var monetPlayer: {
        task.monetPlayers;
        return task.isWindow ? mpris2Source.playerForLauncherUrl(model.LauncherUrlWithoutIcon, model.AppPid) : null;
    }
    Connections {
        target: mpris2Source
        function onRowsInserted(): void { task.monetPlayers++; }
        function onRowsRemoved(): void { task.monetPlayers++; }
    }
    Connections {
        target: task.monetPlayer
        ignoreUnknownSignals: true
        function onTrackChanged(): void { task.monetTrackChanged(); }
        function onArtistChanged(): void { task.monetTrackChanged(); }
    }
    function monetTrackChanged(): void {
        task.audioStreams.forEach(stream => stream.monetTrackChanged?.());
    }

''')
    # A slider for each window that plays sound, when that can be told.
    delegate = applet/'qml/ToolTipDelegate.qml'
    prepend(delegate, '                // Required to know whether to display the media player buttons on the first window or not',
            '''                // Monet: each window with the streams it plays, when every
                // one of the app's streams can be told apart by window.
                readonly property var monetWindowStreams: {
                    const pa = pulseAudio.item;
                    const task = toolTipDelegate.parentTask;
                    if (!pa?.monetByWindow || !task?.tooltipControlsEnabled) return null;
                    const ids = [];
                    for (let i = 0; i < model.items.count; ++i) {
                        const item = model.items.get(i).model;
                        void item.display; // A new title can name another window.
                        ids.push(String(item.WinIdList?.[0] ?? ""));
                    }
                    return pa.monetByWindow(task.audioStreams, ids);
                }

''')
    replace(delegate, '                    hasTrackInATitle: groupToolTipListView.hasTrackInATitle\n',
            '''                    hasTrackInATitle: groupToolTipListView.hasTrackInATitle
                    monetWindowStreams: groupToolTipListView.monetWindowStreams
''')
    tooltip = applet/'qml/ToolTipInstance.qml'
    # The title and the thumbnail select the same window. The handler stays
    # behind the header controls so the close button keeps its own click.
    replace(tooltip, 'id: headerHoverHandler\n            active: (root.index !== -1) && !Plasmoid.configuration.showToolTips',
            'id: headerHoverHandler\n            active: root.index !== -1')
    replace(tooltip, '// make the header clickable if image tooltips are disabled (and thus there is no other clickable area that activates the window)',
            '// The title selects the window even when a thumbnail is visible.')
    replace(tooltip, '                PlasmaComponents3.ToolTip.text: i18nc("@info:tooltip Close this window", "Close window")',
            '''                text: i18nc("@info:tooltip Close this window", "Close window")
                display: PlasmaComponents3.ToolButton.IconOnly
                Accessible.name: closeButton.text
                PlasmaComponents3.ToolTip.text: closeButton.text''')
    prepend(tooltip, '    property bool hasTrackInATitle: false', '''    // Monet: when each of the app's streams plays for one window, every
    // window that plays sound has its own slider. Otherwise the app has one.
    property var monetWindowStreams: null
    readonly property var monetStreams: monetWindowStreams
        ? (monetWindowStreams[String(thumbnailSourceItem.winId)] ?? []) : null
    readonly property var monetAudioStreams: monetStreams ?? (toolTipDelegate.parentTask?.audioStreams ?? [])
    readonly property bool monetMuted: monetStreams
        ? monetStreams.length > 0 && monetStreams.every(stream => stream.muted)
        : (toolTipDelegate.parentTask?.muted ?? false)
    readonly property string monetName: monetStreams ? root.title : (toolTipDelegate.parentTask?.appName ?? "")
    function monetToggleMuted(): void {
        if (!monetStreams) {
            toolTipDelegate.parentTask.toggleMuted();
        } else if (monetMuted) {
            monetStreams.forEach(stream => stream.unmute());
        } else {
            monetStreams.forEach(stream => stream.mute());
        }
    }
    function monetRemember(stream: var, value: real): void {
        if (monetStreams) {
            pulseAudio.item.monetVolume.rememberWindow(String(thumbnailSourceItem.winId), stream, value);
        } else {
            pulseAudio.item.monetVolume.remember(stream, value);
        }
    }

''')
    replace(tooltip, '''             && toolTipDelegate.parentTask.hasAudioStream
             // Only load for one entry, as the controls only apply to one window.
             // If this is changed in the future, test for index != -1 to avoid loading
             // when the instance is going to be destroyed
             && ((hasTrackInATitle && albumArtImage.available) || (!hasTrackInATitle && root.index == 0))
''', '''             && (root.monetStreams ? root.monetStreams.length > 0 && root.index !== -1
             : toolTipDelegate.parentTask.hasAudioStream
             // Only load for one entry, as the controls only apply to one window.
             // If this is changed in the future, test for index != -1 to avoid loading
             // when the instance is going to be destroyed
             && ((hasTrackInATitle && albumArtImage.available) || (!hasTrackInATitle && root.index == 0)))
''')
    replace(tooltip, 'onClicked: toolTipDelegate.parentTask.toggleMuted()', 'onClicked: root.monetToggleMuted()')
    replace(tooltip, 'checked: toolTipDelegate.parentTask.muted', 'checked: root.monetMuted')
    replace(tooltip, '"Unmute %1", toolTipDelegate.parentTask.appName)', '"Unmute %1", root.monetName)')
    replace(tooltip, '"Mute %1", toolTipDelegate.parentTask.appName)', '"Mute %1", root.monetName)')
    replace(tooltip, '"Adjust volume for %1", toolTipDelegate.parentTask.appName)', '"Adjust volume for %1", root.monetName)')
    replace(tooltip, 'readonly property int loudestVolume: toolTipDelegate.parentTask.audioStreams',
            'readonly property int loudestVolume: root.monetAudioStreams')
    replace(tooltip, 'opacity: toolTipDelegate.parentTask.muted ? 0.5 : 1', 'opacity: root.monetMuted ? 0.5 : 1')
    replace(tooltip, 'onMoved: toolTipDelegate.parentTask.audioStreams.forEach((stream) => {',
            'onMoved: root.monetAudioStreams.forEach((stream) => {')
    replace(tooltip, '                    stream.model.Volume = v',
            '''                    root.monetRemember(stream, Math.max(from, value))
                    stream.model.Volume = v''')
    replace(tooltip, 'readonly property int displayValue: Math.round(value / to * 100)',
            'readonly property int displayValue: Math.round(value / pulseAudio.item.normalVolume * 100)')
    replace(tooltip, 'to: pulseAudio.item.normalVolume\n                value: loudestVolume\n                stepSize: to / 100',
            'to: 2 * pulseAudio.item.normalVolume\n                value: loudestVolume\n                stepSize: pulseAudio.item.normalVolume / 100')
    prepend(tooltip, '                readonly property int displayValue:', """                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.top: parent.top
                    width: 2; height: Math.min(5, parent.height / 4)
                    color: Kirigami.Theme.textColor; opacity: 0.65
                    Accessible.ignored: true
                }
""")
    (applet/'qml/MonetAppVolume.qml').write_bytes(Path(__file__).with_name('MonetAppVolume.qml').read_bytes())

def patch_preview_snap(applet):
    header = applet/'backend.h'
    backend = applet/'backend.cpp'
    prepend(header, '    Q_INVOKABLE QRect globalRect', '''    Q_PROPERTY(bool monetSnapAvailable READ monetSnapAvailable NOTIFY monetSnapAvailableChanged)
    bool monetSnapAvailable() const;
    Q_INVOKABLE void requestMonetSnap(const QString &windowId) const;

''')
    prepend(header, '    void showAllPlaces();', '    void monetSnapAvailableChanged();\n')
    prepend(header, '    KConfigWatcher::Ptr m_activityManagerPluginsSettingsWatcher;', '''    const KSharedConfig::Ptr m_monetKWinConfig = KSharedConfig::openConfig(QStringLiteral("kwinrc"));
    const KConfigWatcher::Ptr m_monetKWinWatcher = KConfigWatcher::create(m_monetKWinConfig);
''')
    prepend(backend, '#include <QAction>\n', '#include <QDBusConnection>\n#include <QDBusMessage>\n#include <QUuid>\n')
    prepend(backend, '    connect(m_activityManagerPluginsSettingsWatcher.get(),', '''    connect(m_monetKWinWatcher.get(), &KConfigWatcher::configChanged, this, [this](const KConfigGroup &group) {
        if (group.name() == QLatin1String("Script-monet-snap") || group.name() == QLatin1String("Plugins")) {
            Q_EMIT monetSnapAvailableChanged();
        }
    });
''')
    prepend(backend, 'void Backend::setActionGroup(QAction *action) const', '''bool Backend::monetSnapAvailable() const
{
    return KWindowSystem::isPlatformWayland()
        && m_monetKWinConfig->group(QStringLiteral("Plugins")).readEntry("monet-snapEnabled", true)
        && m_monetKWinConfig->group(QStringLiteral("Script-monet-snap")).readEntry("Snapping", true);
}

void Backend::requestMonetSnap(const QString &windowId) const
{
    const QUuid id(windowId);
    if (id.isNull() || !monetSnapAvailable()) {
        return;
    }
    auto message = QDBusMessage::createSignal(QStringLiteral("/org/monet/HomeBar"), QStringLiteral("org.monet.HomeBar"), QStringLiteral("SnapWindowRequested"));
    message << id.toString();
    QDBusConnection::sessionBus().send(message);
}

''')
    prepend(applet/'CMakeLists.txt', '                      Qt::Qml\n', '                      Qt::DBus\n')
    prepend(applet/'qml/ToolTipInstance.qml', '            // Count badge.', '''            PlasmaComponents3.ToolButton {
                id: snapButton
                readonly property var windowModel: root.model ?? toolTipDelegate.parentTask?.model
                readonly property string windowId: String(windowModel?.WinIdList?.[0] ?? "")
                visible: root.index >= 0 && toolTipDelegate.isWin && backend.monetSnapAvailable
                    && windowId.length > 0 && windowModel?.IsResizable === true && !windowModel.IsFullScreen
                Layout.alignment: Qt.AlignTop
                Layout.topMargin: -headerItem.Layout.margins
                icon.name: "view-split-left-right"
                text: i18nd("monet", "Snap layouts")
                display: PlasmaComponents3.ToolButton.IconOnly
                Accessible.name: text
                Accessible.description: root.display
                PlasmaComponents3.ToolTip.text: text
                PlasmaComponents3.ToolTip.visible: root.visible && hovered
                PlasmaComponents3.ToolTip.delay: Kirigami.Units.toolTipDelay
                onClicked: {
                    backend.requestMonetSnap(windowId);
                    tasks.cancelHighlightWindows();
                    toolTipDelegate.parentTask.hideImmediately();
                }
            }

''')

def apply(source):
    applet=source/'applets/taskmanager'
    patch_audio(applet)
    patch_preview_snap(applet)
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

            height: taskList.height''', '''            // Coordinates avoid competing anchors during a live edge change.
            x: tasks.vertical ? 0 : Plasmoid.configuration.monetIconAlignment === "center" ? (parent.width - width) / 2
                : tasks.shouldBeMirrored(Plasmoid.configuration.reverseMode, Application.layoutDirection, false) ? parent.width - width : 0
            y: tasks.vertical && Plasmoid.configuration.monetIconAlignment === "center" ? (parent.height - height) / 2 : 0

            height: taskList.height''')
    replace(context, 'text: editModeAction ? editModeAction.text : ""',
            'text: editModeAction ? i18nd("monet", "Customize Home Bar…") : ""')
    replace(applet/'CMakeLists.txt','        qml/Task.qml','        qml/Task.qml\n        qml/MonetDockMotion.qml\n        qml/MonetDockHover.qml\n        qml/MonetAppVolume.qml')
    prepend(applet/'qml/main.qml', 'import QtQuick\n', 'import QtQuick.Controls as MonetControls\n')
    prepend(applet/'qml/main.qml', '    property Task toolTipOpenedByClick', '''    readonly property bool monetSingleRowDock: iconsOnly && !vertical
        && Plasmoid.location === PlasmaCore.Types.BottomEdge && Plasmoid.configuration.maxStripes === 1
    readonly property real monetRequiredWidth: taskList.count * TaskManagerApplet.LayoutMetrics.preferredMinWidth()
    readonly property bool monetOverflow: monetSingleRowDock && monetRequiredWidth > width + 1
    function monetRevealTask(item) {
        if (!monetOverflow || !item || item.parent !== taskList) return;
        const point = item.mapToItem(monetViewport.contentItem, 0, 0);
        if (point.x < monetViewport.contentX) monetViewport.contentX = Math.max(0, point.x);
        else if (point.x + item.width > monetViewport.contentX + monetViewport.width)
            monetViewport.contentX = Math.min(monetViewport.contentWidth - monetViewport.width, point.x + item.width - monetViewport.width);
    }

''')
    replace(applet/'qml/main.qml', '''        TriangleMouseFilter {
            id: tmf''', '''        Flickable {
            id: monetViewport
            objectName: "monetTaskViewport"
            anchors.fill: parent
            anchors.leftMargin: tasks.monetOverflow ? 24 : 0
            anchors.rightMargin: tasks.monetOverflow ? 24 : 0
            contentWidth: tasks.monetOverflow ? Math.max(width, tasks.monetRequiredWidth) : width
            contentHeight: height
            clip: tasks.monetOverflow || tasks.monetLayoutSettling || tasks.monetInternalDragging
            interactive: false // Native task drags retain their press and reordering.
            onWidthChanged: contentX = Math.max(0, Math.min(contentX, contentWidth - width))
            onContentWidthChanged: contentX = tasks.monetOverflow ? Math.max(0, Math.min(contentX, contentWidth - width)) : 0
        }
        MonetControls.ToolButton {
            objectName: "monetPreviousTasks"
            anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
            width: 24; height: Math.min(40, parent.height)
            visible: tasks.monetOverflow
            enabled: monetViewport.contentX > 0
            text: i18nd("monet", "Show previous apps")
            icon.name: "arrow-left"; display: MonetControls.AbstractButton.IconOnly
            onClicked: monetViewport.contentX = Math.max(0, monetViewport.contentX - monetViewport.width * .7)
        }
        MonetControls.ToolButton {
            objectName: "monetNextTasks"
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            width: 24; height: Math.min(40, parent.height)
            visible: tasks.monetOverflow
            enabled: monetViewport.contentX < monetViewport.contentWidth - monetViewport.width
            text: i18nd("monet", "Show more apps")
            icon.name: "arrow-right"; display: MonetControls.AbstractButton.IconOnly
            onClicked: monetViewport.contentX = Math.min(monetViewport.contentWidth - monetViewport.width, monetViewport.contentX + monetViewport.width * .7)
        }
        TriangleMouseFilter {
            id: tmf
            parent: monetViewport.contentItem''')
    replace(applet/'qml/main.qml', 'return Math.min(tasks.width, Layout.maximumWidth);',
            'return Math.min(monetViewport.contentWidth, Layout.maximumWidth);')
    prepend(applet/'qml/Task.qml', '    onXChanged: {', '''    readonly property bool monetWindowActive: model.IsActive === true
    onMonetWindowActiveChanged: if (monetWindowActive) Qt.callLater(() => tasksRoot.monetRevealTask(task))
    onActiveFocusChanged: if (activeFocus) Qt.callLater(() => tasksRoot.monetRevealTask(task))

''')
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
    # Keep rearrangement inside Qt Quick, without a GPU readback/platform drag
    # loop. Only a launcher dragged outside the bar needs a native system drag.
    prepend(applet/'qml/main.qml', '    property Task toolTipOpenedByClick', '''    readonly property bool monetReordering: iconsOnly && !vertical
        && Plasmoid.location === PlasmaCore.Types.BottomEdge && taskList.rows === 1 && !!dragSource

    readonly property bool monetManualDrag: iconsOnly && (vertical || Plasmoid.formFactor === PlasmaCore.Types.Horizontal)
        && Plasmoid.configuration.maxStripes === 1
        && tasksModel.sortMode === TaskManager.TasksModel.SortManual
    property bool monetInternalDragging: false
    property point monetDragPointer: Qt.point(0, 0)
    property point monetDragOffset: Qt.point(0, 0)
    property bool monetLayoutSettling: true
    function monetSettleLayout() {
        monetLayoutSettling = true;
        monetHoverState.current = null;
        if (monetInternalDragging) monetEndDrag();
        monetLayoutTimer.restart();
    }
    onVerticalChanged: monetSettleLayout()
    onWidthChanged: monetSettleLayout()
    onHeightChanged: monetSettleLayout()
    readonly property Timer monetLayoutTimer: Timer {
        interval: 160
        running: true
        onTriggered: tasks.monetLayoutSettling = false
    }
    function monetBeginDrag(item, scenePoint) {
        const point = taskList.mapFromItem(null, scenePoint.x, scenePoint.y);
        monetDragPointer = point;
        const painted = item.mapToItem(taskList, 0, 0);
        monetDragOffset = Qt.point(point.x - painted.x, point.y - painted.y);
        dragSource = item;
        monetInternalDragging = true;
    }
    function monetUpdateDrag(scenePoint) {
        monetDragPointer = taskList.mapFromItem(null, scenePoint.x, scenePoint.y);
        mouseHandler.monetQueueReorder(taskList.mapToItem(mouseHandler, monetDragPointer.x, monetDragPointer.y));
    }
    function monetHandoffDrag() {
        mouseHandler.monetFlushReorder();
        monetInternalDragging = false;
    }
    function monetEndDrag() {
        monetHandoffDrag();
        dragSource = null; // Persist the final order once on release.
    }

''')
    prepend(applet/'qml/MouseHandler.qml', '    onPositionChanged: event => {', '''    function monetReorder(point) {
        if (isGroupDialog || !tasks.monetManualDrag || !tasks.dragSource
                || tasksModel.sortMode !== TaskManager.TasksModel.SortManual) return false;
        // The list can be centered or mirrored inside the full-width drop area.
        const local = target.mapFromItem(dropArea, point.x, point.y);
        const source = tasks.dragSource;
        if (source.parent !== target) return false;
        const coordinate = tasks.vertical ? local.y : local.x;
        const origin = tasks.vertical ? source.y + source.height / 2 : source.x + source.width / 2;
        let above = source;
        let distance = 0;
        // Use stable layout slots and cross their centres with a small dead
        // band. In-flight painted positions otherwise oscillate under a still
        // pointer. Choose the furthest crossed slot in either text direction.
        for (const item of target.children) {
            if (!item.visible || item.index < 0 || !item.model || item === source) continue;
            const center = tasks.vertical ? item.y + item.height / 2 : item.x + item.width / 2;
            if (((coordinate > origin && center > origin && coordinate >= center + 3)
                    || (coordinate < origin && center < origin && coordinate <= center - 3))
                    && Math.abs(center - origin) > distance) {
                above = item;
                distance = Math.abs(center - origin);
            }
        }
        if (above !== source) tasksModel.move(source.index, above.index);
        return true;
    }
    property point monetPendingPoint: Qt.point(0, 0)
    function monetQueueReorder(point) {
        monetPendingPoint = point;
        if (!monetReorderFrame.running) monetReorderFrame.start();
    }
    function monetFlushReorder() {
        if (!monetReorderFrame.running) return;
        monetReorderFrame.stop();
        monetReorder(monetPendingPoint);
    }
    Timer {
        id: monetReorderFrame
        interval: 16 // Coalesce input bursts; never poll while idle.
        onTriggered: dropArea.monetReorder(dropArea.monetPendingPoint)
    }

''')
    replace(applet/'qml/MouseHandler.qml', '    onPositionChanged: event => {', '''    onPositionChanged: event => {
        if (!isGroupDialog && tasks.monetManualDrag && tasks.dragSource) {
            monetQueueReorder(Qt.point(event.x, event.y));
            return;
        }''')
    replace(applet/'qml/Task.qml', '''            onActiveChanged: {
                if (active) {
                    icon.grabToImage(result => {''', '''            target: !task.inPopup && task.tasksRoot.monetManualDrag ? null : parent
            property bool monetLocal: false
            property bool monetExported: false
            function monetExport() {
                if (monetExported) return;
                monetExported = true;
                if (monetLocal) {
                    // Keep dragSource alive until the platform drag finishes:
                    // saving launchers here can replace this very delegate.
                    tasksRoot.monetHandoffDrag();
                    monetLocal = false;
                }
                icon.grabToImage(result => {''')
    replace(applet/'qml/Task.qml', '''                    });
                } else {
                    setRequestedInhibitDnd(false);
                    dragHelper.Drag.active = false;
                    dragHelper.Drag.imageSource = "";
                }
            }
        }
    }

    Loader {''', '''                });
            }
            onCentroidChanged: {
                if (!active || !monetLocal) return;
                const point = tasksRoot.mapFromItem(null, centroid.scenePosition.x, centroid.scenePosition.y);
                const outside = point.x < -24 || point.x > tasksRoot.width + 24
                    || point.y < -24 || point.y > tasksRoot.height + 24;
                if (outside) monetExport();
                else if (tasksRoot.monetInternalDragging) tasksRoot.monetUpdateDrag(centroid.scenePosition);
            }
            onActiveChanged: {
                if (active) {
                    monetExported = false;
                    monetLocal = !task.inPopup && tasksRoot.monetManualDrag;
                    if (monetLocal) {
                        setRequestedInhibitDnd(true);
                        tasksRoot.monetBeginDrag(task, centroid.scenePosition);
                    } else monetExport();
                } else {
                    // A quick release can beat the asynchronous export image.
                    // In that case no platform drag-finished signal will arrive.
                    const finishLocal = monetLocal || (monetExported
                        && tasksRoot.dragSource === task && !dragHelper.Drag.active);
                    monetLocal = false;
                    setRequestedInhibitDnd(false);
                    dragHelper.Drag.active = false;
                    dragHelper.Drag.imageSource = "";
                    if (finishLocal) tasksRoot.monetEndDrag();
                }
            }
        }
    }

    Loader {''')
    replace(applet/'qml/Task.qml', 'if (!dragHandler.active) {', 'if (!dragHandler || !dragHandler.active) {')
    prepend(applet/'qml/Task.qml', '    onXChanged: {', '''    readonly property bool monetDragged: tasksRoot.monetInternalDragging && tasksRoot.dragSource === task
    z: monetDragged ? 100 : 0
    function monetResetMovement() {
        moveAnim.stop();
        translateTransform.x = 0;
        translateTransform.y = 0;
        oldX = x;
        oldY = y;
    }
    onMonetDraggedChanged: {
        monetResetMovement();
        if (!monetDragged && !tasksRoot.monetLayoutSettling) {
            moveAnim.x = tasksRoot.monetDragPointer.x - tasksRoot.monetDragOffset.x - x;
            moveAnim.y = tasksRoot.monetDragPointer.y - tasksRoot.monetDragOffset.y - y;
            moveAnim.restart();
        }
    }
    Connections {
        target: task.tasksRoot
        function onMonetLayoutSettlingChanged() { task.monetResetMovement(); }
    }

''')
    replace(applet/'qml/Task.qml', '''    onXChanged: {
        if (!completed) {''', '''    onXChanged: {
        if (tasksRoot.monetLayoutSettling || monetDragged) { monetResetMovement(); return; }
        if (!completed) {''')
    replace(applet/'qml/Task.qml', '''    onYChanged: {
        if (!completed) {''', '''    onYChanged: {
        if (tasksRoot.monetLayoutSettling || monetDragged) { monetResetMovement(); return; }
        if (!completed) {''')
    replace(applet/'qml/Task.qml', '''    transform: Translate {
        id: translateTransform
    }''', '''    transform: [Translate {
        id: translateTransform
    }, Translate {
        x: task.monetDragged ? task.tasksRoot.monetDragPointer.x - task.tasksRoot.monetDragOffset.x - task.x : 0
        y: task.monetDragged ? task.tasksRoot.monetDragPointer.y - task.tasksRoot.monetDragOffset.y - task.y : 0
    }]''')
    # First reorder must animate even for the delegate that initially sat at x=0.
    # Seed after initial layout, before accepting the first displacement.
    replace(applet/'qml/Task.qml', '        completed = true;', '''        Qt.callLater(() => {
            oldX = x;
            oldY = y;
            completed = true;
        });''')
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
            property real dropScale: root.containsAcceptableDrag ? 1.10 : 1.0
            readonly property real dropLift: root.containsAcceptableDrag && Kirigami.Units.shortDuration > 0 ? 3 : 0
            Behavior on dropScale { enabled: Kirigami.Units.shortDuration > 0; NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutCubic } }
            Rectangle {
                objectName: "monetTrashDropFeedback"
                anchors.fill: parent
                anchors.margins: -4
                z: -1
                radius: Math.min(width, height) / 3
                color: "#357F72"
                border.color: "#92D6C4"
                border.width: 2
                opacity: root.containsAcceptableDrag ? .45 : 0
                visible: opacity > 0
                Behavior on opacity { enabled: Kirigami.Units.shortDuration > 0; NumberAnimation { duration: Kirigami.Units.shortDuration } }
                Accessible.name: i18nd("monet", "Release to move to Trash")
            }
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
                    xScale: monetMotion.iconScale * trashIcon.dropScale; yScale: monetMotion.iconScale * trashIcon.dropScale },
                Translate { y: -monetMotion.lift - trashIcon.dropLift }
            ]''')
    (trash/'MonetDockMotion.qml').write_bytes(Path(__file__).with_name('MonetDockMotion.qml').read_bytes())
    (trash/'MonetDockHover.qml').write_bytes(Path(__file__).with_name('MonetDockHover.qml').read_bytes())

if __name__=='__main__':apply(Path(sys.argv[1]))
