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

// Executed by monet-quick inside Plasma. Move applets, never recreate users' pins.
(function () {
    var selected = panelById(MONET_PANEL_ID), choice = MONET_PANEL_CHOICE, plan = MONET_PANEL_PLAN;
    function reply(value) { print(JSON.stringify(value)); }
    if (!selected || selected.screen < 0) { reply({ok:false}); return; }
    var roles = ["left", "middle", "right"];
    function read(object, key, fallback) {
        object.currentConfigGroup = ["MonetBar"];
        return String(object.readConfig(key, fallback));
    }
    function write(object, key, value) {
        object.currentConfigGroup = ["MonetBar"]; object.writeConfig(key, value);
    }
    function locate(id) {
        var found = null;
        panels().some(function (p) {
            var w = p.widgetById(id);
            if (w) { found = {widget:w, panel:p}; return true; }
            return false;
        });
        return found;
    }
    function later() { reply({ok:true, pending:plan}); }
    if (plan) {
        if (plan.rollback) {
            // Restore ownership one widget per event-loop turn, too.
            for (var i = 0; i < plan.original.length; i++) {
                var original = plan.original[i], found = locate(original.id), home = panelById(original.panel);
                if (!found || !home) { reply({ok:false}); return; }
                if (found.panel.id !== home.id) {
                    home.addWidget(found.widget); later(); return;
                }
            }
            plan.added.forEach(function (id) { var found = locate(id); if (found) found.widget.remove(); });
            plan.members.forEach(function (id) {
                plan.original.filter(function (r) { return r.panel === id; }).reverse().forEach(function (r) {
                    var found = locate(r.id); if (found) found.widget.index = 0;
                });
            });
            plan.created.forEach(function (id) { var p = panelById(id); if (p && !p.widgets().length) p.remove(); });
            reply({ok:false}); return;
        }
        try {
            // Plasma saves AppletOrder with Qt.callLater. Wait for its view to
            // register every applet before moving the next one or reordering.
            var ready = plan.order.every(function (entry) {
                var p = panelById(entry.panel);
                if (!p) throw new Error("panel removed");
                return p.widgets().every(function (w) { return w.index >= 0; });
            });
            if (!ready) { later(); return; }
            if (plan.next < plan.moves.length) {
                var move = plan.moves[plan.next], found = locate(move.id), target = panelById(move.to);
                if (!found || !target) throw new Error("widget removed");
                if (found.panel.id !== target.id) target.addWidget(found.widget);
                if (!target.widgetById(move.id)) throw new Error("move");
                plan.next++; later(); return;
            }
            var orders = {};
            plan.order.forEach(function (entry) {
                if (!orders[entry.panel]) orders[entry.panel] = [];
                orders[entry.panel] = orders[entry.panel].concat(entry.ids);
            });
            Object.keys(orders).forEach(function (id) {
                var p = panelById(Number(id));
                orders[id].slice().reverse().forEach(function (id) {
                    var w = p.widgetById(id); if (!w || w.index < 0) throw new Error("placement");
                    w.index = 0;
                });
            });
            // All applets must be visibly registered before their old panels go.
            if (plan.choice === "one" && plan.members.some(function (id) {
                var p = panelById(id); return id !== selected.id && p && p.widgets().length;
            })) throw new Error("remaining");
            plan.order.forEach(function (entry) {
                var p = panelById(entry.panel);
                entry.ids.forEach(function (id) { write(p.widgetById(id), "role", entry.role); });
                write(p, "group", plan.group); write(p, "role", plan.choice === "one" ? "one" : entry.role);
                p.alignment = plan.choice === "one" || entry.role === "middle" ? "center" : entry.role;
                p.offset = plan.choice === "one" || entry.role === "middle" ? 0 : 16;
                p.floating = plan.choice === "three";
                p.lengthMode = plan.choice === "one" ? "fill" : "fit";
            });
            if (plan.choice === "one") plan.members.forEach(function (id) {
                var p = panelById(id); if (p && id !== selected.id) p.remove();
            });
            reply({ok:true, available:true, layout:plan.choice}); return;
        } catch (error) { plan.rollback = true; later(); return; }
    }
    function has(p, type) { return p.widgets(type).length > 0; }
    function role(p) {
        var found = [];
        if (has(p, "org.monet.menu")) found.push("left");
        if (has(p, "org.kde.plasma.icontasks") || has(p, "org.kde.plasma.taskmanager")) found.push("middle");
        if (has(p, "org.monet.quick")) found.push("right");
        return found.length > 1 ? "one" : found[0] || read(p, "role", "");
    }
    var group = read(selected, "group", ""), current = role(selected);
    var members = [selected], assigned = {}, ambiguous = false;
    if (current !== "one" && current !== "") {
        members = panels().filter(function (p) {
            return p.screen === selected.screen && p.location === selected.location
                && (group ? read(p, "group", "") === group : read(p, "group", "") === "" && roles.indexOf(role(p)) >= 0);
        });
        members.forEach(function (p) {
            var r = role(p);
            if (assigned[r]) ambiguous = true;
            assigned[r] = p;
        });
    }
    var layout = members.length > 1 ? "three" : "one";
    if (choice === null || ambiguous) { reply({ok:true, available:!ambiguous, layout:layout}); return; }
    if (choice !== "one" && choice !== "three") { reply({ok:false}); return; }
    var required = {
        left:["org.monet.menu", "org.monet.games"],
        middle:["org.kde.plasma.icontasks", "org.kde.plasma.marginsseparator", "org.kde.plasma.trash"],
        right:["org.monet.weather", "org.monet.quick", "org.monet.sound", "org.kde.plasma.systemtray", "org.monet.clock"]
    };
    var rows = [], buckets = {left:[], middle:[], right:[]}, added = [], created = [];
    members.forEach(function (p) {
        var r = role(p);
        p.widgets().sort(function (a,b) { return a.index - b.index; }).forEach(function (w) {
            var home = roles.indexOf(r) >= 0 ? r : read(w, "role", "");
            if (roles.indexOf(home) < 0) {
                home = roles.find(function (key) { return required[key].indexOf(w.type) >= 0; }) || "middle";
                if (w.type === "org.monet.transfers") home = "right";
            }
            var row = {widget:w, panel:p, index:w.index, role:home};
            rows.push(row); buckets[home].push(row);
        });
    });
    function exists(type) {
        return rows.some(function (r) { return r.widget.type === type
            || type === "org.kde.plasma.icontasks" && r.widget.type === "org.kde.plasma.taskmanager"; });
    }
    var missing = [];
    roles.forEach(function (r) { required[r].forEach(function (type) { if (!exists(type)) missing.push({type:type, role:r}); }); });
    if (missing.some(function (w) { return knownWidgetTypes.indexOf(w.type) < 0; })) { reply({ok:false}); return; }
    var destinations = {}, groupId = group || String(selected.id);
    try {
        // Keep the edited panel alive, including when starting from either side island.
        if (choice === "one") roles.forEach(function (r) { destinations[r] = selected; });
        else {
            roles.forEach(function (r) {
                var p = assigned[r];
                if (!p && ((current === "one" || current === "") && r === "middle" || current === r)) p = selected;
                if (!p) {
                    p = new Panel; created.push(p);
                    p.screen = selected.screen; p.location = selected.location;
                    p.height = selected.height; p.hiding = selected.hiding;
                }
                destinations[r] = p;
            });
        }
        missing.forEach(function (entry) {
            var p = destinations[entry.role], w = p.addWidget(entry.type);
            if (!w || !w.id || w.type !== entry.type) throw new Error("create");
            added.push(w);
            if (entry.type === "org.monet.menu") {
                w.currentConfigGroup = ["Shortcuts"]; w.writeConfig("global", "Alt+F1");
            } else if (entry.type === "org.kde.plasma.icontasks") {
                w.currentConfigGroup = ["General"];
                w.writeConfig("launchers", ["preferred://filemanager", "preferred://browser", "applications:steam.desktop",
                    "applications:org.kde.konsole.desktop", "applications:monet-store.desktop", "applications:monet-settings.desktop"]);
                w.writeConfig("showOnlyCurrentDesktop", false); w.writeConfig("indicateAudioStreams", true); w.writeConfig("iconSpacing", 1);
            } else if (entry.type === "org.kde.plasma.systemtray") monetTray(w);
            w.reloadConfig();
            var row = {widget:w, panel:p, role:entry.role};
            // Put a newly restored menu/task manager before any existing extras.
            if (entry.type === "org.monet.menu" || entry.type === "org.kde.plasma.icontasks") buckets[entry.role].unshift(row);
            else buckets[entry.role].push(row);
        });
        plan = {choice:choice, group:groupId, next:0, moves:[], order:[],
            members:members.map(function (p) { return p.id; }),
            created:created.map(function (p) { return p.id; }),
            added:added.map(function (w) { return w.id; }),
            original:rows.map(function (r) { return {id:r.widget.id, panel:r.panel.id}; })};
        roles.forEach(function (r) {
            var p = destinations[r];
            plan.order.push({panel:p.id, role:r, ids:buckets[r].map(function (row) { return row.widget.id; })});
            buckets[r].forEach(function (row) {
                if (row.panel.id !== p.id) plan.moves.push({id:row.widget.id, to:p.id});
            });
        });
    } catch (error) {
        // An unavailable widget or failed move must leave the old layout usable.
        rows.forEach(function (row) {
            if (!row.panel.widgetById(row.widget.id)) row.panel.addWidget(row.widget);
        });
        added.forEach(function (w) { w.remove(); });
        members.forEach(function (p) {
            rows.filter(function (r) { return r.panel.id === p.id; }).reverse().forEach(function (r) { r.widget.index = 0; });
        });
        created.forEach(function (p) { if (!p.widgets().length) p.remove(); });
        reply({ok:false}); return;
    }
    later();
})();
