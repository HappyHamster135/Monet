.pragma library
// Monet Titles' arithmetic: which windows get a title bar that appears when you point at the top,
// where the pointer brings one, and where it goes. Plain functions of what KWin says about a
// window (rectangles in logical pixels), so the tests run them as they are.

// The same at every scale: KWin draws the bar at its screen's.
var BAR = 40     // the bar's height, as on Monet's own apps' title bars
var BUTTON_WIDTH = 44
var EDGE_DEPTH = 6   // the pointer stops at the screen edge
var FLOATING_DEPTH = 18  // an easier target when the pointer can pass the top in either direction
var ABOVE = 7   // let the pointer just overshoot a floating window's top
var BARE = 4     // a frame whose top is no taller than this has no title bar of its own
var SLACK = 4    // how far off the bar the pointer may stray before it goes

function rect(x, y, width, height) {
    return { x: x, y: y, width: width, height: height }
}

function overlaps(a, b) {
    return Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x) > 0
        && Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y) > 0
}

// Overlapping, or meeting along an edge.
function touches(a, b) {
    return Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x) > 0
        && Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y) >= 0
}

// Where a window's top can be seen: its own top, or its screen's when it reaches above it.
function visibleTop(client, screen) {
    return Math.max(client.y, screen.y)
}

// The bar: across the window's top, as wide as the window and never taller than it.
function barRect(client, screen) {
    var top = visibleTop(client, screen)
    var x = Math.round(client.x)
    var y = Math.round(top)
    var width = Math.max(1, Math.round(client.x + client.width) - x)
    var height = Math.max(1, Math.min(BAR, Math.round(client.y + client.height) - y))
    return rect(x, y, width, height)
}

// Keep the native title and the panel independently clickable. Round the gap
// outwards so neither surface takes a pixel of the notch on fractional scales.
function barLayout(client, screen, stack) {
    var bar = barRect(client, screen)
    for (var i = 0; i < stack.length; ++i) {
        var dock = stack[i]
        if (!dock || !dock.dock || dock.deleted || dock.hidden || dock.minimized) continue
        var d = dock.frameGeometry
        if (Math.abs(d.y - screen.y) > 1 || d.width >= screen.width / 2
                || Math.abs(d.x + d.width / 2 - screen.x - screen.width / 2) > 2
                || !overlaps(d, bar)) continue
        var leftWidth = Math.max(0, Math.floor(d.x) - bar.x)
        var right = Math.ceil(d.x + d.width)
        var rightWidth = bar.x + bar.width - right
        if (rightWidth >= 3 * BUTTON_WIDTH + BAR) {
            return {main: rect(right, bar.y, rightWidth, bar.height),
                    side: leftWidth > 0 ? rect(bar.x, bar.y, leftWidth, bar.height) : null}
        }
        // A narrow window may have its close button directly under the notch.
        // Drop its controls below the panel rather than squeezing or hiding them.
        var below = Math.ceil(d.y + d.height)
        var available = Math.floor(client.y + client.height) - below
        if (available > 0) {
            bar.y = below
            bar.height = Math.min(bar.height, available)
        }
        break
    }
    return {main: bar, side: null}
}

// The pointer at a window's top: within its reveal band. For a window
// that fills the screen, that's the screen's top edge, where the pointer stops by itself.
function atTop(client, screen, p) {
    var top = visibleTop(client, screen)
    var depth = top === screen.y ? EDGE_DEPTH : FLOATING_DEPTH
    var start = Math.max(screen.y, top - ABOVE)
    return p.x >= client.x && p.x < client.x + client.width
        && p.y >= start && p.y < top + Math.min(depth, (client.y + client.height - top) / 3)
}

// Most pointer movement is inside app content. Reject that cheap geometry case
// before eligibility walks KWin's window stack to check occlusion.
function aimedAt(p, pick, eligible) {
    var w = pick(p)
    if (!w || w.desktopWindow) w = pick({ x: p.x, y: p.y + ABOVE })
    if (!w || w.move || w.resize || !w.output
            || !atTop(w.clientGeometry, w.output.geometry, p)) return null
    return eligible(w) ? w : null
}

// Still on the bar, or only just off it: the bar stays until the pointer is away.
function onBar(bar, p) {
    return p.x >= bar.x - SLACK && p.x < bar.x + bar.width + SLACK
        && p.y >= bar.y - SLACK && p.y < bar.y + bar.height + SLACK
}

// Which windows get a bar: those KWin frames itself with no title bar in the frame. Monet's
// frames are never opaque (Aurorae's never are), so KWin's frame shows as decorationHasAlpha; an
// app that draws its own title bar (GTK, Chromium, Zen, Monet's own apps) has none. Never a window
// that's full screen (a game), minimized or hidden, nor Plasma's and KWin's own (panels, the
// desktop, notifications, popups, the screen-edge outline).
function titleless(w) {
    if (!w || w.deleted || !w.managed || w.minimized || w.hidden || w.fullScreen)
        return false
    if (!(w.normalWindow || w.dialog || w.utility) || w.specialWindow || w.popupWindow || w.outline)
        return false
    if (!w.decorationHasAlpha)
        return false
    var frame = w.frameGeometry, client = w.clientGeometry
    return client.y - frame.y <= BARE && client.width > 0 && client.height > 0
}

// A fading snap surface can cover the screen visually while clicks already reach the app.
function isSnapPreview(w) {
    return w.pid === -1 && !w.resourceClass && w.captionNormal === "Monet snap preview"
}

// Something already where the bar would go, which it mustn't cover: a window above this one (a
// menu, a notification, another app), or a panel along that edge, even while it's hidden away
// (pointing at the edge brings the panel back there instead). ignore: the bar's own window.
function covered(w, bar, stacking, desktop, ignore) {
    var at = stacking.indexOf(w)
    for (var i = 0; i < stacking.length; i++) {
        var o = stacking[i]
        if (!o || o === w || o.deleted || isSnapPreview(o) || (ignore && ignore(o)))
            continue
        if (o.dock) {
            if (o.hidden ? touches(o.frameGeometry, bar) : overlaps(o.frameGeometry, bar))
                return true
            continue
        }
        if (i < at || o.minimized || o.hidden)
            continue
        if (desktop && !o.onAllDesktops && o.desktops && o.desktops.indexOf(desktop) < 0)
            continue
        if (overlaps(o.frameGeometry, bar))
            return true
    }
    return false
}

// Filling the screen both ways (KWin's MaximizeFull): the middle button restores it.
function filling(mode) {
    return mode === 3
}

// A button's picture: the frames' own (tools/make-decoration.py), in the light and state it's in.
function art(folder, smoke, kind, pressed, hovered, active) {
    var state = pressed ? "pressed" : hovered ? "hover" : active ? "active" : "inactive"
    return folder + (smoke ? "MonetSmoke" : "Monet") + "-" + kind + "-" + state + ".svg"
}
