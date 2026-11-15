// One upgrade repair on panels that already have Monet's sound control.
// Keep a standalone KDE volume control when Monet's was deliberately removed.
panels().forEach(function (panel) {
    var sound = panel.widgets("org.monet.sound");
    if (!panel.widgets("org.monet.quick").length || !sound.length) return;
    sound.slice(1).forEach(function (widget) { widget.remove(); });
    panel.widgets("org.kde.plasma.volume").forEach(function (widget) { widget.remove(); });
    panel.widgets("org.kde.plasma.systemtray").forEach(function (tray) {
        tray.currentConfigGroup = ["General"];
        function list(key) { return String(tray.readConfig(key, "")).split(",").filter(Boolean); }
        var volume = "org.kde.plasma.volume";
        var known = list("knownItems");
        if (known.indexOf(volume) < 0) known.push(volume);
        tray.writeConfig("knownItems", known);
        ["extraItems", "shownItems", "hiddenItems"].forEach(function (key) {
            tray.writeConfig(key, list(key).filter(function (id) { return id !== volume; }));
        });
        tray.reloadConfig();
    });
});
