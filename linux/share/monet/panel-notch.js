// The notch is a separate, content-sized top panel on the edited bar's screen.
// A one/three-bar conversion must never claim this containment or its applets.
(function () {
    var choice = MONET_NOTCH_CHOICE;
    var source = panels().find(p => p.id === MONET_PANEL_ID);
    if (!source) source = desktops().find(d => d.id === MONET_PANEL_ID);
    var type = "org.monet.notch";
    if (!source || source.screen < 0) { print(JSON.stringify({ok:false})); return; }
    var existing = panels().filter(function (p) {
        return p.screen === source.screen && p.widgets(type).length;
    });
    if (existing.length > 1) { print(JSON.stringify({ok:false})); return; }
    var panel = existing[0], widget = panel && panel.widgets(type)[0];
    var removedWidget = 0;
    var defaultTabs = ["music", "activity", "time", "calendar", "notes", "clipboard", "tools", "agents", "notifications"];
    var names = defaultTabs.concat("camera");
    var defaults = {hoverControls:true, autoHide:false, combined:true, levels:false, companion:false, alerts:true, previews:false, gestures:true, awake:true, countdown:true, openActivity:true};
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
    var layoutDefaults = {expandedWidth:464, toolHeight:420, leftRail:"time", rightRail:"controls,mixer,files", reopen:"sections"};
    var railNames = ["controls","mixer","files","music","activity","time","calendar","notes","camera","clipboard","tools","agents","notifications"];
    function validRail(value) {
        var rows = value === "none" ? [] : String(value).split(",");
        return rows.length <= 4 && rows.every((key, index) => railNames.indexOf(key) >= 0 && rows.indexOf(key) === index);
    }
    function layoutOf(w) {
        var result = {};
        Object.keys(layoutDefaults).forEach(function(key) {
            var value = w ? w.readConfig(key, layoutDefaults[key]) : layoutDefaults[key];
            result[key] = typeof layoutDefaults[key] === "number" ? Number(value) : String(value);
        });
        return result;
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
    var setting = /^(levels|companion|alerts|previews|gestures|awake|countdown|hoverControls|autoHide|combined|openActivity)-(on|off)$/.exec(choice || "");
    var tab = /^tab-(music|activity|time|calendar|notes|camera|clipboard|tools|agents|notifications)-(show|hide|earlier|later)$/.exec(choice || "");
    var companion = /^companion-([a-z]+)-([a-z]+)$/.exec(choice || "");
    if (companion && (!Object.prototype.hasOwnProperty.call(companionFields, companion[1]) ||
            companionFields[companion[1]].indexOf(companion[2]) < 0)) { print(JSON.stringify({ok:false})); return; }
    var size = /^(expandedWidth|toolHeight)-([0-9]+)$/.exec(choice || "");
    var dimensions = /^size-([0-9]+)-([0-9]+)$/.exec(choice || "");
    var rail = /^rail-(left|right)-([a-z,]+)$/.exec(choice || "");
    var reopen = /^reopen-(sections|last)$/.exec(choice || "");
    if (size && (Number(size[2]) < (size[1] === "expandedWidth" ? 340 : 316) || Number(size[2]) > 640)
            || dimensions && (Number(dimensions[1]) < 340 || Number(dimensions[1]) > 640 || Number(dimensions[2]) < 316 || Number(dimensions[2]) > 640)
            || rail && !validRail(rail[2])) { print(JSON.stringify({ok:false})); return; }
    var tabOrder = /^tabs-([a-z,]+)$/.exec(choice || "");
    if (tabOrder && (tabOrder[1] !== "none" && (tabsOf(tabOrder[1]).join(",") !== tabOrder[1]))) { print(JSON.stringify({ok:false})); return; }
    if (tab || setting || companion || size || dimensions || rail || reopen || tabOrder) {
        if (!widget) { print(JSON.stringify({ok:false})); return; }
        widget.currentConfigGroup = ["General"];
        if (dimensions) {
            widget.writeConfig("expandedWidth", Number(dimensions[1]));
            widget.writeConfig("toolHeight", Number(dimensions[2]));
        }
        else if (tabOrder) widget.writeConfig("tabs", tabOrder[1]);
        else if (size) widget.writeConfig(size[1], Number(size[2]));
        else if (rail) widget.writeConfig(rail[1]+"Rail", rail[2]);
        else if (reopen) widget.writeConfig("reopen", reopen[1]);
        else if (tab) {
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
    } else if (choice === "hello") {
        if (!widget) { print(JSON.stringify({ok:false})); return; }
        widget.currentConfigGroup = ["General"];
        if (!optionsOf(widget).companion) { print(JSON.stringify({ok:false})); return; }
        widget.writeConfig("companionGreeting", String(Date.now()));
        widget.reloadConfig();
    } else if (choice === "off" && widget) {
        widget.currentConfigGroup = ["General"];
        removedWidget = widget.id;
        var preferences = optionsOf(widget);
        preferences.wide = String(widget.readConfig("wide", false)) === "true";
        preferences.companionSettings = companionOf(widget);
        preferences.layout = layoutOf(widget);
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
    } else if (choice && choice !== "off" && (choice !== "add" || !widget)) {
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
                widget = panel.addWidget(MONET_NOTCH_PACKAGE);
                if (!widget || widget.type !== type) throw new Error("widget");
                widget.currentConfigGroup = ["General"];
                Object.keys(defaults).forEach(function (key) {
                    if (typeof previous[key] === "boolean") widget.writeConfig(key, previous[key]);
                });
                Object.keys(layoutDefaults).forEach(function(key) {
                    var value = previous.layout && previous.layout[key];
                    if (key === "expandedWidth" || key === "toolHeight") {
                        if (Number.isInteger(value) && value >= (key === "expandedWidth" ? 340 : 316) && value <= 640) widget.writeConfig(key,value);
                    } else if (key === "reopen") {
                        if (value === "last" || value === "sections") widget.writeConfig(key,value);
                    } else if (typeof value === "string" && validRail(value)) widget.writeConfig(key,value);
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
        widget.writeConfig("wide", choice === "wide" || (choice === "add" && previous.wide === true)); widget.reloadConfig();
    }
    if (widget) widget.currentConfigGroup = ["General"];
    var wide = widget && String(widget.readConfig("wide", false)) === "true";
    var visibleTabs = widget ? tabsOf(widget.readConfig("tabs", "")) : [];
    var result = {ok:true, options:optionsOf(widget), tabs:visibleTabs, mode: !widget ? "off" : wide ? "wide" : "compact"};
    result.companionSettings = companionOf(widget);
    result.layout = layoutOf(widget);
    if (removedWidget) result.removedWidget = removedWidget;
    print(JSON.stringify(result));
})();
