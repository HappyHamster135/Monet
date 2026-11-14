// Keep the task manager in place. Copy the side widgets because Plasma does
// not reliably reattach existing applets when a script moves them.
const menuType = "org.monet.menu";
const gamesType = "org.monet.games";
const quickType = "org.monet.quick";
const tasksType = "org.kde.plasma.icontasks";
const trashType = "org.kde.plasma.trash";
const separatorType = "org.kde.plasma.marginsseparator";
const trayType = "org.kde.plasma.systemtray";

function has(panel, type) {
    return panel.widgets(type).length > 0;
}

function barsByScreen() {
    const screens = {};
    const bottom = panels().filter(p => p.location === "bottom" && p.screen >= 0);
    bottom.forEach(p => {
        p.currentConfigGroup = ["General"];
        const role = p.readConfig("MonetBarRole", "");
        const menu = has(p, menuType), quick = has(p, quickType);
        if (!menu && !quick && !["single", "left", "right"].includes(role)) return;
        const bars = screens[p.screen] || (screens[p.screen] = {});
        if (role === "single" || (menu && quick && p.lengthMode === "fill")) bars.single = p;
        else if (role === "left" || menu) bars.left = p;
        else bars.right = p;
    });
    bottom.forEach(p => {
        const bars = screens[p.screen];
        if (!bars || !has(p, tasksType)) return;
        p.currentConfigGroup = ["General"];
        if (p.readConfig("MonetBarRole", "") === "middle" ||
                (!has(p, menuType) && !has(p, quickType) && has(p, trashType)
                && has(p, separatorType) && p.alignment === "center")) bars.middle = p;
    });
    return screens;
}

function barMode(bars) {
    if (bars.single) return "single";
    if (bars.left && bars.middle && bars.right) return "islands";
    return "incomplete";
}

function newBar(screen, reference) {
    const panel = new Panel;
    panel.screen = screen;
    panel.location = "bottom";
    panel.height = reference.height;
    return panel;
}

function styleBar(panel, role) {
    const single = role === "single";
    panel.alignment = role === "left" || role === "right" ? role : "center";
    panel.offset = 0;
    panel.lengthMode = single ? "fill" : "fit";
    panel.floating = !single;
    panel.hiding = dodge ? "dodgewindows" : "windowsgobelow";
    panel.currentConfigGroup = ["General"];
    panel.writeConfig("MonetBarRole", role);
}

function addTaskManager(panel) {
    const tasks = panel.addWidget(tasksType);
    tasks.currentConfigGroup = ["General"];
    tasks.writeConfig("launchers", [
        "preferred://filemanager", "preferred://browser", "applications:steam.desktop",
        "applications:org.kde.konsole.desktop", "applications:monet-store.desktop",
        "applications:monet-settings.desktop"
    ]);
    tasks.writeConfig("showOnlyCurrentDesktop", false);
    tasks.writeConfig("indicateAudioStreams", true);
    tasks.writeConfig("iconSpacing", 1);
    tasks.reloadConfig();
    panel.addWidget(separatorType);
    panel.addWidget(trashType);
}

function ordered(panel) {
    return panel ? panel.widgets().sort((a, b) => a.index - b.index) : [];
}

function copySettings(source, target, group) {
    source.currentConfigGroup = group;
    target.currentConfigGroup = group;
    source.configKeys.forEach(key => target.writeConfig(key, source.readConfig(key, "")));
    source.configGroups.forEach(child => copySettings(source, target, group.concat(child)));
}

function copyWidgets(widgets, panel) {
    const copies = [];
    try {
        widgets.forEach(w => {
            const copy = panel.addWidget(w.type);
            if (!copy || !copy.id) throw new Error("Could not add " + w.type);
            copies.push(copy);
            if (w.type === trayType) {
                // The tray owns a separate containment. Keep its preferences and let
                // Plasma create new instances of the internal status widgets.
                const from = desktopById(w.id);
                const to = desktopById(copy.id);
                if (from && to) copySettings(from, to, ["General"]);
                if (to) to.reloadConfig();
            } else copySettings(w, copy, []);
            copy.reloadConfig();
        });
        return copies;
    } catch (error) {
        copies.forEach(w => w.remove());
        throw error;
    }
}

