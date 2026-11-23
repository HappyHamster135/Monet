// Loaded by the Settings page loader; shares its window context.
import QtCore
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Templates as T
import QtQuick.Window
import org.kde.kirigami as Kirigami
import "../games" as Shared
import "FocusNavigation.js" as FocusNavigation


ColumnLayout {
    id: safetyCard
    spacing: 20
    readonly property var s: sheet.safety
    readonly property var network: s.network || ({})
    readonly property var rules: network.sharing || ({ apps: [], ports: [] })
    readonly property bool canChangeNetwork: s.networkActions === true
    readonly property bool confirmingFirmware: sheet.securityConfirmation === "firmware"
    readonly property bool confirmingLegacy: sheet.securityConfirmation === "legacy"
    readonly property var overview: sheet.securityOverview()
    readonly property var apps: [
        ["games", i18n("Games you host")],
        ["localsend", "LocalSend"],
        ["syncthing", "Syncthing"],
        ["sunshine", i18n("Streaming this PC")],
        ["deskflow", "Deskflow"]
    ]

    function cancelConfirmation() {
        if (!sheet.securityConfirmation) return false
        const review = confirmingFirmware ? firmwareReview : legacyReview
        sheet.securityConfirmation = ""
        if (review.visible && review.enabled) review.forceActiveFocus(Qt.OtherFocusReason)
        return true
    }

    SettingsControls.PageTitle {
        tone: look
        entry: sheet.entry("security")
        art: sheet.art
        text: i18n("Security")
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            objectName: "security-overview"
            tone: look
            divider: false
            title: safetyCard.overview.title
            detail: safetyCard.overview.detail || ""
            SettingsControls.Pill {
                objectName: "security-overview-action"
                tone: look
                kind: ["restart", "firewall-on"].includes(safetyCard.overview.command) ? "sun" : "plain"
                visible: !!(safetyCard.overview.action || safetyCard.overview.anchor)
                enabledPill: sheet.securityFixing === "" && !sheet.securityChecking
                text: safetyCard.overview.action || i18n("Review")
                onClicked: {
                    const next = safetyCard.overview
                    if (next.anchor) {
                        sheet.pendingAnchor = next.anchor
                        sheet.revealSearchTarget()
                    } else if (next.command === "check") {
                        sheet.loadSecurity()
                        sheet.checkFirmware()
                    } else {
                        sheet.fixSecurity(next.command)
                    }
                }
            }
        }
        SettingsControls.SettingRow {
            visible: sheet.securityProblem !== "" || sheet.securityFixing !== ""
            tone: look
            title: sheet.securityProblem || i18n("Waiting for the change…")
        }
    }

    SettingsControls.Caption { tone: look; text: i18n("Device security") }
    SettingsControls.Card {
        tone: look
        // Secure Boot: only signed software starts. Before it goes on, the firmware has
        // to trust Monet's key (its blue screen), or Monet wouldn't start.
        SettingsControls.SettingRow {
            id: bootRow
            objectName: "search-security-device"
            tone: look
            divider: false
            title: i18n("Secure Boot")
            readonly property bool needsKey: safetyCard.s.secureBoot === "off" && safetyCard.s.keyTrusted !== true
            readonly property bool canRestartToFirmware: safetyCard.s.firmwareRestartAvailable === true
            detail: !sheet.securityChecked ? ""
                : safetyCard.s.secureBoot === "on" ? i18n("On. The PC checks the boot software against keys it trusts.")
                : safetyCard.s.secureBoot === "unavailable" ? i18n("This PC didn't start in UEFI mode, so Secure Boot can't be on.")
                : safetyCard.s.secureBoot !== "off" ? i18n("Couldn’t check Secure Boot.")
                : sheet.keyAsked ? i18n("At the next restart a blue screen asks to trust Monet: choose Enroll MOK, Continue and Yes, type monetsetup and choose Reboot. Then turn Secure Boot on in the firmware settings.")
                : bootRow.needsKey ? i18n("Off. Before it goes on, the PC has to trust Monet, or Monet won't start: a blue screen asks once, at the next restart.")
                : !bootRow.canRestartToFirmware ? i18n("Off. Open the PC’s firmware settings at startup to turn it on.")
                : safetyCard.confirmingFirmware ? i18n("Your PC restarts into its firmware settings. Find Secure Boot (often under Boot or Security), turn it on, then save and exit.")
                    + "\n" + i18n("Open apps close, so save your work first.")
                : i18n("Off. Games with anti-cheat in Windows need it too. It's turned on in the PC's firmware settings.")
            lead: SettingsControls.Mark {
                tone: look
                known: safetyCard.s.secureBoot === "on" || safetyCard.s.secureBoot === "off"
                good: safetyCard.s.secureBoot === "on"
            }
            Row {
                spacing: 8
                visible: safetyCard.s.secureBoot === "off"
                         && (sheet.keyAsked || bootRow.needsKey || bootRow.canRestartToFirmware)
                SettingsControls.Pill {
                    id: firmwareCancel
                    objectName: "security-firmware-cancel"
                    tone: look
                    visible: safetyCard.confirmingFirmware && !sheet.keyAsked && !bootRow.needsKey
                    text: i18n("Cancel")
                    onClicked: safetyCard.cancelConfirmation()
                }
                SettingsControls.Pill {
                    id: firmwareReview
                    objectName: "security-firmware-review"
                    tone: look
                    visible: !firmwareCancel.visible
                    kind: sheet.keyAsked ? "sun" : "plain"
                    enabledPill: sheet.securityFixing === ""
                    text: sheet.securityFixing === "trust-key" ? i18n("Asking…")
                        : sheet.keyAsked ? i18n("Restart")
                        : bootRow.needsKey ? i18n("Trust Monet…")
                        : i18n("Firmware settings…")
                    onClicked: {
                        if (sheet.keyAsked) {
                            sheet.fixSecurity("restart")
                        } else if (bootRow.needsKey) {
                            sheet.fixSecurity("trust-key")
                        } else {
                            sheet.securityConfirmation = "firmware"
                            firmwareCancel.forceActiveFocus(Qt.OtherFocusReason)
                        }
                    }
                }
                SettingsControls.Pill {
                    objectName: "security-firmware-confirm"
                    tone: look
                    kind: "sun"
                    visible: firmwareCancel.visible
                    enabledPill: sheet.securityFixing === ""
                    text: i18n("Restart")
                    onClicked: {
                        safetyCard.cancelConfirmation()
                        sheet.fixSecurity("firmware-setup")
                    }
                }
            }
        }
        SettingsControls.SettingRow {
            tone: look
            title: i18n("Encryption")
            detail: !sheet.securityChecked ? ""
                : safetyCard.s.encryptionSetup === "pending" ? i18n("Setup is still using a temporary key. Keep your recovery key safe.")
                : safetyCard.s.encrypted === true && safetyCard.s.encryptionSetup === "complete" ? i18n("Monet’s system disk is encrypted.")
                : safetyCard.s.encrypted === true ? i18n("The system disk is encrypted. Monet couldn’t verify that setup finished.")
                : safetyCard.s.encrypted === false ? i18n("Off: someone who takes the disk out can read your files. Monet Setup encrypts the disk when it installs Monet.")
                : i18n("Couldn’t check disk encryption.")
            lead: SettingsControls.Mark {
                tone: look
                known: typeof safetyCard.s.encrypted === "boolean"
                good: safetyCard.s.encrypted === true && safetyCard.s.encryptionSetup === "complete"
            }
        }
        SettingsControls.SettingRow {
            tone: look
            title: i18n("App isolation")
            detail: !sheet.securityChecked ? ""
                : safetyCard.s.selinux === "enforcing" ? i18n("SELinux limits what system services and apps can access.")
                : safetyCard.s.selinux === "permissive" ? i18n("SELinux records violations but doesn’t block them.")
                : safetyCard.s.selinux === "disabled" ? i18n("SELinux is off.")
                : safetyCard.s.selinux === "unavailable" ? i18n("SELinux is unavailable on this installation.")
                : i18n("Couldn’t check SELinux.")
            lead: SettingsControls.Mark {
                tone: look
                known: ["enforcing", "permissive", "disabled"].includes(safetyCard.s.selinux)
                good: safetyCard.s.selinux === "enforcing"
            }
        }
    }

    SettingsControls.Caption { tone: look; text: i18n("Firewall & networks") }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            objectName: "search-security-network"
            tone: look
            divider: false
            title: i18n("Firewall")
            detail: !sheet.securityChecked ? ""
                : safetyCard.s.firewall === "on" ? (safetyCard.network.complete === true
                    ? i18n("On. See the active connections below.") : i18n("On. Monet couldn’t check all firewall rules."))
                : safetyCard.s.firewall === "off" ? i18n("Off. Other devices can try to connect to this PC.")
                : safetyCard.s.firewall === "unavailable" ? i18n("Firewalld is unavailable on this installation.")
                : i18n("Couldn’t check the firewall.")
            lead: SettingsControls.Mark {
                tone: look
                known: ["on", "off"].includes(safetyCard.s.firewall)
                good: safetyCard.s.firewall === "on"
            }
            SettingsControls.Pill {
                tone: look
                visible: safetyCard.s.firewall === "on"
                enabledPill: !sheet.securityChecking && sheet.securityFixing === ""
                text: i18n("Check again")
                onClicked: sheet.loadSecurity()
            }
        }
        SettingsControls.SettingRow {
            id: defaultFirewallRow
            objectName: "security-default-firewall"
            tone: look
            title: i18n("Use Monet’s default rules")
            detail: i18n("These rules cover nearby printers, your phone, and Steam on your local network.")
            visible: safetyCard.s.firewall === "on" && typeof safetyCard.s.firewallStrict === "boolean"
            tappable: safetyCard.canChangeNetwork && sheet.securityFixing === ""
            checkable: true
            checked: safetyCard.s.firewallStrict === true
            onTapped: sheet.fixSecurity("firewall-strict " + (checked ? "off" : "on"))
            SettingsControls.Switch { tone: look; active: defaultFirewallRow.checked }
        }
        SettingsControls.SettingRow {
            tone: look
            visible: safetyCard.s.firewall === "on" && !safetyCard.canChangeNetwork
            title: i18n("Network changes need the updated system helper.")
            detail: i18n("You can still see the active connections and rules here.")
        }
        SettingsControls.SettingRow {
            tone: look
            visible: safetyCard.network.sharingAsDefault === true
            title: i18n("Shared ports may be open on other connections.")
            detail: i18n("Choose Monet’s default rules to keep sharing on selected profiles.")
        }
        SettingsControls.SettingRow {
            tone: look
            visible: safetyCard.s.firewall === "on" && (safetyCard.network.devices || []).length === 0
            title: safetyCard.network.known ? i18n("No active firewall zones found.") : i18n("Couldn’t read the active firewall zones.")
        }
        Repeater {
            model: safetyCard.network.devices || []
            SettingsControls.SettingRow {
                required property var modelData
                tone: look
                title: modelData.name || modelData.interface || i18n("Source addresses")
                detail: (modelData.zone ? i18n("Zone: %1", modelData.zone) : i18n("Couldn’t check this connection’s zone."))
                    + (modelData.sources ? " · " + modelData.sources.join(", ") : "")
                    + (modelData.ports ? "\n" + i18n("Zone ports: %1", modelData.ports) : "")
                    + (modelData.services ? "\n" + i18n("Zone services: %1", modelData.services) : "")
                SettingsControls.Pill {
                    tone: look
                    objectName: modelData.interface ? "security-sharing-profile-" + modelData.interface : ""
                    visible: modelData.changeable === true
                    enabledPill: safetyCard.canChangeNetwork && sheet.securityFixing === ""
                        && (modelData.zone === "monet-shared" || safetyCard.network.sharingAsDefault === false)
                    text: modelData.zone === "monet-shared" ? i18n("Stop sharing") : i18n("Share on this profile")
                    onClicked: sheet.fixSecurity("firewall-network " + modelData.uuid
                                                  + (modelData.zone === "monet-shared" ? " off" : " on"))
                }
            }
        }
        SettingsControls.SettingRow {
            visible: safetyCard.network.legacy === true
            tone: look
            title: i18n("Older firewall rules")
            detail: i18n("These rules open ports across firewall zones.")
                + ((safetyCard.network.legacyApps || []).length ? "\n" + safetyCard.network.legacyApps.join(", ") : "")
                + ((safetyCard.network.legacyPorts || []).length ? "\n" + safetyCard.network.legacyPorts.map(rule => rule.port).join(", ") : "")
                + (safetyCard.confirmingLegacy ? "\n" + i18n("Remove all of these rules? You can add the ports you still use under Shared ports.") : "")
            Row {
                spacing: 8
                visible: safetyCard.canChangeNetwork
                SettingsControls.Pill {
                    id: legacyReview
                    objectName: "security-legacy-review"
                    tone: look
                    visible: !safetyCard.confirmingLegacy
                    enabledPill: sheet.securityFixing === "" && safetyCard.s.firewall === "on"
                    text: i18n("Review")
                    onClicked: {
                        sheet.securityConfirmation = "legacy"
                        legacyCancel.forceActiveFocus(Qt.OtherFocusReason)
                    }
                }
                SettingsControls.Pill {
                    id: legacyCancel
                    objectName: "security-legacy-cancel"
                    tone: look
                    visible: safetyCard.confirmingLegacy
                    text: i18n("Cancel")
                    onClicked: safetyCard.cancelConfirmation()
                }
                SettingsControls.Pill {
                    objectName: "security-legacy-confirm"
                    tone: look
                    visible: safetyCard.confirmingLegacy
                    enabledPill: sheet.securityFixing === "" && safetyCard.s.firewall === "on"
                    text: i18n("Remove all")
                    onClicked: {
                        safetyCard.cancelConfirmation()
                        sheet.fixSecurity("firewall-clear-legacy")
                    }
                }
            }
        }
    }

    SettingsControls.Caption { tone: look; text: i18n("Shared ports") }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Ports for nearby devices")
            detail: !sheet.securityChecked ? ""
                : !safetyCard.network.sharing ? i18n("Couldn’t read Monet’s sharing rules.")
                : i18n("These ports open on connection profiles you choose to share with. Any app listening on one of them can receive connections. A wired profile may be used on more than one network.")
        }
        Repeater {
            model: safetyCard.network.appPorts ? safetyCard.apps : []
            SettingsControls.SettingRow {
                id: shareRow
                required property var modelData
                objectName: "security-sharing-app-" + modelData[0]
                tone: look
                title: modelData[1]
                detail: safetyCard.network.appPorts[modelData[0]].join(", ")
                checkable: true
                checked: safetyCard.rules.apps.includes(modelData[0])
                tappable: safetyCard.canChangeNetwork && safetyCard.s.firewall === "on"
                          && (checked || safetyCard.network.sharingAsDefault === false)
                          && !!safetyCard.network.sharing && sheet.securityFixing === ""
                onTapped: sheet.fixSecurity("firewall-sharing " + modelData[0] + (checked ? " off" : " on"))
                SettingsControls.Switch { tone: look; active: shareRow.checked }
            }
        }
        Repeater {
            model: safetyCard.rules.ports
            SettingsControls.SettingRow {
                required property var modelData
                tone: look
                title: modelData.name
                detail: modelData.port
                SettingsControls.Pill {
                    objectName: "security-sharing-port-" + modelData.port
                    tone: look
                    enabledPill: safetyCard.canChangeNetwork && safetyCard.s.firewall === "on" && sheet.securityFixing === ""
                    text: i18n("Remove")
                    onClicked: sheet.fixSecurity("firewall-remove-port " + modelData.port)
                }
            }
        }
    }

    SettingsControls.Caption { tone: look; text: i18n("Sign-in") }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Sign-in and screen lock")
            detail: i18n("Manage your account or choose when Monet asks you to unlock the screen.")
            SettingsControls.Pill { tone: look; text: i18n("Accounts"); onClicked: sheet.open("users") }
        }
        SettingsControls.SettingRow {
            tone: look
            title: i18n("Lock when you step away")
            SettingsControls.Pill { tone: look; text: i18n("Screen lock"); onClicked: sheet.open("power#lock") }
        }
    }

    SettingsControls.Caption { tone: look; text: i18n("Updates & recovery") }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            id: updateRow
            tone: look
            objectName: "search-security-updates"
            divider: false
            readonly property string automatic: safetyCard.s.autoUpdates || "unknown"
            readonly property bool ready: safetyCard.s.updateWaiting === true
            readonly property bool failed: safetyCard.s.lastUpdateFailed === true
            readonly property bool nothingStaged: safetyCard.s.updateWaiting === false
            title: i18n("Automatic updates")
            detail: !sheet.securityChecked ? ""
                : ready ? i18n("An update is ready. It's used from the next restart.")
                : failed ? i18n("The last automatic update failed.")
                : automatic === "off" ? i18n("Only when you ask, so fixes for security holes wait until then.")
                : automatic === "on" && nothingStaged ? i18n("Monet checks for updates in the background.")
                : automatic === "unavailable" ? i18n("Automatic updates are unavailable on this installation.")
                : i18n("Couldn’t check automatic updates.")
            lead: SettingsControls.Mark {
                objectName: "security-update-mark"
                tone: look
                known: updateRow.ready || updateRow.failed || updateRow.automatic === "off" || good
                good: updateRow.automatic === "on" && updateRow.nothingStaged && !updateRow.failed
            }
            SettingsControls.Pill {
                objectName: "security-update-action"
                tone: look
                visible: updateRow.ready || updateRow.failed || updateRow.automatic === "off"
                enabledPill: sheet.securityFixing === ""
                text: updateRow.ready ? i18n("Restart") : updateRow.failed ? i18n("Open Updates") : i18n("Turn on")
                onClicked: {
                    if (updateRow.ready) {
                        sheet.fixSecurity("restart")
                    } else if (updateRow.failed) {
                        sheet.open("updates#update-history")
                    } else {
                        sheet.fixSecurity("auto-updates on")
                    }
                }
            }
        }
        SettingsControls.SettingRow {
            tone: look
            title: i18n("Firmware")
            detail: sheet.firmwareState === "unavailable" ? i18n("Firmware updates are unavailable on this installation.")
                : sheet.firmwareState === "none" ? i18n("No firmware updates were offered for this PC.")
                : sheet.firmwareState === "available" ? sheet.firmwareTitle() + ". " + sheet.firmwareDetail()
                : sheet.firmwareState === "checking" || sheet.firmwareState === "" ? i18n("Looking for updates for this PC's own parts…")
                : sheet.firmwareDetail()
            lead: SettingsControls.Mark {
                tone: look
                known: sheet.firmwareState !== "checking" && sheet.firmwareState !== "" && sheet.firmwareState !== "failed" && sheet.firmwareState !== "unavailable"
                good: sheet.firmwareState === "none" || (sheet.firmwareState === "done" && !sheet.firmwareRestart)
            }
            SettingsControls.Pill {
                tone: look
                visible: sheet.firmwareState === "available" || sheet.firmwareState === "installing"
                    || sheet.firmwareState === "failed" || (sheet.firmwareState === "done" && sheet.firmwareRestart)
                enabledPill: sheet.firmwareState !== "installing" && (sheet.firmwareState !== "done" || sheet.securityFixing === "")
                    && (sheet.firmwareState !== "available" || sheet.firmware.some(f => !f.blocked))
                text: sheet.firmwareState === "installing" ? i18n("Installing…")
                    : sheet.firmwareState === "done" ? i18n("Restart now")
                    : sheet.firmwareState === "failed" ? i18n("Try again")
                    : i18n("Install")
                onClicked: sheet.firmwareState === "done" ? sheet.fixSecurity("restart")
                    : sheet.firmwareState === "failed" ? sheet.checkFirmware()
                    : sheet.installFirmware()
            }
        }
        SettingsControls.SettingRow {
            tone: look
            title: i18n("Backups")
            detail: safetyCard.s.versions === false ? i18n("Earlier versions of files are turned off.")
                : safetyCard.s.versions === true && safetyCard.s.drive ? i18n("Earlier versions of your files every hour, and copies on %1.", safetyCard.s.drive)
                : safetyCard.s.versions === true ? i18n("Earlier versions of your files every hour. Copies on a USB drive keep them safe from a broken disk too.")
                : ""
            lead: SettingsControls.Mark {
                tone: look
                known: typeof safetyCard.s.versions === "boolean"
                good: safetyCard.s.versions === true
            }
            SettingsControls.Pill {
                tone: look
                visible: safetyCard.s.versions === false || (safetyCard.s.versions === true && !safetyCard.s.drive)
                enabledPill: sheet.securityFixing === ""
                text: safetyCard.s.versions === false ? (sheet.securityFixing === "keep on" ? i18n("Turning on…") : i18n("Turn on"))
                    : i18n("Add a drive…")
                onClicked: {
                    if (safetyCard.s.versions === false) {
                        sheet.fixSecurity("keep on")
                    } else {
                        sheet.page = "backups"
                    }
                }
            }
        }
    }

    SettingsControls.Caption { tone: look; text: i18n("Protection history") }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Recent activity")
            detail: !sheet.securityChecked ? ""
                : safetyCard.s.historyAvailable !== true ? i18n("Monet couldn’t read all of the local security log.")
                : (safetyCard.s.history || []).length ? i18n("Changes recorded on this PC.")
                : i18n("No recent security activity was found in the local log.")
        }
        Repeater {
            model: safetyCard.s.history || []
            SettingsControls.SettingRow {
                required property var modelData
                tone: look
                visible: title !== ""
                title: sheet.securityEvent(modelData.event)
                detail: new Date(modelData.time).toLocaleString(Qt.locale(), Locale.ShortFormat)
            }
        }
    }
    Text {
        Layout.fillWidth: true
        text: i18n("For Windows protections, open Windows Security in Windows.")
        color: look.dim
        font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
        wrapMode: Text.Wrap
    }
}
