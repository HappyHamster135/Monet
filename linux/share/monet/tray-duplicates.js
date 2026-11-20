// Once on existing Monet panels: one entry point for connectivity and brightness
// in Quick Settings, and one sound control. Network status and clipboard history
// remain in the tray overflow. Leave other panels and unrelated app icons alone.
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
        ["extraItems", "shownItems"].forEach(function (key) {
            tray.writeConfig(key, list(key).filter(function (id) { return duplicates.indexOf(id) < 0; }));
        });
        var overflow = quick ? ["org.kde.plasma.networkmanagement", "org.kde.plasma.clipboard"] : [];
        var hidden = list("hiddenItems");
        var hide = duplicates.concat(overflow);
        tray.writeConfig("hiddenItems", hidden.concat(hide.filter(function (id) { return hidden.indexOf(id) < 0; })));
        tray.writeConfig("shownItems", list("shownItems").filter(function (id) { return hide.indexOf(id) < 0; }));
        tray.reloadConfig();
    });
});
