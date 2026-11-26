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
