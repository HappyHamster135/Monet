.pragma library
// Monet Snap's file and folder dialogs on an ultrawide screen.
//
// KDE's file and folder dialog (KIO's KFileWidget: in KDE's and Qt's apps, and in KDE's portal,
// which shows it for Flatpak apps, Electron apps and others that ask it) opens the first time
// at half the screen's width and half its height, or 48 by 30 lines of text when that's more,
// never more than 90% of the screen (KFileWidget::sizeHint). On a 16:9 screen that's
// comfortable. On a 32:9 one it's a strip 2560 wide and 720 tall, where the names push the sizes
// and dates out of sight. So the first time, such a dialog is given the width KDE would give it
// on a 16:9 screen as tall as this one, centered on the app's window that opened it.
//
// KDE keeps the size a file dialog closes at (KWindowConfig, in the app's own state file, or the
// portal's), and opens it at that size from then on. A size it kept isn't its first one, so it's
// left alone: one you chose stays yours. On 16:9 and 16:10 screens nothing changes at all.
// Plain functions of what KWin says about windows and screens (logical pixels), so the tests
// run them as they are.

var WIDE = 2        // wider than 2:1 is an ultrawide: 21:9 is 2.4:1 and 32:9 3.6:1, 16:9 only 1.8:1
var SLACK = 8       // rounding between the app's idea of the screen and KWin's
var PANELS = 100    // how much of the screen's height an app may leave out for panels
var PORTAL = "org.freedesktop.impl.portal.desktop.kde"   // KDE's portal: its dialogs' own name

function rect(x, y, width, height) {
    return { x: x, y: y, width: width, height: height }
}

function ultrawide(screen) {
    return screen.width > WIDE * screen.height
}

// KDE's first size for a file dialog, made for this screen: half its width, and half its height
// or 30 lines of text (no more than 90% of it). Only on an ultrawide, where that's too wide.
function kdesFirst(client, screen) {
    return ultrawide(screen) && Math.abs(client.width - screen.width / 2) <= SLACK
        && client.height >= screen.height / 2 - PANELS && client.height <= screen.height * 0.9 + SLACK
}

// The windows a file dialog can be: a dialog, a window an app opened over one of its own (which
// is what a dialog is on Wayland), or a window of KDE's portal. Never an app's own window (Monet
// Work puts those back after a restart), nor one held, moved or resized, full screen, filling
// the screen, minimized, or KWin's or Plasma's own.
function eligible(w) {
    if (!w || w.deleted || !w.managed || w.fullScreen || w.minimized || w.hidden || w.move || w.resize)
        return false
    if (w.maximizeMode !== 0 || !w.resizeable || w.specialWindow || w.popupWindow || w.outline)
        return false
    if (!(w.normalWindow || w.dialog))
        return false
    return !!(w.dialog || w.transient || w.transientFor || w.desktopFileName === PORTAL || w.resourceClass === PORTAL)
}

// The width KDE gives a file dialog on a 16:9 screen as tall as this one: half that screen's
// width, or 48 lines of text when that's more (the dialog's 30 lines of height say how tall a
// line is), never more than 90% of it.
function width169(height, screen) {
    var wide = screen.height * 16 / 9
    return Math.round(Math.min(wide * 0.9, Math.max(wide / 2, height * 48 / 30)))
}

// Where a dialog that has just opened goes: as wide as on a 16:9 screen, as tall as it is,
// centered on the window that opened it (or where KWin put it), inside the screen's work area.
// screens: every screen's geometry, as the app may have measured another one than it opens on.
// area: its screen's work area. null: it stays as it is.
function fitted(w, screens, area) {
    if (!eligible(w) || !w.output)
        return null
    var client = w.clientGeometry, frame = w.frameGeometry
    var measured = false
    for (var i = 0; i < screens.length && !measured; i++)
        measured = kdesFirst(client, screens[i])
    if (!measured)
        return null
    var width = Math.max(width169(client.height, w.output.geometry), w.minSize ? w.minSize.width : 0)
    if (width >= client.width - SLACK)
        return null
    var outer = Math.min(Math.round(width + frame.width - client.width), area.width)
    var parent = w.transientFor && !w.transientFor.deleted && !w.transientFor.minimized
        ? w.transientFor.frameGeometry : null
    var middle = parent ? parent.x + parent.width / 2 : frame.x + frame.width / 2
    var x = Math.max(area.x, Math.min(Math.round(middle - outer / 2), area.x + area.width - outer))
    return rect(x, frame.y, outer, frame.height)
}
