.pragma library

// What Task Manager's tables say about each app, without KDE: which rows KDE couldn't name,
// what an app's windows show, and what the cards count that no app row does (System).
// Plain functions, so the Applications and Processes faces share them and tests can run them.

// A row KDE couldn't name: no menu entry and no icon, so its name is the raw id
// (app3241660 for a Steam game, org.chromium.Chromium when KDE missed Flatpak's entry).
function unresolved(name, menuId, icon) {
    return !!name && !menuId && !icon && name !== "services"
}

// The ids worth asking monet-quick about: app ids, each once.
function toAsk(ids, asked) {
    const wanted = []
    for (const id of ids) {
        const text = String(id || "")
        if (/^[\w.+@-]{1,255}$/.test(text) && !(text in asked) && !wanted.includes(text)) wanted.push(text)
    }
    return wanted.slice(0, 64)
}

// UTF-8, as hex: the helper's arguments are never words a shell reads.
function hex(text) {
    let out = ""
    for (const ch of String(text)) {
        const code = ch.codePointAt(0)
        const bytes = code < 0x80 ? [code]
            : code < 0x800 ? [0xc0 | code >> 6, 0x80 | code & 63]
            : code < 0x10000 ? [0xe0 | code >> 12, 0x80 | code >> 6 & 63, 0x80 | code & 63]
            : [0xf0 | code >> 18, 0x80 | code >> 12 & 63, 0x80 | code >> 6 & 63, 0x80 | code & 63]
        for (const b of bytes) out += (b < 16 ? "0" : "") + b.toString(16)
    }
    return out
}

// KDE's own overrides (Background Services) with Monet's names for rows it couldn't name, and
// the sums of rows that gained processes (account): {id: {attribute: value}}.
function overrides(base, names, numbers) {
    const result = {}
    for (const id in base || {}) result[id] = Object.assign({}, base[id])
    for (const id in names || {}) {
        const found = names[id]
        if (found && found.name && !(id in result)) result[id] = {appName: found.name, iconName: found.icon || ""}
    }
    for (const id in numbers || {}) result[id] = Object.assign({}, result[id] || {}, numbers[id])
    return result
}

// The id KDE files a row under (its overrides' key): its menu entry, else the raw id Monet named.
function rowKey(name, menuId, found) {
    if (menuId) return String(menuId)
    for (const id in found || {}) {
        if (found[id] && found[id].name === name) return id
    }
    return String(name || "")
}

// What KDE adds up over an app's processes for its row, and so Monet can add to.
const ADDABLE = ["usage", "userUsage", "sysUsage", "vmPSS", "memory", "vmURSS", "vmRSS", "swap",
    "ioCharactersReadRate", "ioCharactersWrittenRate", "ioCharactersActuallyReadRate", "ioCharactersActuallyWrittenRate",
    "netInbound", "netOutbound", "monetGraphics"]

function addable(attribute) {
    return ADDABLE.includes(attribute)
}

function sums(processes, attributes) {
    const total = {}
    for (const attribute of attributes) total[attribute] = 0
    for (const p of processes) {
        for (const attribute of attributes) total[attribute] += Number((p.values || {})[attribute]) || 0
    }
    return total
}

// Every process of this account in a row. KDE's rows hold the apps (each app's systemd unit) and
// Background Services; a process of this account in none of them (a terminal's or an SSH login's
// session, a unit of its own: systemd-run, a timer's job) joins the row of the app that started
// it, its parent's or theirs, else Other. rows: [{key, pids}]; processes: [{pid, ppid, uid, name,
// values: {attribute: number}}]. Returns {mine: this account's uid, totals: {key: sums of a row
// that gained processes, its own with them}, gained: {key: how many}, added: {key: [processes]},
// other: [processes]}.
function account(rows, processes, attributes) {
    const byPid = {}, owner = {}
    for (const p of processes || []) byPid[Number(p.pid)] = p
    for (const row of rows || []) {
        for (const pid of row.pids || []) owner[Number(pid)] = row.key
    }
    let mine = null
    for (const pid in owner) {
        if (byPid[pid] && byPid[pid].uid !== undefined && byPid[pid].uid !== null) {
            mine = Number(byPid[pid].uid)
            break
        }
    }
    const added = {}, other = []
    for (const p of processes || []) {
        if (mine === null || Number(p.pid) in owner || Number(p.uid) !== mine) continue
        let key = null
        for (let up = byPid[Number(p.ppid)], steps = 0; up && steps < 64; up = byPid[Number(up.ppid)], ++steps) {
            if (Number(up.pid) in owner) {
                key = owner[Number(up.pid)]
                break
            }
        }
        if (key === null) other.push(p)
        else (added[key] = added[key] || []).push(p)
    }
    const totals = {}, gained = {}
    for (const row of rows || []) {
        if (!added[row.key]) continue
        const own = (row.pids || []).map(pid => byPid[Number(pid)]).filter(p => !!p)
        totals[row.key] = sums(own.concat(added[row.key]), attributes)
        gained[row.key] = added[row.key].length
    }
    return {mine: mine, totals: totals, gained: gained, added: added, other: other}
}

