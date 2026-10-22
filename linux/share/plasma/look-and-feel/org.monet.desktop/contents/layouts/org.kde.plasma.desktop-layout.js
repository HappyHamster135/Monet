// Monet's desktop: the painting, a placard with the time, and three glass
// islands along the bottom.
//
//   left:    the Monet menu and Windows Games
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
    set(p, "hiding", "none")
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
    "applications:org.kde.discover.desktop",
    "applications:monet-settings.desktop"
])
tasks.writeConfig("showOnlyCurrentDesktop", false)
tasks.writeConfig("indicateAudioStreams", true)
tasks.writeConfig("iconSpacing", 1)
middle.addWidget("org.kde.plasma.marginsseparator")
middle.addWidget("org.kde.plasma.trash")

var right = island("right")
right.addWidget("org.monet.quick")
right.addWidget("org.kde.plasma.systemtray")
right.addWidget("org.monet.clock")
