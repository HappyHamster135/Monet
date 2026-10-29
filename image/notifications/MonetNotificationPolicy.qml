/* SPDX-License-Identifier: GPL-3.0-or-later */
import QtQuick
import org.kde.notificationmanager as NotificationManager

// Keep Plasma's models, actions and privacy filters. This object only decides
// which received messages should stay in history instead of becoming popups.
QtObject {
    id: policy
    required property QtObject notificationSettings
    readonly property string dismissLabel: i18nd("monet", "Dismiss to history")

    function keepPopup(type, urgency, transient) {
        return type === NotificationManager.Notifications.NotificationType
            && urgency === NotificationManager.Notifications.CriticalUrgency && !transient
    }

    property NotificationManager.Notifications received: NotificationManager.Notifications {
        objectName: "monetReceivedNotifications"
        showJobs: false
        showExpired: false
        showDismissed: false
        showAddedDuringInhibition: true
        urgencies: NotificationManager.Notifications.LowUrgency
                 | NotificationManager.Notifications.NormalUrgency
                 | NotificationManager.Notifications.CriticalUrgency
        groupMode: NotificationManager.Notifications.GroupDisabled
    }

    property Instantiator mutedMessages: Instantiator {
        model: policy.received
        delegate: QtObject {
            property bool ready: false
            required property int index
            required property var model
            required property string desktopEntry
            required property string notifyRcName
            readonly property bool muted: policy.notificationSettings.popupBlacklistedApplications.includes(desktopEntry)
                || policy.notificationSettings.popupBlacklistedServices.includes(notifyRcName)

            function keepQuiet() {
                if (!ready || !muted) return
                const row = policy.received.index(index, 0)
                if (model.transient) {
                    policy.received.close(row)
                } else {
                    // Mark it as history without sending the server's expire/close
                    // event, so its actions survive. Clear History can still remove it.
                    policy.received.stopTimeout(row)
                    model.expired = true
                }
            }
            onMutedChanged: keepQuiet()
            Component.onCompleted: { ready = true; keepQuiet() }
        }
    }
}
