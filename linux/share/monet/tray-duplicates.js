// Once on existing Monet panels: KDE's sound, Bluetooth and brightness items out of the
// tray when Monet's own controls sit beside it. Quick Settings has Bluetooth and the
// brightness slider; Monet's sound control replaces KDE's volume item. A panel without
// Monet's control keeps KDE's item, so nothing goes missing. Known but not chosen, or
// Plasma adds them back as new.
panels().forEach(function (panel) {
    var quick = panel.widgets("org.monet.quick").length > 0;
    var sound = panel.widgets("org.monet.sound").length > 0;
    var duplicates = (quick ? ["org.kde.plasma.bluetooth", "org.kde.plasma.brightness"] : [])
        .concat(sound ? ["org.kde.plasma.volume"] : []);
    if (!duplicates.length) return;
    panel.widgets("org.kde.plasma.systemtray").forEach(function (tray) {
        tray.currentConfigGroup = ["General"];
        function list(key) { return String(tray.readConfig(key, "")).split(",").filter(Boolean); }
        var known = list("knownItems");
        tray.writeConfig("knownItems", known.concat(duplicates.filter(function (id) { return known.indexOf(id) < 0; })));
        ["extraItems", "shownItems", "hiddenItems"].forEach(function (key) {
            tray.writeConfig(key, list(key).filter(function (id) { return duplicates.indexOf(id) < 0; }));
        });
        tray.reloadConfig();
    });
});
