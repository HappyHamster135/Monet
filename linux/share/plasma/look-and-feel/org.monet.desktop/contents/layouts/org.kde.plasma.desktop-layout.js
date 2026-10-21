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

// The painting that changes with the hours, and the placard.
var desktops = desktopsForActivity(currentActivity())
for (var i = 0; i < desktops.length; i++) {
    var d = desktops[i]
    d.wallpaperPlugin = "org.monet.hours"
    d.currentConfigGroup = ["General"]
    d.writeConfig("iconSize", 3)
    d.addWidget("org.monet.placard", gridUnit * 3, gridUnit * 3, gridUnit * 24, gridUnit * 12)
}

var left = island("left")
var menu = left.addWidget("org.kde.plasma.kickoff")
menu.currentConfigGroup = ["General"]
menu.writeConfig("icon", "monet")
menu.writeConfig("favoritesDisplay", 0)
menu.writeConfig("applicationsDisplay", 0)
menu.writeConfig("showActionButtonCaptions", false)
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
    "applications:systemsettings.desktop"
])
tasks.writeConfig("showOnlyCurrentDesktop", false)
tasks.writeConfig("indicateAudioStreams", true)
tasks.writeConfig("iconSpacing", 1)
middle.addWidget("org.kde.plasma.marginsseparator")
middle.addWidget("org.kde.plasma.trash")

var right = island("right")
right.addWidget("org.monet.quick")
right.addWidget("org.kde.plasma.systemtray")
var clock = right.addWidget("org.kde.plasma.digitalclock")
clock.currentConfigGroup = ["Appearance"]
clock.writeConfig("showDate", true)
clock.writeConfig("dateDisplayFormat", 2)
clock.writeConfig("dateFormat", "custom")
clock.writeConfig("customDateFormat", "ddd d MMM")
