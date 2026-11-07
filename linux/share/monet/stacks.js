// Virtual stacks hide folder-view icons; turning them off restores the old filter.
// Each desktop keeps its own receipt, so screens and activities are independent.
desktops().forEach(function (desktop) {
    if (desktop.type !== "org.kde.plasma.folder") return;
    if (typeof targetDesktop !== "undefined" && desktop.id !== targetDesktop) return;
    var widgets = desktop.widgets("org.monet.stacks");
    desktop.currentConfigGroup = ["MonetStacks"];
    var receipt = String(desktop.readConfig("previous", ""));
    if (typeof reconcile !== "undefined" && (widgets.length || !receipt)) return;
    if (typeof forceOn !== "undefined" && receipt) return;
    desktop.currentConfigGroup = ["General"];
    if ((widgets.length && typeof forceOn === "undefined") || typeof forceOff !== "undefined" || typeof reconcile !== "undefined") {
        // A later custom filter is a newer user choice.
        var ours = Number(desktop.readConfig("filterMode", 0)) === 2
            && String(desktop.readConfig("filterPattern", "*")) === "*";
        desktop.currentConfigGroup = ["MonetStacks"];
        var saved = String(desktop.readConfig("previous", ""));
        if (ours && saved) {
            var previous = JSON.parse(saved);
            desktop.currentConfigGroup = ["General"];
            desktop.writeConfig("filterMode", previous.mode);
            desktop.writeConfig("filterPattern", previous.pattern);
            desktop.writeConfig("filterMimeTypes", previous.mime);
        }
        desktop.currentConfigGroup = ["MonetStacks"];
        desktop.writeConfig("previous", "");
        widgets.forEach(function (widget) { widget.remove(); });
    } else {
        // Only the real Desktop, not a containment intentionally showing another folder.
        var url = String(desktop.readConfig("url", "desktop:/"));
        if (url !== "desktop:/" && url !== "desktop:") return;
        var previous = { mode: desktop.readConfig("filterMode", 0), pattern: desktop.readConfig("filterPattern", "*"),
                         mime: desktop.readConfig("filterMimeTypes", ["all/all"]) };
        desktop.currentConfigGroup = ["MonetStacks"];
        desktop.writeConfig("previous", JSON.stringify(previous));
        var widget = widgets.length ? widgets[0] : desktop.addWidget("org.monet.stacks", gridUnit * 3, gridUnit * 17, gridUnit * 27, gridUnit * 15);
        if (!widget) return;
        desktop.currentConfigGroup = ["General"];
        desktop.writeConfig("filterPattern", "*");
        desktop.writeConfig("filterMimeTypes", ["all/all"]);
        desktop.writeConfig("filterMode", 2);
    }
    desktop.reloadConfig();
});
