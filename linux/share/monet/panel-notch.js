// The notch is a separate, content-sized top panel on the edited bar's screen.
// A one/three-bar conversion must never claim this containment or its applets.
(function () {
    var source = panelById(MONET_PANEL_ID), choice = MONET_NOTCH_CHOICE;
    var type = "org.monet.notch";
    if (!source) { print(JSON.stringify({ok:false})); return; }
    var existing = panels().filter(function (p) {
        return p.screen === source.screen && p.widgets(type).length;
    });
    if (existing.length > 1) { print(JSON.stringify({ok:false})); return; }
    var panel = existing[0], widget = panel && panel.widgets(type)[0];
    var setting = /^(levels|companion|alerts|previews|gestures)-(on|off)$/.exec(choice || "");
    if (setting) {
        if (!widget) { print(JSON.stringify({ok:false})); return; }
        widget.currentConfigGroup = ["General"];
        widget.writeConfig(setting[1], setting[2] === "on"); widget.reloadConfig();
    } else if (choice === "off" && widget) {
        panel.currentConfigGroup = ["MonetNotch"];
        if (panel.readConfig("owned", "") === "yes" && panel.widgets().length === 1) { widget.remove(); panel.remove(); }
        else widget.remove();
        widget = null;
    } else if (choice && choice !== "off") {
        if (!widget) {
            if (knownWidgetTypes.indexOf(type) < 0) { print(JSON.stringify({ok:false})); return; }
            panel = new Panel;
            try {
                panel.screen = source.screen;
                panel.location = "top"; panel.alignment = "center"; panel.offset = 0;
                panel.height = 32; panel.floating = false; panel.lengthMode = "fit";
                panel.hiding = "windowsgobelow";
                panel.currentConfigGroup = ["MonetNotch"]; panel.writeConfig("owned", "yes");
                widget = panel.addWidget(type);
                if (!widget || widget.type !== type) throw new Error("widget");
            } catch (error) { panel.remove(); print(JSON.stringify({ok:false})); return; }
        }
        widget.currentConfigGroup = ["General"];
        widget.writeConfig("wide", choice === "wide"); widget.reloadConfig();
    }
    if (widget) widget.currentConfigGroup = ["General"];
    var wide = widget && String(widget.readConfig("wide", false)) === "true";
    var options = {};
    ["levels", "companion", "alerts", "previews", "gestures"].forEach(function (key) {
        options[key] = !!widget && String(widget.readConfig(key, key === "alerts" || key === "gestures")) === "true";
    });
    print(JSON.stringify({ok:true, options:options, mode: !widget ? "off" : wide ? "wide" : "compact"}));
})();
