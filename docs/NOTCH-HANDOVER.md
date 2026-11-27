# Monet notch handover · 0.9.8-9

26 November 2026

The `notch` branch contains the full local development history through `9e5ae652`, including the 147 commits following `21cb87dd` on `monet-0.9.8-9`. The handover commit adds these notes and two screenshots from the installed widget test. To pick up the work in an existing clone, run:

```sh
git fetch origin notch
git switch notch
```

## Navigation and motion

Open **Customize Home Bar** from the taskbar context menu to configure the top-center notch. From a main tab such as Music or Controls, the nine-dot button opens Sections. In Sections it becomes a Back arrow that returns to the tab you left. Back from Music’s mixer returns to Music.

Sections shows three rows per page. Scroll vertically to snap one page at a time or select one of the two dots on the right. Reopening Sections after using a tab on page two returns you to page two. A slide can reverse mid-animation. With reduced motion enabled, the destination appears immediately. [Controls screenshot](notch-handover/controls-grid.png) · [Sections screenshot](notch-handover/sections-arrow.png)

Start with [navigation history](../linux/share/plasma/plasmoids/org.monet.notch/contents/ui/NotchNavigation.qml), [the Sections pager](../linux/share/plasma/plasmoids/org.monet.notch/contents/ui/IslandSections.qml), [the page deck](../linux/share/plasma/plasmoids/org.monet.notch/contents/ui/IslandPages.qml), [the slide animation](../linux/share/plasma/plasmoids/org.monet.notch/contents/ui/IslandSlide.qml), or [the grid and Back control](../linux/share/plasma/plasmoids/org.monet.notch/contents/ui/IslandNavigationButton.qml).

## Verification on the test ThinkPad

The navigation, tab and gesture suites recorded 13 passing checks with zero skips. Six tab and navigation checks passed again after the final edits. The installed widget was exercised in an isolated Plasma session, including rapid reversals and returning to the previous tab. Reduced motion was checked separately. To rerun the focused checks from the repository root:

```sh
python3 tools/test.py tests.test_notch_tabs tests.test_notch_navigation tests.test_notch_gestures
```

The local live update verified all 15 payload files. Deployment `9e414247` is active through live replacement and staged for the next ordinary restart. Stable 0.9.8-8 deployment `3166a6e8` is pinned for recovery. Ask the owner before restarting and preserve the current firmware and notch preferences.

## Remaining work

- Try Music → Sections → page two → System on the physical trackpad. Reopen Sections, reverse a scroll mid-slide, and press Back. Check for flashes, a skipped page, or disagreement between the active dot and the visible page.
- The under-ten-second power-on goal remains open. On the next approved physical boot, measure the time to a visible login screen separately from login-manager activation. Record when the Bluetooth mouse is first moved to distinguish its wake time from reconnection. [Earlier boot measurements](benchmarks/0.9.8-9-login-recheck.json)
- This branch is a development handover. Public distribution through Settings still requires portable image qualification and an upgrade test. [Test guide](TESTING.md) · [Publication workflow](../.github/workflows/publish-qualified.yml)


## Editor reliability update — 27 November 2026

The editor and notch previews are installed for the local account. All panels
now share one editor host, so Edit notch selects the Notch page in the existing
window. Returning to a taskbar changes the editor context without closing or
recreating its window. Ending edit mode also closes the panel and widget editor
windows; the close path dismisses immediately while geometry capture finishes.
Editors reuse the Settings/Store frame with permanent title controls rather than
native decorations that trigger Monet's hover title dropdown.

The installed layout helper had still been reading the image's older
`panel-notch.js`, which omitted layout and openActivity from its replies. The
current preview binds the helper to the matching private script. Navigation
controls retain the saved state, serialize writes, and refresh when returning to
the notch. The custom dropdown uses the Qt template instead of inheriting the
KDE desktop style's TextField-only cursor behavior.

`NotchEditHighlight.qml` suppresses the native rectangular hover fill on a
standalone notch, preserving its click target. The selection glow uses the same
shoulder and chin paths as the compact notch and follows its dimensions.

Validation: 74 focused checks passed across editor windows, panel editor,
panel layout, preview installation, widget gallery and music/outline tests.
Two additional interaction checks passed with the actual KDE desktop control
style. Live KWin checks verified one window identity across taskbar/notch
navigation, unchanged geometry during navigation, and complete closure on two
successive uses. Gestures, visible-activity opening and the reopen page were
changed, read back, then restored to the owner's values. The live outline and
window controls were inspected after installation; the final fresh editor
produced no editor QML errors in the shell journal.

Reproduce the focused suite with:

```sh
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python3 -m unittest tests.test_editor_windows tests.test_panel_editor tests.test_panel_layout tests.test_native_preview tests.test_widget_gallery tests.test_notch_music_preview -q
```

The desktop shell was reloaded; no reboot is needed. Account-local installation
receipts and backups are in `~/.local/state/monet/desktop-preview/`, including
`20261127T141343.057854Z`, `20261127T141354.082092Z`,
`20261127T141510.985519Z`, `20261127T141806.947770Z` and
`20261127T141807.020771Z`.


### Optional hidden notch

Desktop layout → Notch → Behavior now includes **Hidden until hover**. The
`autoHide` setting defaults off and is shared with the separate notch settings.
When enabled, the notch's full, fixed panel area reveals its compact face
immediately on pointer entry. The sensor lives outside Plasma's inset/clipped
applet content, and does not shrink while hidden or depend on hover controls.
It fades after a 600 ms pointer-leave delay, stays visible while
open, keyboard-focused, accepting a file drag, or in edit mode, and preserves
panel geometry. Existing click-to-open and hover-preview choices still apply.
The compact waveform and companion stop animating while hidden.

Five focused settings/pointer tests and seven existing music/hover tests passed.
Live screenshots verified hiding and restoring the installed notch; the user's
original preferences were restored. Editor and notch previews were installed
locally on 27 November 2026 and the shell reloaded.

The follow-up hover fix removes the tiny moving reveal target and the quick
buttons' `glance` binding loop. Twelve pointer/music/preview tests passed,
including entry from the middle, sides and outside the clipped applet, quick
button clicks, focus preservation and repeated reveal/hide. Live Wayland pointer
checks revealed the installed notch from the center, both sides, top edge and
lower panel margin without clicking; screenshots confirmed the hover preview
and subsequent hiding. The user's enabled auto-hide preference was preserved.
Installed receipt: `20261127T143934.625694Z`; the shell was reloaded.