// A program as people call it: java is Java, REPO.exe is REPO.
function programName(name) {
    const bare = String(name || "").split(/[\\/]/).pop().replace(/\.exe$/i, "")
    return bare.charAt(0).toUpperCase() + bare.slice(1)
}

// Other's own name when it's mostly one busy program, as {program, count} ("Java (8)"), else null.
// usage: KDE's CPU for each process, 100 for a whole processor.
function mostlyOne(processes) {
    const by = {}
    let busy = 0
    for (const p of processes || []) {
        const name = programName(p.name), usage = Number((p.values || {}).usage) || 0
        by[name] = by[name] || {program: name, count: 0, usage: 0}
        by[name].count += 1
        by[name].usage += usage
        busy += usage
    }
    const top = Object.values(by).sort((a, b) => b.usage - a.usage || b.count - a.count)[0]
    return top && top.program && busy >= 5 && top.usage * 2 >= busy ? {program: top.program, count: top.count} : null
}

function same(a, b) {
    return String(a || "").toLowerCase().replace(/\.desktop$/, "") === String(b || "").toLowerCase().replace(/\.desktop$/, "")
}

// The windows among a row's processes, the one in front first: the active one, then any not
// minimized, then the one stacked highest.
function windowsOf(pids, windows) {
    const mine = {}
    for (const pid of pids || []) mine[Number(pid)] = true
    return (windows || []).filter(w => Number(w.pid) > 0 && mine[Number(w.pid)]).sort((a, b) =>
        (b.active === true) - (a.active === true) || (a.minimized === true) - (b.minimized === true)
            || (Number(b.order) || 0) - (Number(a.order) || 0))
}

// A window's title without its app's name at the end ("ChatGPT - Chromium" is ChatGPT).
function cleanTitle(title, names) {
    let text = String(title || "").replace(/\s+/g, " ").trim()
    for (const name of names) {
        if (!name) continue
        const escaped = String(name).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
        const found = new RegExp("^(.*?)\\s+[-–—|]\\s+" + escaped + "(\\s+[-–—|]\\s.*)?$", "i").exec(text)
        if (found && found[1].trim()) text = found[1].trim()
    }
    return text
}

// A browser's web app window, by its window id: Chromium's and Chrome's (chrome-<id>-Default,
// crx_<id>; a Flatpak browser's portal names its entry ...flextop.chrome-<id>-Default), Edge's,
// Brave's, and Firefox's and Zen's through Progressive Web Apps for Firefox (FFPWA-<id>).
function webAppId(id) {
    return /(^|\.)(chrome|msedge|brave)-[a-p]{32}-/i.test(id) || /^crx_[a-p]{32}/i.test(id) || /^FFPWA-/i.test(id)
}

// A window of a web app of its row's browser (ChatGPT installed from Chromium), by the web app's
// own name and icon where its menu entry is known (to KDE, or to monet-quick: names), else null.
function webApp(win, row, names) {
    const id = String(win.appId || "").replace(/\.desktop$/, "")
    if (!webAppId(id) || same(id, row.menuId)) return null
    const known = names && names[id]
    const name = win.appName && !same(win.appName, row.name) ? win.appName : (known && known.name) || ""
    if (!name || same(name, row.name)) return null
    return {text: name, icon: name === win.appName ? win.icon : (known && known.icon) || ""}
}

