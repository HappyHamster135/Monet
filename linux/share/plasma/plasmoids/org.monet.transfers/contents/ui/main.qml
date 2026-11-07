import QtQuick
import QtQuick.Controls as C
import QtQuick.Templates as T
import QtQuick.Layouts
import QtCore
import Qt.labs.folderlistmodel
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.kde.notificationmanager as NotificationManager
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root
    SessionActivity { id: activity; viewVisible: root.visible; onActiveChanged: if (active) Qt.callLater(root.refresh) }
    FolderOpenController { id: folderOpen }
    Plasmoid.icon: "folder-download"
    toolTipMainText: i18n("Transfers")
    toolTipSubText: i18n("Copies, downloads and extractions")
    preferredRepresentation: compactRepresentation
    property var localJobs: []
    property bool busy: false
    property bool watchReady: false
    property string problem: ""
    readonly property rect usableScreen: {
        const area = Plasmoid.containment ? Plasmoid.containment.availableScreenRect : null;
        return area && area.width > 0 && area.height > 0 ? area : Qt.rect(0, 0, Screen.width, Screen.height);
    }
    readonly property bool activeLocal: localJobs.some(job => ["queued", "running", "paused", "cancelling"].includes(job.state))
    readonly property string stateFolder: StandardPaths.writableLocation(StandardPaths.GenericStateLocation) + "/monet/"
    function refresh() {
        if (!activity.active || busy) return;
        busy = true;
        runner.connectSource("@LIBEXECDIR@/monet-file-jobs status");
    }
    function control(action, job) {
        if (!["pause", "resume", "cancel", "retry"].includes(action) || !/^[a-f0-9]{32}$/.test(job.token)) return;
        runner.connectSource("@LIBEXECDIR@/monet-file-jobs " + action + " " + job.owner + " " + job.token);
    }
    function label(state) {
        return ({queued:i18n("Waiting"), running:i18n("Working"), paused:i18n("Paused"), cancelling:i18n("Cancelling"),
            done:i18n("Completed"), failed:i18n("Failed"), cancelled:i18n("Cancelled"), interrupted:i18n("Interrupted")})[state] || state;
    }
    function representedExtraction(job) {
        if (!job || String(job.desktopEntry).replace(/\.desktop$/, "") !== "org.kde.ark" || !String(job.destUrl)) return false;
        function location(value) {
            // Python's fully encoded file URL and KIO's display form can spell
            // spaces/Unicode differently. Compare their local path spelling.
            try { return decodeURIComponent(String(value)).replace(/\/+$/, ""); }
            catch (error) { return String(value).replace(/\/+$/, ""); }
        }
        const destination = location(job.destUrl);
        return root.localJobs.some(local => local.owner === "files" && location(local.destinationUrl) === destination);
    }
    P5Support.DataSource {
        id: runner; engine: "executable"
        onNewData: (source, data) => {
            disconnectSource(source);
            if (source.endsWith(" status")) {
                root.busy = false;
                try {
                    if (data["exit code"] !== 0) throw new Error();
                    const result = JSON.parse(data.stdout);
                    root.localJobs = result.files.map(job => Object.assign({}, job, {owner:"files"}))
                        .concat(result.store.map(job => Object.assign({}, job, {owner:"store", kind:job.action === "remove" ? "remove" : "download"})))
                        .sort((a,b) => b.updated - a.updated);
                    root.watchReady = true; // The status helper has created both queue directories.
                    root.problem = "";
                } catch (error) { root.problem = i18n("Could not read transfers. Try refreshing."); }
            } else {
                if (data["exit code"] !== 0) root.problem = i18n("That transfer changed. Refresh and try again.");
                root.refresh();
            }
        }
    }
    // This model lives inside Plasma, sharing its native KIO JobViewServer.
    // It observes the actual CopyJobs; no duplicate copy engine or undo history.
    NotificationManager.Notifications {
        id: nativeJobs
        showNotifications: false; showJobs: true; showExpired: true; showDismissed: true
        groupMode: NotificationManager.Notifications.GroupDisabled
    }
    FolderListModel { id: filesWatch; folder: root.watchReady ? root.stateFolder + "files/transfers" : ""; nameFilters: ["*.json"]; showDirs: false; onCountChanged: debounce.restart() }
    FolderListModel { id: storeWatch; folder: root.watchReady ? root.stateFolder + "store" : ""; nameFilters: ["downloads.json"]; showDirs: false; onCountChanged: debounce.restart() }
    Connections { target: filesWatch; function onDataChanged() { debounce.restart(); } }
    Connections { target: storeWatch; function onDataChanged() { debounce.restart(); } }
    Timer { id: debounce; interval: 150; onTriggered: root.refresh() }
    Timer { interval: 1000; repeat: true; running: root.expanded && root.activeLocal && activity.active; onTriggered: root.refresh() }
    onExpandedChanged: expanded => { if (expanded) refresh(); }
    function takeOpenRequest() {
        if (Plasmoid.configuration.openRequest !== "") {
            root.expanded = true;
            refresh(); // Also refresh a Transfers panel that is already open.
            Plasmoid.configuration.openRequest = "";
        }
    }
    Connections { target: Plasmoid.configuration; function onOpenRequestChanged() { Qt.callLater(root.takeOpenRequest); } }
    Component.onCompleted: { refresh(); takeOpenRequest(); }
    compactRepresentation: C.ToolButton {
        icon.name: "folder-download"; Accessible.name: i18n("Transfers")
        onClicked: root.expanded = !root.expanded
        C.BusyIndicator { width: 12; height: 12; anchors.right: parent.right; running: activity.active && (root.activeLocal || nativeJobs.activeJobsCount > 0) }
    }
    fullRepresentation: Rectangle {
        id: page
        readonly property real maximumContentWidth: Math.max(1, root.usableScreen.width - Kirigami.Units.largeSpacing * 2)
        readonly property real maximumContentHeight: Math.max(1, root.usableScreen.height - Kirigami.Units.largeSpacing * 2)
        Layout.minimumWidth: Math.min(400, maximumContentWidth); Layout.minimumHeight: Math.min(300, maximumContentHeight)
        Layout.preferredWidth: Math.min(500, maximumContentWidth); Layout.preferredHeight: Math.min(540, maximumContentHeight)
        Layout.maximumWidth: maximumContentWidth; Layout.maximumHeight: maximumContentHeight
        color: Kirigami.Theme.backgroundColor
        radius: 14
        property Item pendingReveal: null
        property bool followFocus: true
        readonly property rect focusedBounds: {
            const item = page.Window.window ? page.Window.window.activeFocusItem : null;
            if (!item) return Qt.rect(0, 0, 0, 0);
            let parent = item;
            while (parent && parent !== transferView) {
                // mapToItem alone does not subscribe to ancestor geometry.
                const geometry = [parent.x, parent.y, parent.width, parent.height,
                    parent.scale, parent.rotation, parent.transformOrigin];
                parent = parent.parent;
            }
            return parent ? item.mapToItem(transferView, 0, 0, item.width, item.height) : Qt.rect(0, 0, 0, 0);
        }
        onFocusedBoundsChanged: scheduleReveal()
        function fitPopup() {
            const window = page.Window.window;
            if (!root.expanded || !window) return;
            const limitWidth = maximumContentWidth + Math.max(0, window.width - width);
            const limitHeight = maximumContentHeight + Math.max(0, window.height - height);
            if (window.width > limitWidth) window.width = limitWidth;
            if (window.height > limitHeight) window.height = limitHeight;
            window.update();
        }
        onMaximumContentWidthChanged: Qt.callLater(fitPopup)
        onMaximumContentHeightChanged: Qt.callLater(fitPopup)
        onWidthChanged: Qt.callLater(fitPopup)
        onHeightChanged: Qt.callLater(fitPopup)
        function scheduleReveal() {
            if (!followFocus) return;
            pendingReveal = page.Window.window ? page.Window.window.activeFocusItem : null;
            Qt.callLater(revealFocus);
        }
        function revealFocus() {
            const item = pendingReveal; pendingReveal = null;
            const view = transferScroll.contentItem;
            if (!item || !item.visible || !item.enabled || !page.Window.window || item !== page.Window.window.activeFocusItem) return;
            let parent = item;
            while (parent && parent !== view) parent = parent.parent;
            if (!parent) return;
            const bounds = item.mapToItem(view, 0, 0, item.width, item.height);
            const delta = bounds.y < 0 ? bounds.y : Math.max(0, bounds.y + bounds.height - view.height);
            const first = view.originY - view.topMargin;
            const last = Math.max(first, view.originY + view.contentHeight - view.height + view.bottomMargin);
            view.contentY = Math.max(first, Math.min(last, view.contentY + delta));
        }
        ListModel { id: localRows; dynamicRoles: true }
        function focusedJob() {
            const focus = page.Window.window ? page.Window.window.activeFocusItem : null;
            for (let item = focus; item; item = item.parent)
                if (item.transferKey !== undefined) return {key: item.transferKey, action: focus.objectName, item: focus};
            return null;
        }
        function jobAction(item, name) {
            if (item.objectName === name && item.visible && item.enabled) return item;
            for (const child of item.children || []) {
                const found = jobAction(child, name);
                if (found) return found;
            }
            return null;
        }
        function restoreJobFocus(previous) {
            if (!previous || !page.Window.window) return;
            const focus = page.Window.window.activeFocusItem;
            if (focus && (focus === previous.item && focus.visible && focus.enabled
                    || focus !== previous.item && typeof focus.clicked === "function")) return;
            let action = null;
            for (let i = 0; i < localRepeater.count; i++) {
                const row = localRepeater.itemAt(i);
                if (row && row.transferKey === previous.key) {
                    action = jobAction(row, previous.action) || jobAction(row, "openLocalTransferFolder");
                    break;
                }
            }
            (action || refreshButton).forceActiveFocus(Qt.TabFocusReason);
        }
        function focusFolderError() {
            if (root.expanded && folderOpen.error !== "" && dismissFolderMessage.visible) {
                dismissFolderMessage.forceActiveFocus(Qt.TabFocusReason);
                scheduleReveal();
            }
        }
        function focusFolderActivity() {
            if (root.expanded && folderOpen.busy && folderOpen.cancellable && cancelFolderOpening.visible) {
                cancelFolderOpening.forceActiveFocus(Qt.TabFocusReason);
                scheduleReveal();
            }
        }
        function focusTransferProblem() {
            if (root.expanded && root.problem !== "") {
                refreshButton.forceActiveFocus(Qt.TabFocusReason);
                pendingReveal = null; followFocus = false;
                transferView.cancelFlick(); transferView.contentY = transferView.originY - transferView.topMargin;
            }
        }
        function syncLocalJobs() {
            const focus = focusedJob();
            // Progress updates keep the delegate and its keyboard focus alive.
            for (let i = 0; i < root.localJobs.length; i++) {
                const job = root.localJobs[i]; const key = job.owner + ":" + job.token;
                let at = i;
                while (at < localRows.count && localRows.get(at).key !== key) at++;
                if (at === localRows.count) localRows.insert(i, {key: key, job: job});
                else {
                    if (at !== i) localRows.move(at, i, 1);
                    localRows.setProperty(i, "job", job);
                }
            }
            if (localRows.count > root.localJobs.length) localRows.remove(root.localJobs.length, localRows.count - root.localJobs.length);
            scheduleReveal();
            if (focus) Qt.callLater(() => page.restoreJobFocus(focus));
        }
        Component.onCompleted: { syncLocalJobs(); Qt.callLater(fitPopup); Qt.callLater(focusFolderError); Qt.callLater(focusFolderActivity); }
        Connections {
            target: root
            function onLocalJobsChanged() { page.syncLocalJobs(); }
            function onProblemChanged() { if (root.problem !== "") Qt.callLater(page.focusTransferProblem); }
            function onExpandedChanged() { if (root.expanded) Qt.callLater(page.fitPopup); }
        }
        Connections {
            target: page.Window.window
            function onActiveFocusItemChanged() { page.followFocus = true; page.scheduleReveal(); }
            function onXChanged() { Qt.callLater(page.fitPopup); }
            function onYChanged() { Qt.callLater(page.fitPopup); }
        }
        Connections {
            target: transferScroll.contentItem
            function onContentHeightChanged() { page.scheduleReveal(); }
            function onHeightChanged() { page.scheduleReveal(); }
        }
        Connections {
            target: folderOpen
            function onErrorChanged() { if (folderOpen.error !== "") Qt.callLater(page.focusFolderError); }
            function onBusyChanged() { if (folderOpen.busy) Qt.callLater(page.focusFolderActivity); }
            function onCancellableChanged() { if (folderOpen.cancellable) Qt.callLater(page.focusFolderActivity); }
        }
        Keys.onPressed: event => {
            if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && event.modifiers === Qt.NoModifier) {
                const item = page.Window.window ? page.Window.window.activeFocusItem : null;
                if (item instanceof T.AbstractButton && item.visible && item.enabled) {
                    if (!event.isAutoRepeat) item.clicked();
                    event.accepted = true;
                }
            }
        }
        ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10
        RowLayout {
            Layout.margins: 12
            C.Label { text: i18n("Transfers"); font.pixelSize: 25; font.family: "Fraunces 72pt SuperSoft"; Layout.fillWidth: true }
            C.ToolButton { id: refreshButton; objectName: "refreshTransfers"; icon.name: "view-refresh"; Accessible.name: i18n("Refresh transfers"); onClicked: root.refresh() }
        }
        Item {
            id: transferScroll
            objectName: "transferScroll"
            Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            readonly property real availableWidth: Math.max(0, width - transferBar.width)
            readonly property Item contentItem: transferView
            Flickable {
                id: transferView
                anchors.fill: parent
                contentWidth: width
                contentHeight: transferList.implicitHeight
                boundsBehavior: Flickable.StopAtBounds
                clip: true
                activeFocusOnTab: true
                C.ScrollBar.vertical: C.ScrollBar {
                    id: transferBar
                    onPressedChanged: if (pressed) { page.pendingReveal = null; page.followFocus = false; }
                }
                ScrollInput {
                    id: transferInput; view: transferView
                    onScrollRequested: { page.pendingReveal = null; page.followFocus = false; }
                }
                Keys.onPressed: event => transferInput.key(event)
                ColumnLayout {
                    id: transferList
                    width: transferScroll.availableWidth
                    C.Label { visible: root.problem !== ""; text: root.problem; textFormat: Text.PlainText; wrapMode: Text.WordWrap; Layout.fillWidth: true; Layout.minimumWidth: 0 }
                    RowLayout {
                        visible: folderOpen.busy
                        Layout.fillWidth: true; Layout.minimumWidth: 0
                        C.BusyIndicator { running: root.expanded && folderOpen.busy && activity.active; Layout.preferredWidth: 20; Layout.preferredHeight: 20 }
                        C.Label { text: i18n("Opening folder…"); wrapMode: Text.WordWrap; Layout.fillWidth: true; Layout.minimumWidth: 0 }
                        C.Button {
                            id: cancelFolderOpening; visible: folderOpen.cancellable; text: i18n("Cancel opening")
                            onClicked: { folderOpen.cancel(); refreshButton.forceActiveFocus(Qt.TabFocusReason); }
                        }
                    }
                    RowLayout {
                        visible: folderOpen.error !== ""
                        Layout.fillWidth: true; Layout.minimumWidth: 0
                        C.Label {
                            text: folderOpen.error; textFormat: Text.PlainText; wrapMode: Text.WordWrap
                            Accessible.description: folderOpen.error; Layout.fillWidth: true; Layout.minimumWidth: 0
                        }
                        C.ToolButton {
                            id: dismissFolderMessage; objectName: "dismissFolderMessage"; Layout.alignment: Qt.AlignTop
                            icon.name: "window-close"; Accessible.name: i18n("Dismiss folder message")
                            onClicked: { folderOpen.dismissError(); refreshButton.forceActiveFocus(Qt.TabFocusReason); }
                        }
                    }
                    Repeater {
                        model: nativeJobs
                        delegate: C.Frame {
                            required property var model
                            readonly property var job: model.jobDetails
                            visible: !root.representedExtraction(job)
                            Layout.fillWidth: true; Layout.minimumWidth: 0
                            ColumnLayout {
                                anchors.fill: parent
                                C.Label { text: job ? job.summary : ""; textFormat: Text.PlainText; font.bold: true; wrapMode: Text.WordWrap; Layout.fillWidth: true; Layout.minimumWidth: 0 }
                                C.Label { objectName: "nativeTransferDescription"; text: job ? folderOpen.plainText(job.text) : ""; textFormat: Text.PlainText; wrapMode: Text.WordWrap; Layout.fillWidth: true; Layout.minimumWidth: 0 }
                                C.Label { visible: job && job.state === NotificationManager.Notifications.JobStateStopped; text: job && job.error ? i18n("Failed") : i18n("Completed") }
                                C.ProgressBar { Layout.fillWidth: true; from: 0; to: 100; value: job ? job.percentage : 0; indeterminate: root.expanded && activity.active && job && job.percentage === 0 && job.state === NotificationManager.Notifications.JobStateRunning }
                                Flow {
                                    Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 8
                                    C.Button { visible: job && job.suspendable && job.state !== NotificationManager.Notifications.JobStateStopped; text: job && job.state === NotificationManager.Notifications.JobStateSuspended ? i18n("Resume") : i18n("Pause"); onClicked: job.state === NotificationManager.Notifications.JobStateSuspended ? job.resume() : job.suspend() }
                                    C.Button { visible: job && job.killable && job.state !== NotificationManager.Notifications.JobStateStopped; text: i18n("Cancel"); onClicked: job.kill() }
                                    C.Button {
                                        objectName: "openNativeTransferFolder"
                                        readonly property url destination: job ? (String(job.effectiveDestUrl) !== "" ? job.effectiveDestUrl : job.destUrl) : ""
                                        visible: String(destination) !== "" && !String(destination).startsWith("trash:")
                                        enabled: !folderOpen.busy
                                        text: i18n("Open folder")
                                        onClicked: folderOpen.open(destination, false, this)
                                    }
                                }
                            }
                        }
                    }
                    Repeater {
                        id: localRepeater
                        model: localRows
                        delegate: C.Frame {
                            required property var model
                            readonly property var modelData: model.job
                            readonly property string transferKey: model.key
                            Layout.fillWidth: true; Layout.minimumWidth: 0
                            ColumnLayout {
                                anchors.fill: parent
                                C.Label { text: modelData.name; textFormat: Text.PlainText; font.bold: true; Layout.fillWidth: true; Layout.minimumWidth: 0; elide: Text.ElideMiddle }
                                C.Label { text: (modelData.kind === "extract" ? i18n("Extracting") : modelData.kind === "remove" ? i18n("Removing app") : i18n("Store download")) + " · " + root.label(modelData.state); wrapMode: Text.WordWrap; Layout.fillWidth: true; Layout.minimumWidth: 0 }
                                C.ProgressBar { Layout.fillWidth: true; from: 0; to: 1; value: Math.max(0, modelData.progress); indeterminate: root.expanded && activity.active && modelData.progress < 0 && ["running","queued"].includes(modelData.state) }
                                C.Label { visible: modelData.error !== ""; text: modelData.error; textFormat: Text.PlainText; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                Flow {
                                    Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 8
                                    C.Button { objectName: "pauseLocalTransfer"; visible: modelData.owner === "files" && ["running","paused"].includes(modelData.state); text: modelData.state === "paused" ? i18n("Resume") : i18n("Pause"); onClicked: root.control(modelData.state === "paused" ? "resume" : "pause", modelData) }
                                    C.Button { objectName: "cancelLocalTransfer"; visible: ["queued","running","paused"].includes(modelData.state); text: i18n("Cancel"); onClicked: root.control("cancel", modelData) }
                                    C.Button { objectName: "retryLocalTransfer"; visible: ["failed","cancelled","interrupted"].includes(modelData.state); text: i18n("Retry"); onClicked: root.control("retry", modelData) }
                                    C.Button {
                                        objectName: "openLocalTransferFolder"
                                        readonly property url destination: modelData.destinationUrl || ""
                                        visible: modelData.owner === "files" && String(modelData.destinationUrl || "") !== ""
                                        enabled: !folderOpen.busy
                                        text: i18n("Open folder")
                                        onClicked: folderOpen.open(modelData.destinationUrl, true, this)
                                    }
                                }
                            }
                        }
                    }
                    C.Label { visible: root.localJobs.length === 0 && nativeJobs.count === 0; text: i18n("No transfers yet"); Layout.margins: 24 }
                    C.Label { text: i18n("Transfers keep going when this panel closes. Files’ Undo remains available for native copies and moves."); wrapMode: Text.WordWrap; Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.margins: 12 }
                }
            }
        }
        }
    }
}