function toSingle(bars, screen) {
    if (bars.single) return;
    if ([bars.left, bars.right].some(panel => panel?.locked)) throw new Error("Taskbar widgets are locked");
    const panel = bars.middle || newBar(screen, bars.left || bars.right);
    if (!bars.middle) addTaskManager(panel);
    const middle = ordered(panel);
    const left = ordered(bars.left);
    const right = ordered(bars.right);
    let copies;
    try {
        copies = copyWidgets(left.concat(right), panel);
    } catch (error) {
        if (!bars.middle) panel.remove();
        throw error;
    }
    const leftCopies = copies.slice(0, left.length);
    const rightCopies = copies.slice(left.length);
    left.concat(right).forEach((w, index) => {
        const shortcut = w.globalShortcut;
        if (shortcut) {
            w.globalShortcut = "";
            copies[index].globalShortcut = shortcut;
        }
    });
    [bars.left, bars.right].filter(Boolean).forEach(side => side.remove());
    leftCopies.concat(middle, rightCopies).forEach((w, index) => { w.index = index; });
    styleBar(panel, "single");
    panel.writeConfig("MonetBarLeftWidgets", leftCopies.map(w => w.id).join(","));
    panel.writeConfig("MonetBarRightWidgets", rightCopies.map(w => w.id).join(","));
}

function toIslands(bars, screen) {
    if (barMode(bars) === "islands") return;
    if (bars.single?.locked) throw new Error("Taskbar widgets are locked");
    const reference = bars.single || bars.left || bars.right;
    const left = bars.left || (bars.single ? newBar(screen, reference) : null);
    const right = bars.right || (bars.single ? newBar(screen, reference) : null);
    const middle = bars.single || bars.middle || newBar(screen, reference);
    if (bars.single) {
        middle.currentConfigGroup = ["General"];
        const leftIds = String(middle.readConfig("MonetBarLeftWidgets", "")).split(",");
        const rightIds = String(middle.readConfig("MonetBarRightWidgets", "")).split(",");
        const original = ordered(middle);
        const leftWidgets = original.filter(w => leftIds.includes(String(w.id)) || [menuType, gamesType].includes(w.type));
        const rightWidgets = original.filter(w => !leftWidgets.includes(w)
            && (rightIds.includes(String(w.id)) || ["org.monet.weather", quickType, "org.monet.sound",
                "org.monet.transfers", trayType, "org.monet.clock"].includes(w.type)));
        let copies;
        try {
            copies = copyWidgets(leftWidgets, left).concat(copyWidgets(rightWidgets, right));
        } catch (error) {
            left.remove();
            right.remove();
            throw error;
        }
        leftWidgets.concat(rightWidgets).forEach((w, index) => {
            const shortcut = w.globalShortcut;
            if (shortcut) {
                w.globalShortcut = "";
                copies[index].globalShortcut = shortcut;
            }
            w.remove();
        });
    }
    if (!has(middle, tasksType)) addTaskManager(middle);
    if (left) styleBar(left, "left");
    styleBar(middle, "middle");
    if (right) styleBar(right, "right");
}

function fitIslands(bars, screen) {
    const {left, middle, right} = bars;
    if (!left || !middle || !right || left.length < 2 || right.length < 2) return;
    const width = screenGeometry(screen).width;
    // Plasma reports content length. The floating panel background adds
    // padding, so give each side 16 pixels for it and an 8-pixel gap.
    const padding = 16;
    const gap = 8;
    const taskMinimum = 80;
    if (width < taskMinimum + 2 * (gap + 10)) return;
    const sideBudget = width - taskMinimum - 2 * gap;
    const leftWidth = Math.min(left.length + padding, Math.floor(sideBudget / 2));
    const rightWidth = Math.min(right.length + padding, sideBudget - leftWidth);
    for (const [panel, extent] of [[left, leftWidth], [right, rightWidth]]) {
        if (panel.length + padding <= extent) {
            panel.lengthMode = "fit";
        } else {
            panel.offset = 0;
            panel.minimumLength = 10;
            panel.maximumLength = extent;
            panel.lengthMode = "custom";
        }
    }
    // The Wayland center anchor ignores offsets. Calculate the position
    // from the left edge so the dock can sit between unequal side panels.
    const start = leftWidth + gap;
    const end = width - rightWidth - gap;
    const preferred = Math.min(Math.max(taskMinimum, middle.length + padding), end - start);
    const offset = Math.max(start, Math.min(Math.floor((width - preferred) / 2), end - preferred));
    middle.writeConfig("MonetBarRole", "middle");
    middle.alignment = "left";
    middle.offset = offset;
    middle.minimumLength = taskMinimum;
    middle.maximumLength = end - offset;
    middle.lengthMode = "custom";
}

const screens = barsByScreen();
if (requestedMode) {
    for (const [screen, bars] of Object.entries(screens)) {
        if (requestedMode === "single") toSingle(bars, Number(screen));
        else if (requestedMode === "islands") toIslands(bars, Number(screen));
        else if (requestedMode === "fit") fitIslands(bars, Number(screen));
    }
}
const modes = Object.values(requestedMode ? screens : barsByScreen()).map(bars => {
    if (requestedMode === "single") return "single";
    if (requestedMode === "islands" && (bars.single || (bars.left && bars.right))) return "islands";
    return barMode(bars);
});
print(modes.length && modes.every(mode => mode === modes[0]) ? modes[0] : modes.length ? "incomplete" : "");
