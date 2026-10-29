// Everyday controls in view; specialist tools remain in Settings and Configure System Tray.
// Applied once when adopting Monet's look, never on --keep upgrades.
function monetTray(tray) {
    tray.currentConfigGroup = ["General"];
    function list(key) { return String(tray.readConfig(key, "")).split(",").filter(Boolean); }
    function union(a, b) { return a.concat(b.filter(function (id) { return a.indexOf(id) < 0; })); }
    var removed = ["org.kde.plasma.brightness", "org.kde.plasma.volume", "org.kde.plasma.weather",
        "org.kde.kscreen", "org.kde.plasma.manage-inputmethod", "org.kde.plasma.keyboardindicator",
        "org.kde.plasma.vault"];
    // Keyboard layout switching stays available for multilingual users. Camera/privacy
    // indicators, print jobs and other apps retain their normal active/passive behavior.
    var visible = ["org.kde.plasma.networkmanagement", "org.kde.plasma.bluetooth"];
    var enabled = visible.concat(["org.kde.plasma.notifications", "org.kde.plasma.battery",
        "org.kde.plasma.devicenotifier", "org.kde.plasma.clipboard"]);
    tray.writeConfig("knownItems", union(list("knownItems"), removed.concat(enabled)));
    tray.writeConfig("extraItems", union(list("extraItems").filter(function (id) { return removed.indexOf(id) < 0; }), enabled));
    tray.writeConfig("shownItems", union(list("shownItems").filter(function (id) { return removed.indexOf(id) < 0; }), visible));
    tray.writeConfig("hiddenItems", union(list("hiddenItems").filter(function (id) { return visible.indexOf(id) < 0; }), ["org.kde.plasma.clipboard"]));
    // Hide only its status icon; the compatibility service continues screen sharing.
    tray.writeConfig("disabledStatusNotifiers", union(list("disabledStatusNotifiers"), ["Xwayland Video Bridge"]));
    tray.reloadConfig();
}

panels().forEach(function (panel) {
    if (!panel.widgets("org.monet.quick").length) return;
    panel.widgets("org.kde.plasma.systemtray").forEach(monetTray);
    if (!panel.widgets("org.monet.weather").length) {
        var weather = panel.addWidget("org.monet.weather");
        weather.index = panel.widgets("org.monet.quick")[0].index;
    }
});
