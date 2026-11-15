// Monet's desktop: the painting, a placard with the time, and three glass
// islands along the bottom.
//
//   left:    the Monet menu and Games
//   middle:  your apps and open windows, then Trash
//   right:   quick settings, status icons and the clock

function set(object, key, value) {
    // Newer panel options; older Plasma versions keep their default.
    try { object[key] = value } catch (e) {}
}

function island(alignment) {
    var p = new Panel
    p.location = "bottom"
    p.height = 2 * Math.round(gridUnit * 3.3 / 2)
    p.alignment = alignment
    set(p, "lengthMode", "fit")
    set(p, "floating", true)
    // Out of the way when a window comes over it, back when you point at the bottom of the
    // screen (with any pointer: monet-look). Light & Wallpaper's "Bar steps aside" keeps it in view.
    set(p, "hiding", "dodgewindows")
    return p
}

// The painting that changes with the hours, the placard, and the weather and
// the month at the top right, the way a desk keeps them.
var desktops = desktopsForActivity(currentActivity())
for (var i = 0; i < desktops.length; i++) {
    var d = desktops[i]
    d.wallpaperPlugin = "org.monet.hours"
    d.currentConfigGroup = ["General"]
    d.writeConfig("iconSize", 3)
    d.addWidget("org.monet.placard", gridUnit * 3, gridUnit * 3, gridUnit * 24, gridUnit * 12)
    var width = 1920
    try { width = screenGeometry(d.screen).width } catch (e) {}
    var right = width - gridUnit * 22
    d.addWidget("org.monet.weather", right, gridUnit * 3, gridUnit * 19, gridUnit * 10)
    d.addWidget("org.monet.calendar", right + gridUnit * 7, gridUnit * 14, gridUnit * 12, gridUnit * 12)
}

var left = island("left")
var menu = left.addWidget("org.monet.menu")
menu.currentConfigGroup = ["Shortcuts"]
menu.writeConfig("global", "Alt+F1")
left.addWidget("org.monet.games")

var middle = island("center")
var tasks = middle.addWidget("org.kde.plasma.icontasks")
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
middle.addWidget("org.kde.plasma.marginsseparator")
middle.addWidget("org.kde.plasma.trash")

var right = island("right")
right.addWidget("org.monet.weather")
right.addWidget("org.monet.quick")
right.addWidget("org.monet.sound")
var tray = right.addWidget("org.kde.plasma.systemtray")
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
right.addWidget("org.monet.clock")
