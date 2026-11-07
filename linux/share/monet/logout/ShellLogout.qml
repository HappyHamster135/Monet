// SPDX-License-Identifier: GPL-3.0-or-later
// Keep Plasma's original page available if Monet's page cannot load.
import QtQuick
import org.kde.taskmanager as TaskManager

FocusScope {
    id: host
    objectName: "MonetPowerHost"
    focus: true
    width: typeof screenGeometry === "undefined" ? 1440 : screenGeometry.width
    height: typeof screenGeometry === "undefined" ? 900 : screenGeometry.height
    property bool usingFallback: false
    readonly property bool monetHandoff: !usingFallback && page.status === Loader.Ready
    readonly property string transitionMessage: page.item?.transitionMessage || ""
    property bool handoffStarted: false
    property bool applicationReview: false
    property var initialWindows: ({})
    property bool needsInteraction: false
    readonly property bool monetInteractionRequired: applicationReview || needsInteraction
    // The native unfiltered window model includes save dialogs skipped by the
    // Home Bar. Older greeters still load the page and offer Show applications.
    readonly property var windows: typeof monetSessionWindows === "undefined" ? null : monetSessionWindows
    function windowState() {
        let current = {}
        if (!windows) return current
        for (let row = 0; row < windows.rowCount(); ++row) {
            const index = windows.index(row, 0)
            if (!windows.data(index, TaskManager.AbstractTasksModel.IsWindow)) continue
            const ids = windows.data(index, TaskManager.AbstractTasksModel.WinIdList)
            const key = JSON.stringify(ids)
            if (!ids || !key || key === "[]") continue
            current[key] = !!windows.data(index, TaskManager.AbstractTasksModel.IsDemandingAttention)
        }
        return current
    }
    function updateInteraction() {
        if (!handoffStarted) return
        const current = windowState()
        // New windows include native save/inhibitor prompts, including windows
        // skipped by the Home Bar. Reveal them until they close. Attention on
        // an existing window also takes priority over the transition screen.
        needsInteraction = Object.keys(current).some(key => !(key in initialWindows) || current[key])
    }
    Timer { id: interactionDelay; interval: 0; onTriggered: host.updateInteraction() }
    Connections {
        target: windows
        function onRowsInserted() { interactionDelay.restart() }
        function onRowsRemoved() { interactionDelay.restart() }
        function onDataChanged() { interactionDelay.restart() }
        function onModelReset() { interactionDelay.restart() }
    }
    function showLeaving(message) {
        if (!handoffStarted) initialWindows = windowState()
        handoffStarted = true
        if (page.item && page.item.showLeaving) page.item.showLeaving(message)
        interactionDelay.restart()
    }

    signal logoutRequested()
    signal haltRequested()
    signal haltUpdateRequested()
    signal suspendRequested(int spdMethod)
    signal rebootRequested()
    signal rebootRequested2(int opt)
    signal rebootUpdateRequested()
    signal cancelRequested()
    signal lockScreenRequested()
    signal cancelSoftwareUpdateRequested()

    Loader {
        id: page
        anchors.fill: parent
        focus: true
        source: "MonetLogout.qml"
        onStatusChanged: {
            if (status === Loader.Error && !host.usingFallback) {
                host.usingFallback = true
                source = "KdeLogout.qml"
            }
        }
    }
    Connections {
        target: page.item
        ignoreUnknownSignals: true
        function onLogoutRequested() { host.logoutRequested() }
        function onHaltRequested() { host.haltRequested() }
        function onHaltUpdateRequested() { host.haltUpdateRequested() }
        function onSuspendRequested(spdMethod) { host.suspendRequested(spdMethod) }
        function onRebootRequested() { host.rebootRequested() }
        function onRebootRequested2(opt) { host.rebootRequested2(opt) }
        function onRebootUpdateRequested() { host.rebootUpdateRequested() }
        function onCancelRequested() { host.cancelRequested() }
        function onLockScreenRequested() { host.lockScreenRequested() }
        function onCancelSoftwareUpdateRequested() { host.cancelSoftwareUpdateRequested() }
        function onShowApplicationsRequested() { host.applicationReview = true }
    }
    Shortcut {
        sequence: "Escape"
        enabled: page.status === Loader.Error
        onActivated: host.cancelRequested()
    }
}
