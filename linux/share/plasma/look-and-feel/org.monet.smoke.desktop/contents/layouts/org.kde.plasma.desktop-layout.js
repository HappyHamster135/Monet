// Monet's painting, desktop cards and one bottom bar.

function addDesktopCard(desktop, plugin) {
    // Use the live containment to place the cards once Plasma knows the screen.
    var card = desktop.addWidget(plugin)
    card.currentConfigGroup = ["General"]
    card.writeConfig("monetDefaultPlacement", true)
    card.reloadConfig()
}

var desktops = desktopsForActivity(currentActivity())
for (var i = 0; i < desktops.length; i++) {
    var d = desktops[i]
    d.wallpaperPlugin = "org.monet.hours"
    d.currentConfigGroup = ["General"]
    d.writeConfig("iconSize", 3)
    addDesktopCard(d, "org.monet.placard")
    addDesktopCard(d, "org.monet.weather")
    addDesktopCard(d, "org.monet.calendar")
}

var bar = new Panel
bar.location = "bottom"
bar.height = 2 * Math.round(gridUnit * 3.3 / 2)
bar.alignment = "center"
bar.lengthMode = "fill"
bar.floating = false
bar.hiding = "dodgewindows"
bar.currentConfigGroup = ["General"]
bar.writeConfig("MonetBarRole", "single")

var menu = bar.addWidget("org.monet.menu")
menu.currentConfigGroup = ["Shortcuts"]
menu.writeConfig("global", "Alt+F1")
bar.addWidget("org.monet.games")
var tasks = bar.addWidget("org.kde.plasma.icontasks")
tasks.currentConfigGroup = ["General"]
tasks.writeConfig("launchers", [
    "preferred://filemanager",
    "preferred://browser",
    "applications:steam.desktop",
    "applications:org.kde.konsole.desktop",
    "applications:monet-store.desktop",
    "applications:monet-settings.desktop"
])
tasks.writeConfig("showOnlyCurrentDesktop", false)
tasks.writeConfig("indicateAudioStreams", true)
tasks.writeConfig("iconSpacing", 1)
bar.addWidget("org.kde.plasma.marginsseparator")
bar.addWidget("org.kde.plasma.trash")

bar.addWidget("org.monet.weather")
bar.addWidget("org.monet.quick")
bar.addWidget("org.monet.sound")
bar.addWidget("org.monet.transfers")
var tray = bar.addWidget("org.kde.plasma.systemtray")
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

monetTray(tray)
bar.addWidget("org.monet.clock")
