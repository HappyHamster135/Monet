# Notch comparison and refinements

26 November 2026. Monet baseline: `notch` at `cae1fee`. Reference: [Vorssaint](https://vorssaint.com/), with the notch source tree at `0f0fdd91eb80e509f737f2c4c1f8630b707f6537`.

The branch already contains much of the core functionality. The most visible gaps were inconsistent controls, empty pages without an explanation, limited pad actions, and note editors whose document size could escape the island. This pass keeps Monet's existing dark surface, navigation, services, and privacy boundaries.

| Surface | Comparison and changes |
| --- | --- |
| Notes | Vorssaint exposes named pads, editing actions and find inside the island. Monet now has a horizontal pad strip, rename, confirmed delete, copy, undoable clear, Find/next/previous, Ctrl+T, Ctrl+S, and save feedback. Both long paragraphs and unbroken text wrap inside a clipped, vertically scrolling editor. The shared pad service still protects competing edits with revisions. |
| Calendar | Bounded day-note editing and compact event rows. The split agenda now has a date-and-add header and a single compact footer for linked calendars and upcoming events, leaving more space for appointments. |
| Controls | Added shortcuts to enabled Notes, Time, Calendar, Volume mixer, Keep awake, Screenshot and Record screen. Slim level sliders and circular action glyphs follow the reference's control layout. Capture actions work before opening the Tools catalogue. Existing native output, microphone and brightness controls remain; a device-free page explains its state. |
| Downloads | Added opening the watched folder directly. Paths and filenames elide within their allotted space; compact rows distinguish partial downloads from completed files. Reveal-in-Files and add-to-shelf actions remain available, with clear loading, empty and unavailable states. |
| Tools | Replaced the catalogue list with a horizontally scrolling tile launcher, following Vorssaint's QuickLauncher. Compact captions sit below monochrome circular glyphs; full descriptions remain searchable and accessible. Favorites stay first. Category filtering, optional search, customization, keyboard activation and empty results remain available. |
| Notifications | Consistent rows, timestamps, actions, reply field and empty state. KDE remains the owner of history, notification actions and clear confirmation semantics. |
| File shelf, captures, camera and Watch | Shared dark surfaces, compact controls and bounded text. Saved captures now have thumbnail cards and All/Images/Videos filters; copied images have a smaller rail. Camera selection and retry controls use the island styling. Camera startup, file removal and capture permissions retain their existing semantics. |
| Music and mixer | Smaller artwork/title header, a full-width timeline, spaced transport controls, compact queue rows and readable active/inactive lyrics. Track-specific seeking and queue ownership checks remain intact. Mixer output controls use consistent glyphs and type. |
| Time and Keep Awake | Orange Start action, 5/15/25/45/60-minute presets, compact shared numeric controls and a Keep Awake status card with a two-hour option. Existing focus rounds, pause/resume, stopwatch persistence and DST-safe end-time selection remain intact. |
| Activity and Agents | Activity uses horizontal battery chips and a stable compact footer. Agents use source cards, clear connection states and compact quota/reset cards, backed by the existing session, Codex and Claude integrations. |
| System | Clickable CPU, memory, graphics and network cards open live history for up to 96 seconds. Missing readings remain gaps; network charts scale to observed download rates. History resets when the page stops observing. |
| Clipboard | Compact searchable cards for text, images and files, pin/copy actions, a bounded text editor, QR codes and native clipboard actions. Search treats punctuation literally. Klipper still owns history and the original MIME data; lock-state protections remain. |
| Shared layout | Monochrome glyphs independent of application-icon masks, compact empty states and consistent bottom spacing keep content away from rounded corners. Section navigation and gestures retain their existing behavior. |

## Differences that remain

- Vorssaint's full scratchpad formatting toolbar, Markdown preview and export are not embedded in Monet's notch. Monet's **Open floating pad** already provides Markdown preview and text export.
- Vorssaint's configurable layout and disk/power/fan detail remain beyond Monet's four-metric System page. Monet now has live history for its supported metrics.
- Music data depends on what the selected Linux MPRIS player supplies. Mac-specific media integrations cannot be reused directly.
- Monet's agent page currently covers a selected session file plus Codex and Claude Code usage. It does not yet have separate OpenCode and GitHub Copilot integrations.
- Physical Mac camera-cutout placement, lock-screen island behavior and macOS-specific controls have no direct implementation in this Plasma widget.

These are remaining parity differences, not claims of completed functionality.

## Validation

The native Qt tests cover long Unicode notes and unbroken strings, caret visibility while scrolling, narrow viewports, copy/clear/undo, find navigation, save-before-switch, rename/delete revision conflicts, last-pad replacement, and day-note Save/Cancel. Controls and Tools tests exercise pointer activation, category popup selection and keyboard search.

All 65 tests passed with no skips, including the existing navigation, gestures, timer, media playback, tool visibility, notification, download, companion, keep-awake, Utilities and calendar suites. Rendering was checked in a separate KWin/Wayland session at 448×316 and 320×316, plus ten sections in the actual Plasma applet at 464×316. Temporary homes, private D-Bus and test fixtures isolated this from the installed desktop, notes and device settings. Audio/brightness hardware and camera recording still need a physical desktop check.

## Local installation correction

The first local installation incorrectly retained image-built `.qmlc`/`.jsc` files. Plasma selected the local package but still executed its old compiled UI, so checking only source hashes and the package path was insufficient. The installer now removes adjacent bytecode whenever it installs editable QML/JavaScript, records removals for rollback, and offers a scoped installation:

```sh
python3 tools/install-desktop-preview.py --notch --apply
systemctl --user restart plasma-plasmashell.service
```

The correction was checked against the running desktop at its actual scale and icon theme: the Notes tab strip and new Tools grid were present. That revealed a KDE-style ComboBox incompatibility and opaque application-icon masks; both were corrected. Notes and panel interaction tests now use `org.kde.desktop`, including long notes, category selection, later grid columns and keyboard activation. All 35 focused checks passed without skips. Installer regression checks cover bytecode removal, rollback and preservation of shared components. Temporary render probes were removed, all 102 installed source payloads were verified, Plasma was reloaded, and all 23 notch preferences remained unchanged.

## Remaining-tab pass

The remaining tabs were compared with the pinned Music, Queue, Timer, Clipboard, Agents, System and Calendar source. The changes above were installed with the scoped installer and checked in the actual Plasma widget at 464×316 logical pixels (882×600 captured pixels). Twenty-two page states were inspected, including System's detail chart and media details. The final pass corrected bottom-edge crowding and the Calendar agenda's oversized controls.

All **61 distinct tests passed with no skips** across the focused Notes, panels, remaining pages, playback, timer, native preview installer, tabs/navigation/gestures, notifications, companion, Keep Awake, camera and calendar suites. Calendar checks used Monet's installed dependency wheels. The camera test used in-memory video patterns, including selection, hotplug and screen-lock release; no physical camera was started by the desktop probe. New checks cover literal clipboard search, pin/copy/edit, long text, timer presets, narrow media layout, capture filtering and metric history gaps.

The clean installation contains **107 verified files** with no adjacent QML bytecode. Temporary capture probes were removed and Plasma restarted. All **23 notch preferences** matched the pre-install snapshot. Saved render evidence and the consolidated test report are under the account's `monet-notch/remaining-tabs` visualization folder. Physical devices and player-specific queue/lyric support still require the user's own testing.

## Reference source

- [Scratchpad](https://github.com/vorssaint/vorssaint-utils/blob/0f0fdd91eb80e509f737f2c4c1f8630b707f6537/Sources/Vorssaint/UI/Notch/NotchScratchpadView.swift)
- [Controls](https://github.com/vorssaint/vorssaint-utils/blob/0f0fdd91eb80e509f737f2c4c1f8630b707f6537/Sources/Vorssaint/UI/Notch/NotchControlsView.swift)
- [Tools launcher](https://github.com/vorssaint/vorssaint-utils/blob/0f0fdd91eb80e509f737f2c4c1f8630b707f6537/Sources/Vorssaint/UI/QuickLauncher/QuickLauncherView.swift)
- [Calendar](https://github.com/vorssaint/vorssaint-utils/blob/0f0fdd91eb80e509f737f2c4c1f8630b707f6537/Sources/Vorssaint/UI/Notch/NotchCalendarView.swift)
- [Downloads](https://github.com/vorssaint/vorssaint-utils/blob/0f0fdd91eb80e509f737f2c4c1f8630b707f6537/Sources/Vorssaint/UI/Notch/NotchDownloadsView.swift)

- [Music](https://github.com/vorssaint/vorssaint-utils/blob/0f0fdd91eb80e509f737f2c4c1f8630b707f6537/Sources/Vorssaint/UI/Notch/NotchMusicView.swift)
- [Clipboard](https://github.com/vorssaint/vorssaint-utils/blob/0f0fdd91eb80e509f737f2c4c1f8630b707f6537/Sources/Vorssaint/UI/Notch/NotchClipboardView.swift)
- [System](https://github.com/vorssaint/vorssaint-utils/blob/0f0fdd91eb80e509f737f2c4c1f8630b707f6537/Sources/Vorssaint/UI/Notch/NotchSystemView.swift)
- [Agents](https://github.com/vorssaint/vorssaint-utils/blob/0f0fdd91eb80e509f737f2c4c1f8630b707f6537/Sources/Vorssaint/UI/Notch/NotchAgentsView.swift)
- [Timer](https://github.com/vorssaint/vorssaint-utils/blob/0f0fdd91eb80e509f737f2c4c1f8630b707f6537/Sources/Vorssaint/UI/Notch/NotchTimerView.swift)

## Hover labels and timer overflow follow-up

Hover tooltips are disabled in the notch's own controls, launchers, sliders, captions and Calendar previews, including native tool pages and Command Bar result hints. Visible labels and accessibility names remain. Standalone Utilities and Calendar widgets retain their tooltips.

The Timer/Focus action strip now wraps according to its content instead of switching to two columns at 400 pixels. Compact spacing keeps the wrapped controls inside the viewport. Clock font sizing uses the viewport width, so a scrollbar cannot repeatedly change the font and content height. Native KDE regression coverage checks Timer, Focus and Stopwatch at 288, 310, 399, 400, 414, 432 and 520 pixels, including both horizontal and vertical control bounds.

## Tools pagination and default selection

Tools opens on the existing Favorites selection; All tools and category filters remain available without removing or changing installed tools. The horizontal scrollbar is replaced by clickable page dots with an elongated active marker. Wheel, drag and keyboard navigation settle on whole pages; an incomplete last page is padded so it contains only new items, without repeating tools from the preceding page. Single-page categories keep a stable layout and hide the unnecessary dots. Empty Favorites offers a direct Browse all tools action. Hover labels remain disabled.

Native checks cover dot activation, disjoint page contents, wheel navigation, keyboard End, a partial last page, filter reset and preserved favorites/visibility preferences.

## Popup containment

The live Plasma dialog exposed an offset missed by page-only screenshots: Qt's popup overlay remained at half a window above and left of the notch after Plasma sized its content before the window. `IslandPopupOverlay` anchors that layer to the window content, including after resizing and reopening. Open popup geometry is now checked in an actual `PlasmaCore.Dialog`, not just an ordinary Qt Quick view.

Category and camera dropdowns stay within their page and show whole rows. Notes, playback-source and clipboard menus share a bounded, scrollable `IslandMenu`; keyboard selection scrolls the selected action into view. Menus close when their page leaves, and Escape dismisses them before notch navigation. Search also reserves space on both sides of the surface. The live Desktop category, Notes actions and Search popups were checked open with their backgrounds and contents inside the notch.

## Tools scrolling and default favorites

Tools now has a 372-pixel surface with four columns and three rows at the standard width. Its twelve default favorites cover Screenshot, Record screen, Text scanner, Color picker, Plain text, Clean link, Emoji, Snippets, Compress, Microphone, Audio output and Cleaning mode. These complement the existing page buttons rather than repeating Notes, Calendars, Clipboard, Files or Music. Existing saved choices, including an empty Favorites list, take precedence. The QML and Utilities defaults agree.

Trackpad updates and momentum move the grid directly; it snaps to a page when the gesture ends. Mouse-wheel bursts retarget a smoothed animation, including reversals, while dots and keyboard navigation stay synchronized. Adjacent tiles are cached and reused, and hidden fallback icons no longer load. Category menus no longer animate their highlighted row or snap during scrolling. Native input tests cover continuous horizontal gestures, momentum, rapid wheel reversals, filter reset and page boundaries.

## Stable agent usage

Codex, Claude Code and Local session each own a fixed card. Account readings are shared by the overview and detail pages, cached under the opted-in connection's generation, and restored on Plasma startup. Opening a page retains the previous successful reading while refreshing in the background; a transient failure keeps that reading with a stale notice. Disconnecting, hiding agents, or switching connections invalidates the cache. Quota cards update their values without recreating or reordering their items, and long labels stay inside the available width.

Tests exercise cached startup, refresh failures, reopening, a delayed response from an old connection, preserved card positions and object identity, and long quota labels. Live checks also compare provider positions before loading and after reopening.

## Music, compact audio and agent cards

The music page follows Vorssaint's current [player layout](https://github.com/vorssaint/vorssaint-utils/blob/main/Sources/Vorssaint/UI/Notch/NotchMusicView.swift): a smaller rounded cover, title and artist, small lyrics/queue switches beside the cover, a full-width timeline, and five evenly spaced transport/output positions. Play/pause uses a larger filled glyph on the surface. Unsupported skip/shuffle controls keep their space so playback stays centered. Repeat and source selection remain available; all commands continue to use native MPRIS.

The compact face uses nine rounded, centered bars and a rounded cover. Enabled live levels still follow only the selected player's audio streams; otherwise the wave is a playback indicator. Pause rests on dots, reduced motion holds a still pose, and hidden faces stop animating. The expanded player has a quieter four-bar version beside its title. This follows the reference [equalizer](https://github.com/vorssaint/vorssaint-utils/blob/main/Sources/Vorssaint/UI/Notch/NotchEqualizerBars.swift) without claiming frequency-band measurements from Plasma's peak monitor.

The agent overview now uses two adjacent rounded [quota cards](https://github.com/vorssaint/vorssaint-utils/blob/main/Sources/Vorssaint/UI/Notch/NotchAgentsView.swift), Codex in blue and Claude in terracotta, with remaining percentages, capsule meters, reset times and update status. Local session activity remains a fixed full-width row. Absent limits show a connection state; no usage values are invented. Cached readings and generation checks remain unchanged. Native tests cover text bounds at 288/414 pixels, stable positions during refresh, media detail links, wave pause/reduced-motion behavior, and actual selected-player audio on an isolated PipeWire server.

## Spending and usage dashboard

AI agents now offers Today, 7 days and 30 days, with estimated API value in USD, input/output totals, request/session counts, quota meters, a selectable cost/token history chart, cache savings and hit rate, active days, reasoning tokens, provider/model breakdowns and recent local activity. The 512-pixel surface stays inside the screen and scrolls to the remaining cards. Provider slots retain their order, saved readings render immediately, and refreshes keep the current values visible.

`agent_history.py` reads the standard local Codex sessions/archive and Claude projects folders (including their configured home overrides). An incremental private SQLite index stores numeric metrics and model names, not prompts or responses. It handles repeated cumulative snapshots, fork inheritance, streamed Claude messages, archive duplicates, partial writes, replacement/truncation and deleted files. Reasoning remains a subset of output tokens. The scanner runs outside Plasma, only refreshes while the AI page is visible, and preserves the prior snapshot after failures.

Like Vorssaint's API-value card, **Spend is an estimate, not a subscription bill**. It prices observed tokens at current standard published rates, accounts for cache reads/writes and the documented GPT-6.2 Astra long-context tariff, and shows missing pricing explicitly instead of treating unknown models as free. Historical totals use the bundled rate snapshot rather than historical invoices. Subscription fees, negotiated rates, speed-tier premiums, credits and tool charges are excluded. Rates were checked on 2026-11-26 against [OpenAI pricing](https://developers.openai.com/api/docs/pricing), the [GPT-6.2 Astra model page](https://developers.openai.com/api/docs/models/gpt-6.2-astra), and [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing).

Focused checks cover accounting and incremental reads, privacy of the cached fields, period boundaries, long-context pricing, narrow card bounds, scrolling to the last section, period switches, saved startup/failure recovery, fixed provider positions and preview installation. The dashboard does not start a CLI conversation or connect an account to read local logs.