// What the row's second line says about one window: its web app, else its title.
function windowLabel(win, row, names) {
    const app = webApp(win, row, names)
    if (app) return app
    const text = cleanTitle(win.title, [row.name, win.appName])
    return {text: same(text, row.name) ? "" : text, icon: ""}
}

// The second line of an app's row: what its front window shows, and how many more say
// something else ("ChatGPT", and 3 more). Only windows' titles: nothing from inside them.
function windowLine(row, wins, names) {
    const labels = []
    for (const win of wins || []) {
        const label = windowLabel(win, row, names)
        if (label.text && !labels.some(l => l.text === label.text)) labels.push(label)
    }
    return labels.length ? {text: labels[0].text, icon: labels[0].icon, more: labels.length - 1}
        : {text: "", icon: "", more: 0}
}

// A row KDE couldn't name and monet-quick hasn't (yet): the name its own windows go by.
function windowName(row, wins) {
    for (const win of wins || []) {
        if (win.appName && (same(win.appId, row.id) || same(win.appId, row.name))) return {name: win.appName, icon: win.icon}
    }
    return null
}

// System: what the cards count that no app row does (system services, other accounts and the
// kernel, with its interrupts). Each column's card, in the card's units.
const CARDS = {usage: "cpu", vmPSS: "used", memory: "used", vmURSS: "used",
    ioCharactersActuallyReadRate: "read", ioCharactersActuallyWrittenRate: "write",
    netInbound: "download", netOutbound: "upload"}

function card(attribute) {
    return CARDS[attribute] || ""
}

// Bytes (or bytes a second) in a column's unit: KDE's units count 100 for bytes, 101 for KiB...,
// 200 for bytes a second, 201 for KiB a second...
function inUnit(bytes, unit) {
    const prefix = unit % 100
    return (unit >= 100 && unit < 106) || (unit >= 200 && unit < 206) ? bytes / Math.pow(1024, prefix) : NaN
}

// System's share of a column, in the column's own units, or NaN where no card compares.
// total: the card's reading (CPU in percent of every processor, the rest in bytes);
// counted: the apps' rows added up; cpuMax: KDE's most for a row's CPU (100 for each processor).
function systemShare(attribute, unit, total, counted, cpuMax) {
    const which = card(attribute)
    if (!which || typeof total !== "number" || !isFinite(total) || total < 0) return NaN
    const whole = which === "cpu" ? total / 100 * cpuMax : inUnit(total, unit)
    if (!isFinite(whole)) return NaN
    return Math.max(0, whole - (Number(counted) || 0))
}

// A row's CPU as the column shows it: scaled to every processor ("lineScaled", Monet's), or per processor.
function cpuShown(value, cpuMax, style) {
    return /Scaled$/.test(String(style || "")) && cpuMax > 0 ? value / cpuMax * 100 : value
}

// The busiest of some processes, busiest first: [{name, pid, usage}] (KDE's CPU, 100 a processor).
function busiest(processes, count) {
    return (processes || []).map(p => ({name: String(p.name || ""), pid: Number(p.pid) || 0, usage: Number((p.values || {}).usage) || 0}))
        .filter(p => p.pid > 0 && p.usage > 0)
        .sort((a, b) => b.usage - a.usage || a.name.localeCompare(b.name))
        .slice(0, count || 5)
}

// The processes no app's row, and no row of Monet's, has: other accounts' and the kernel's.
function systemProcesses(processes, mine) {
    return (processes || []).filter(p => mine === null || Number(p.uid) !== Number(mine))
}

// Processes page: the app a process belongs to, under its own name, where the app starts:
// every process of it in the list, in the tree where its group begins. Nothing for Background
// Services, or where the process is called what the app is.
function processApp(processName, app, parentApp, flat) {
    if (!app || !app.name || app.id === "services") return ""
    if (!flat && parentApp && parentApp.id === app.id) return ""
    const bare = String(processName || "").replace(/\.exe$/i, "").replace(/[\s_-]+/g, "").toLowerCase()
    return bare === String(app.name).replace(/[\s_-]+/g, "").toLowerCase() ? "" : app.name
}
