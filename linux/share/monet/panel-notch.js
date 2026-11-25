// The notch is a separate, content-sized top panel on the edited bar's screen.
// A one/three-bar conversion must never claim this containment or its applets.
(function () {
    var source = panelById(MONET_PANEL_ID), choice = MONET_NOTCH_CHOICE;
    var type = "org.monet.notch";
    if (!source || source.screen < 0) { print(JSON.stringify({ok:false})); return; }
    var existing = panels().filter(function (p) {
        return p.screen === source.screen && p.widgets(type).length;
    });
    if (existing.length > 1) { print(JSON.stringify({ok:false})); return; }
    var panel = existing[0], widget = panel && panel.widgets(type)[0];
    var removedWidget = 0;
    var defaultTabs = ["music", "activity", "time", "calendar", "notes"];
    var names = defaultTabs.concat("camera", "clipboard");
    var defaults = {levels:false, companion:false, alerts:true, previews:false, gestures:true};
    var companionFields = {style:["soft","robot"], shape:["round","egg","square","pill"],
        color:["mint","pearl","lemon","peach","rose","lilac","sky"], side:["left","right"],
        visits:["normal","rare","frequent","off"], reactions:["on","off"], rest:["show","hide"]};
    function companionKey(field) { return "companion" + field[0].toUpperCase() + field.slice(1); }
    function companionOf(w) {
        var values = {};
        Object.keys(companionFields).forEach(function (field) {
            var choices = companionFields[field], value = w && String(w.readConfig(companionKey(field), choices[0]));
            values[field] = choices.indexOf(value) >= 0 ? value : choices[0];
        });
        return values;
    }
    var timeDefaults = {timerMinutes:25, focusSessions:1, shortBreakMinutes:5, longBreakMinutes:15, longBreakEvery:4};
    function tabsOf(value) {
        if (value === "none") return [];
        var keys = String(value || "").split(",");
        return keys.length && keys.every(function (key, i) {
            return names.indexOf(key) >= 0 && keys.indexOf(key) === i;
        }) ? keys : defaultTabs.slice();
    }
    function optionsOf(w) {
        var options = {};
        Object.keys(defaults).forEach(function (key) {
            options[key] = !!w && String(w.readConfig(key, defaults[key])) === "true";
        });
        return options;
    }
    function savedOnBar() {
        // The menu applet keeps its identity during one/three-bar conversions.
        // With a custom bar that has no menu, use the edited containment.
        var bars = panels().filter(function (p) {
            return p.screen === source.screen && (!panel || p.id !== panel.id || p.widgets().length > 1);
        });
        var menuBar = bars.find(function (p) { return p.widgets("org.monet.menu").length; });
        var host = bars.find(function (p) { return p.id === source.id; }) || bars[0];
        if (menuBar) host = menuBar.widgets("org.monet.menu")[0];
        if (host) host.currentConfigGroup = ["MonetNotchPreferences"];
        return host;
    }
    var setting = /^(levels|companion|alerts|previews|gestures)-(on|off)$/.exec(choice || "");
    var tab = /^tab-(music|activity|time|calendar|notes|camera|clipboard)-(show|hide|earlier|later)$/.exec(choice || "");
    var companion = /^companion-([a-z]+)-([a-z]+)$/.exec(choice || "");
    if (companion && (!Object.prototype.hasOwnProperty.call(companionFields, companion[1]) ||
            companionFields[companion[1]].indexOf(companion[2]) < 0)) { print(JSON.stringify({ok:false})); return; }
    if (tab || setting || companion) {
        if (!widget) { print(JSON.stringify({ok:false})); return; }
        widget.currentConfigGroup = ["General"];
        if (tab) {
            var tabs = tabsOf(widget.readConfig("tabs", ""));
            var index = tabs.indexOf(tab[1]), action = tab[2];
            if (action === "show" && index < 0) tabs.push(tab[1]);
            if (action === "hide" && index >= 0) tabs.splice(index, 1);
            var next = index + (action === "earlier" ? -1 : 1);
            if ((action === "earlier" || action === "later") && index >= 0 && next >= 0 && next < tabs.length) {
                tabs.splice(next, 0, tabs.splice(index, 1)[0]);
            }
            widget.writeConfig("tabs", tabs.join(",") || "none");
        } else if (companion) widget.writeConfig(companionKey(companion[1]), companion[2]);
        else widget.writeConfig(setting[1], setting[2] === "on");
        widget.reloadConfig();
    } else if (choice === "off" && widget) {
        widget.currentConfigGroup = ["General"];
        removedWidget = widget.id;
        var preferences = optionsOf(widget);
        preferences.companionSettings = companionOf(widget);
        preferences.tabs = tabsOf(widget.readConfig("tabs", "")).join(",") || "none";
        Object.keys(timeDefaults).forEach(function (key) {
            preferences[key] = Number(widget.readConfig(key, timeDefaults[key]));
        });
        var host = savedOnBar();
        if (host) host.writeConfig("choices", JSON.stringify(preferences));
        panel.currentConfigGroup = ["MonetNotch"];
        if (panel.readConfig("owned", "") === "yes" && panel.widgets().length === 1) { widget.remove(); panel.remove(); }
        else widget.remove();
        widget = null;
    } else if (choice && choice !== "off") {
        if (!widget) {
            if (knownWidgetTypes.indexOf(type) < 0) { print(JSON.stringify({ok:false})); return; }
            var host = savedOnBar(), previous = {};
            try { previous = JSON.parse(host && host.readConfig("choices", "{}")) || {}; } catch (_) {}
            panel = new Panel;
            try {
                panel.screen = source.screen;
                panel.location = "top"; panel.alignment = "center"; panel.offset = 0;
                panel.height = 32; panel.floating = false; panel.lengthMode = "fit";
                panel.hiding = "windowsgobelow";
                panel.currentConfigGroup = ["MonetNotch"]; panel.writeConfig("owned", "yes");
                widget = panel.addWidget(type);
                if (!widget || widget.type !== type) throw new Error("widget");
                widget.currentConfigGroup = ["General"];
                Object.keys(defaults).forEach(function (key) {
                    if (typeof previous[key] === "boolean") widget.writeConfig(key, previous[key]);
                });
                Object.keys(companionFields).forEach(function (field) {
                    var value = previous.companionSettings && previous.companionSettings[field];
                    if (companionFields[field].indexOf(value) >= 0) widget.writeConfig(companionKey(field), value);
                });
                Object.keys(timeDefaults).forEach(function (key) {
                    var max = key === "focusSessions" || key === "longBreakEvery" ? 24 : 1440;
                    if (Number.isInteger(previous[key]) && previous[key] >= 1 && previous[key] <= max)
                        widget.writeConfig(key, previous[key]);
                });
                if (typeof previous.tabs === "string") widget.writeConfig("tabs", tabsOf(previous.tabs).join(",") || "none");
            } catch (error) { panel.remove(); print(JSON.stringify({ok:false})); return; }
        }
        widget.currentConfigGroup = ["General"];
        widget.writeConfig("wide", choice === "wide"); widget.reloadConfig();
    }
    if (widget) widget.currentConfigGroup = ["General"];
    var wide = widget && String(widget.readConfig("wide", false)) === "true";
    var visibleTabs = widget ? tabsOf(widget.readConfig("tabs", "")) : [];
    var result = {ok:true, options:optionsOf(widget), tabs:visibleTabs, mode: !widget ? "off" : wide ? "wide" : "compact"};
    result.companionSettings = companionOf(widget);
    if (removedWidget) result.removedWidget = removedWidget;
    print(JSON.stringify(result));
})();
