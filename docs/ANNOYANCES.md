# What could annoy people about Monet

Written 2026-10-26, after testing 0.9.3 and the 0.9.4 batch in the test VM
(`tools/vm.py`) and reading the code. It's sorted by how many people would run
into each item and how much it would bother them. **Seen** means seen in the VM or
in the code. **Check** means likely, but not confirmed yet.

## Review on 2026-10-27: what still needs work

The older "done" labels below describe implementation, not release sign-off. This review
found two regressions in the owner's screenshot: Store opened Bazaar, and Settings had a
pale frame. The source now repairs Store shortcuts independently of the look/version stamp,
refreshes KDE's launch cache, and removes the extra frame padding and snap insets. Linux
and JavaScript regression checks cover those changes: 380 Linux checks passed, 13 were
skipped for unavailable dependencies, and the two JavaScript checks passed separately on
Windows. After the host PC restarted, the VM reached its desktop. The fixes were then applied
to its existing test installation and checked live: the dock and old Bazaar desktop entry
open Monet's Store, Settings has no pale rim in Mist or Smoke, and the sign-in and app-name
refresh jobs preserve the new shortcuts. The VM had mixed newer user-installed apps with old
system sign-in scripts; its test overrides now consistently use the newer helpers.

A fast shared-edge drag also exposed delayed Wayland resize acknowledgements: a neighbour
could stop following and leave a gap. The snap script now tracks its requested geometry while
waiting for the client, with a regression test for delayed acknowledgements. The six shortcut
and geometry regression tests pass across Linux and Windows (three on each); the targeted
snap/frame suite passes 13 tests, with four dependency skips. Live checks cover normal and
snapped windows, Snap Assist, and shared-edge resizing at 100% scale. A fresh sign-out/sign-in,
fractional scaling, every glass variant and real hardware remain release checks.

The follow-up frame change gives Settings, Store and Games one shared title and body
surface. Their titles follow the selected glass opacity; their outer paint, blur and
pointer outline have matching rounded corners. The top edge now resizes, the title drags,
and double-click/maximize/restore use the compositor. Live VM checks cover Mist and Smoke,
all four glass levels in Mist, top resizing, moving, minimizing and maximize/restore,
Windows+Z, Snap Assist, and resizing the shared edge between Settings and Store.
The frame, snap and shortcut suites pass 40 checks in the VM plus three JavaScript checks
on Windows. Fractional scaling, keyboard/screen-reader review and real hardware remain
release checks; third-party apps still use their own or the system's window decorations.

The upgrade follow-up now keeps an ownership record for Monet's configuration values and
generated launchers. Automatic upgrades no longer reapply the global theme or rearrange
existing panels. Empty/disabled shortcuts, custom launcher commands and icons, removed
launchers, menu/tray choices, GTK edits and Terminal colors are preserved. The live VM's
existing preferences, launcher fields and panel configuration stayed unchanged across two
migration runs. Failed writes remain retryable; the private journal can undo unchanged
migration output without overwriting a later edit. A real image upgrade, reboot and system
rollback still need release validation; this is profile recovery, not a complete recovery UI.

Priorities toward an OS people can depend on every day:

1. **Upgrades must preserve a working desktop.** Test an existing user profile with old pins,
   caches and custom settings, not only a clean installation. Make Store, Settings, sign-in
   and a reboot smoke test release requirements. Today's Store regression is a concrete
   example of an app being present while the user's entry points still open the old app.
2. **Make Store operations recoverable.** Delivered in the next Store slice: a saved Downloads
   list with cancel/retry/dismiss, workers that continue after Store closes, interrupted-worker
   recovery, and clear network, permission, disk-space and startup errors. An unavailable
   catalog has its own retry and leaves Downloads accessible. The live VM test cancelled a
   real Firefox download, closed/reopened Store during a retry, killed its worker, denied that
   worker's connection, then retried successfully and removed the test app. Unit tests inject
   a full-disk write failure and check atomic recovery. Actual power loss/disk exhaustion,
   other account permissions and broader accessibility remain release checks. Cancellation
   can take time while Flatpak cleans up; first catalog refresh can still take 180 seconds.
3. **Restore work after a Windows trip.** The first adapter now restores saved Kate/KWrite
   documents in a single window and places newly opened windows. Checkpoints are private,
   atomic and retain failed launches for retry. Files now restores local-folder tabs and split
   views in one window, with a verified result and retryable pending launches. Zen now reopens
   its original profile and verifies its native saved normal tabs when browser restoration is
   enabled; its startup preference stays unchanged and private windows stay closed. Other
   browsers, multiple profiles, unsaved work and a real Windows return remain open; see
   [RESTORATION.md](RESTORATION.md).
   A persistent return summary now distinguishes verified tabs, ordinary app startup and
   unavailable work. It offers pending/per-app retry, normal app opening, Backups and dismissal;
   a notification links directly to it. The controlled VM flow and 100/200% keyboard layout
   are checked, with 90 focused tests passing. Reopening individual missing documents after a
   drive reconnects and the real Windows/hardware round trip still need work.
4. **Prove hardware reliability.** The real-hardware checklist is still unsigned: sleep/wake,
   hybrid graphics, multiple monitors, fractional scaling, Bluetooth audio and controllers,
   docks, battery drain and Secure Boot. Publish tested configurations and known limits;
   VM success alone cannot establish these.
5. **Make recovery usable under failure.** Exercise rollback after a broken update, restoring
   actual files from a backup, and recovery when the desktop never starts. Give a clear route
   to the previous working system and diagnostics from the recovery screen. The boot blockage
   seen in this VM is evidence to investigate, not yet a diagnosed product defect.
6. **Finish keyboard and accessibility validation.** Audit every custom Settings/Store/Games
   control with keyboard-only navigation, a screen reader, large text, reduced motion, and
   right-to-left languages. Accessible labels in source do not establish a usable flow.
7. **Reduce Settings friction.** There are many sidebar pages plus "More settings" with a
   different presentation. Test finding everyday actions without knowing KDE terminology;
   add direct search results for individual controls and preserve context when opening the
   advanced settings window. This is a usability hypothesis to validate with new users.
   The everyday-search slice now shares 14 navigation destinations between Settings and
   the app menu. Phrases such as "make text bigger", "headphones", "birthday" and "Windows
   files" open the relevant control or calendar. Search failures stay visible and retryable;
   keyboard focus moves between Monet suggestions and the native results without getting
   trapped or scrolled out of view. The destinations and narrow rows were checked at
   100/200% in the VM. New-user discovery and screen-reader validation still remain.
   The appearance repair now keeps its completion message visible for the Settings session,
   offers **Put back again**, and shows **Try again** when the helper reports failure. Its old
   four-second confirmation made the action look as if nothing had happened. This was checked
   in the live VM, with QML tests for persistent feedback, failure and duplicate clicks.
8. **Be explicit about app compatibility and permissions.** The Store already suggests
   alternatives and shows Flatpak access. Build on that with clear native/Windows requirements,
   an understandable permission review, and a tested migration checklist for real documents,
   cloud files and browser data. Opening an app is only the start of a successful migration.

## The next step, in short

1. **Done (in the 0.9.4 batch, tested in the VM, not yet on hardware):** the
   system's own drives hidden in Files (1), updates no longer undo people's
   choices (2), Windows+Space for keyboard layouts (4), metric-compatible fonts
   (14). Snapped windows now share their edges, and Settings gets its size from
   a snap and resizes from its glass edge (part of 6). Snap Assist and
   Windows+Z take keys (3).
2. **Then the biggest gap:** the Windows side of people's *files and apps*, not
   only their games. Done in the 0.9.4 batch, not yet on hardware:
   - Windows' apps (Office, Adobe) are in the app menu and open in Windows (9).
   - OneDrive (10) is in Files.
   - A BitLocker drive (7) opens with its recovery key.
   - Bookmarks from Edge or Chrome (8) come over.
   - The Store is Monet's own (9, 15), and its search finds the apps in Windows too.
   - GTK 4 apps wear Monet's colors (15).

   This is where people coming from Windows would have felt stuck first.
3. ~~**Settings as its own app**, as Games became (6).~~ Done.
4. **What's left** is all one of these:
   - **Hardware:** the list at the end, and Proton games on NTFS (12).
   - **Out of Monet's reach:** browser history (8), the glass edge on GTK 4
     apps (15), the Calculator's menu bar (15).
   Every item above it is done in the 0.9.4 batch: tested in the VM, not yet on
   hardware.

## For everyone

### 1. Files shows the system's insides
**Seen.** Under Devices, Files lists an unnamed drive with a full red bar. It's
the read-only system layer (composefs, 45 MB, always 100% full). Files also lists
"monet", the whole system disk. "/" shows `bin`, `ostree`, `sysroot` and the
rest. Someone from Windows reads the red bar as "my disk is full". 0.9.4 already
hides "boot" (`90-monet-system.rules`).
**Fix:** hide both, the system disk the way "boot" is hidden, and the system layer
from Files' places, so Devices shows only Windows' drive and sticks. *Small.*
**Done:** `90-monet-system.rules` leaves out Setup's `monet` disk (btrfs or its
encrypted container), and `monet-quick files-place` hides the system root at
sign-in. The VM showed the nameless drive gone. The rule itself needs an
install to try.

### 2. Every Monet update puts Monet's choices back
**Seen.** `monet-session` runs `monet-look --keep` once per Monet version. It
applies the look-and-feel again and writes about 30 settings unconditionally
(`kw`, not `kw_default`): the accent color, icons, cursor, the window frame and
its buttons, KWin's effects and screen edges. Anyone who changed one of these
gets Monet's choice back after every update. People coming from Linux will
notice first, but so will anyone who used "More settings".
**Fix:** keep a note of what Monet wrote last time, and write a key again only if
it still holds that value. *Small to medium.*
**Done:** `monet-look` keeps that note (`~/.config/monet/look-written`) and
reads only the person's own files. The global theme's pointer is kept around
its re-apply. The first update after this one still writes everything once,
since older accounts have no note.

### 3. Snap Assist and the layouts take no keys (done)
**Seen.** KWin never gives a script's window the keyboard, so Esc doesn't close
Snap Assist, and arrows and Enter don't pick. People from Windows press Esc.
(Today it does close on a click on its empty glass, as in Windows.)
**Fix:** show Snap Assist from a tiny helper app that Monet Snap starts (an
ordinary window gets the keyboard), or from a KWin effect while it's up.
*Medium.*
**Done, more simply:** while Snap Assist or Windows+Z is up, Monet Snap makes
KWin shortcuts for the arrows, Tab, Enter, Space and Esc, and removes them once
it's gone, so the keys go back to apps. Tested in the VM:
- Windows+Left, then Right and Enter, picks the Calculator.
- Windows+Z, the arrows and Enter place the window.
- Esc closes both, also right after Windows+Z hands over to Snap Assist (a bug
  found while testing, fixed).
- Esc reaches the Calculator again afterwards.
Windows' number keys in Windows+Z work too (a layout's number, then a part's),
tested in the VM: 4 then 3 put the Store in the lower right quarter. The
shortcuts show in KDE's own shortcut list, under KWin.

### 4. Windows+Space doesn't switch the keyboard layout
**Check.** Monet sets Windows' keys (Windows+E, Windows+Shift+S, Ctrl+Shift+Esc,
Windows+I, Windows+R, Windows+A, Windows+G), but not Windows+Space. KDE's own key
for this is Meta+Alt+K. Monet ships 29 languages, and bilingual people switch
layouts all day.
**Fix:** add it to `monet-look --keys`. *Tiny.*
**Done:** added beside KDE's own key, once for every account (`keys-094`), with Windows+Tab for the overview of the windows (Task View).
Settings → Mouse & Keyboard lists it, and Windows+Z too.

### 5. The firewall says no without asking (done)
**Seen.** Monet's zone opens Steam's Remote Play and LAN transfers, Phone (KDE
Connect), mDNS and DHCPv6, and nothing else. Hosting a Minecraft or other LAN
game, LocalSend, Syncthing or a game server is blocked silently. Windows asks
"Allow access?" the first time a program listens.
**Fix:** a list on the Security page ("These apps can accept connections"), at
least for games. Later, a question like Windows'. *Medium.*
**Done:** Settings → Security → Apps that can accept connections, while Monet's
zone is on:
- **What's on it:** games you host (Minecraft, Terraria, Valheim, Factorio,
  Stardew Valley), LocalSend, Syncthing, streaming this PC with Sunshine, and
  Deskflow.
- **How:** each switch asks for an administrator once. It lets that app's own
  ports in, through a firewalld policy of Monet's, so Monet's zone stays
  updatable.

firewalld's own reader parses the policy (VM, firewalld 2.4.4).
**And Windows' question:** when a program of yours starts accepting connections
that Monet's zone keeps out, a notification asks once: "python3 wants to accept
connections", Allow or Keep blocked.
- **Allow** lets that port in, asking for an administrator.
- **Either answer** is remembered, and Security lists the program with a switch.

Tested in the VM with a small web server: the question, Keep blocked, and the
row in Settings. Allow needs the administrator's password, so it's for you to
try. TCP only.

### 6. Settings isn't a window like the others (done)
**Seen.** Settings is a dialog of the bar. It has its own grips instead of the
frame's (today they reach over its glass edge and follow the pointer), its own
double-click to fill the screen, and it closes when the bar restarts. Monet Snap
doesn't place it, and the frame's room to resize doesn't apply. "Apps, not popups."
**Fix:** its own app window, as Games did. *Medium to large.*
**Partly done:** Settings now resizes from every side and corner through KWin,
as a window does, down to the screen's bottom. Snapped, it shares its edges
with the window beside it (it went under it before), takes the snap's size,
and opens at its own size again. Its own app window is still the real fix.
**Done:** Settings is an app of its own, `monet-settings`, built as Games is:
- **A real window:** Monet's frame (title bar, resizing, filling the screen,
  snapping), its own entry in the taskbar, its own size kept, and the keyboard,
  so its search takes typing.
- **Survives the bar:** restarting the bar no longer closes it.
- **One window:** opening it again brings that window to the page asked for.
Tested in the VM: menu, Quick Settings, a second open handing over its page,
Esc, the bar restarting, search.
**Found while testing:** opened again from the bar, Settings only flashed in
the taskbar (the bar has no activation token to give), so Monet Snap now lets
Monet's own apps forward.
**Costs:** about 1.3 seconds to open in the VM, where the sheet was there at
once. And the old Settings' own close button and grips are gone, since the
frame has them.

## People coming from Windows, macOS and other Linux desktops

Familiar-name search now reaches installed Monet tools from Settings and the menu:
Finder/File Explorer/Nautilus → Files, Task Manager/Activity Monitor → System Monitor,
and familiar editor, screenshot, archive and PDF names reach their local tools. It respects
hidden and removed launchers. Store also suggests available alternatives for Apple's office,
video and music apps and nearby sharing, while explaining that features and formats differ.
LocalSend needs to be installed on both devices; this is not AirDrop interoperability.

The 2026-10-28 VM checks cover these discovery paths at 100/200%, not complete migration.
The next acceptance work in [PLAN.md](../PLAN.md) follows actual browser imports, document
interchange, default apps, drives/phones and recovery from each source OS.

### 7. An encrypted Windows drive is invisible (done)
**Seen.** `monet-windows-drive` skips BitLocker, and Settings says so ("Monet
can't keep games there for both"), but offers no way out. Device encryption is
on by default on many Windows 11 laptops. Those people get no shared Games
folder, no Windows files and no Wi-Fi networks from Windows.
**Fix:** unlock the drive once with the recovery key (cryptsetup reads BitLocker)
and keep the key sealed by the TPM, as Monet's own unlock is. *Medium.*
**Done:** Settings → Games & Controllers asks for the recovery key once.
- **Where to find it:** Settings says where, with "Find my key".
- **Unlocking:** the key reaches root sealed and on stdin. It's tested against
  each BitLocker drive, and the one it fits opens with cryptsetup.
- **Kept:** sealed with systemd-creds (TPM), the drive opens at every start,
  before Windows' setup, which can then put Monet Bridge in. Monet's notice for
  a BitLocker Windows now points to Settings instead of the Windows-side
  installer.

**Tested:**
- The key check, finding the drives, and that the key never reaches a command
  line, with made-up drives.
- Settings' card in the VM: a wrong key says so.
- The VM's cryptsetup (2.8.8) takes BitLocker recovery passphrases, and it has
  a TPM.

**Not tried:** a real BitLocker drive (none in the VM, and unlocking needs
root).
**And Windows hands its key over** when it gets encrypted after Monet is
installed (device encryption with a Microsoft account, or BitLocker turned on):
- Monet leaves Bridge a lock in an administrators-only folder.
- Bridge locks the recovery key with it at the next Windows sign-in and leaves it
  on the EFI partition.
- Monet opens the drive by itself at its next start, and Settings says so.

**Tested:** the lock across both systems (Windows PowerShell 5.1 on this PC
locked a made-up key, and Monet's code in the VM opened it), and the script
stopping quietly without administrator rights.
**Not tried:** a real encrypted drive. Also needs checking on Windows 11 Home,
whose device encryption should answer the same way.
**Still typed once:** a Monet installed beside a Windows that was already
encrypted, before Bridge is in it.

### 8. Bookmarks and passwords stay in Windows (done, but not history)
**Seen.** Nothing brings Edge, Chrome or Firefox bookmarks and history from
Windows' drive into Zen. Passwords are sealed by Windows (DPAPI), so Monet can't
read them.
**Fix:** import bookmarks and history at the first sign-in when Windows' drive is
open. For passwords, a short guide to the browser's export or sync. *Medium.*
**Done:**
- **Bookmarks:** read from the person's own Windows account (Edge, Chrome,
  Brave, Vivaldi, Opera, Firefox) whenever the drive is open. A Zen that hasn't
  started yet takes them in on its first start, through Firefox's own import of
  a new profile's `bookmarks.html`. A Zen already in use gets Add to Zen in
  Settings → Default Apps → From Windows (the file in Downloads, Zen's bookmarks
  window open).
- **Passwords:** the same card says how: export them from Edge or Chrome into
  Shared with Monet, then use Zen's Import from a File.

Tested in the VM: Zen's first start in a fresh profile took a made-up set in
(toolbar, folder, the rest), and Add to Zen worked. Parsing Edge's and
Firefox's files is tested with made-up ones.

**Not done:**
- **History:** a bookmarks file can't carry it, and writing Zen's database by
  hand risks breaking it.
- **Passwords by themselves:** Windows seals them.
- **Not tried on a real Windows drive yet.**

### 9. Apps that aren't games (done)
**Seen.** "Play on Windows" is for games. A `.exe` runs here through Proton
(`monet-windows-program`), which is fine for small programs but not for Office,
Adobe, iCloud, or mouse and RGB software (G Hub, Synapse, iCUE). "Play on Windows
for apps" was considered but not built.
**Fix:** "Open in Windows" for any Windows app, the same trip as games. When
someone searches the store for one ("Photoshop"), show what works here and "on
Windows". *Large.*
**Done:** the apps in the person's Start menu in Windows are in Monet's app menu
and its search, each with its own icon on Monet's canvas and "Opens in Windows".
- **Choosing one:** Monet's sheet asks, then the PC restarts in Windows, where
  Monet Bridge opens that app's own shortcut as the person, and Windows stays.
- **Left out:** Windows' own tools, games and their launchers, browsers, OneDrive,
  uninstallers and help, and anything Monet has itself (Discord, Spotify).

Tested against this PC's real Start menu (shortcuts read and icons taken from
the programs) and in the VM with a stand-in list. **Not done:** an older
Office's advertised shortcuts.

**The Store is Monet's own now** (`monet-store`), since Bazaar couldn't take
results from outside:
- **The catalog:** Flathub's, which Flatpak keeps on the PC, read in the
  person's language in under a second. Monet's picks make the front page under
  strips of The Hours; sections down the side put the apps people use most first
  (Flathub's monthly installs, kept a day). Bazzite's blocklist still applies.
- **Search** finds the apps in the person's Windows too ("On your Windows",
  opening there). For an app only made for Windows (Photoshop, Office) it says
  what does the same here.
- **Hung like a gallery** rather than a grid like every store: today's pick
  framed on a painting, rooms with framed apps and a wall of tiles, the month's
  most installed numbered, Fresh paint; each section under its own painting,
  sorted by Popular, Recently updated or Name, narrowed by kind (Strategy,
  Emulators, Code editors…) or to the apps Flathub checked. Scrolling glides.
- **An app's page:** screenshots as a gallery, what it can reach (read from its
  Flatpak permissions, in plain words), sizes, version, website, and more apps
  like it. Install, Open and
  Remove go through Flatpak's own library, with progress; an account that isn't
  an administrator is told why it can't.
- **Everywhere:** the bar's and the menu's Store open it, so do `appstream://`
  links, and a Bazaar or Discover pinned before opens it too.

Tested in the VM: the front page, sections, search with the Windows note, an
app's page, and installing and removing an app. **Not done:** updates stay in
Settings → Updates, and paid or donation links aren't shown.

**Then the Store's apps** (iCloud, WhatsApp, the new Teams, Armoury Crate) too.
- **How:** Monet Bridge lists them as the person at each sign-in in Windows, and
  Monet reads each app's logo from its package.
- **Left out:** Windows' own apps (Calculator, Photos, Settings) and Xbox's.
- **Tested:** the list's shape and filter against this PC's own Windows 11 (34
  Store apps, 9 kept), and the logos with a stand-in package.
- **Needs a trip to Windows** before they show the first time.

**Not tried:** a real trip.

### 10. OneDrive (done)
**Seen.** There's no OneDrive in Files (considered, not done). Many Windows 11 PCs
keep Documents and Desktop in OneDrive as online-only placeholders on Windows'
drive, and those won't open from Monet.
**Fix:** OneDrive as a place in Files. *Medium.*
**Done:** Settings → Storage → OneDrive → Connect.
- **Signing in:** Microsoft's sign-in opens in the browser, once. The other
  questions take their defaults (the account's own drive, personal or work).
  rclone, now in the image, does the work.
- **After that:** OneDrive is at `~/OneDrive` and among the places in Files, at
  every sign-in (`monet-onedrive.service`). Each file comes down as it's opened
  and is kept a month (up to 20 GB), so the online-only files Windows leaves on
  its drive open from here.
- **Settings shows** how full it is, with Show and Disconnect. Disconnect takes it
  off this PC; the files stay in OneDrive.

**Not tried:** a real Microsoft account (the VM has no rclone). Tested with
rclone's steps stood in for.

### 11. A voice call drops on the way to Windows (done)
**Check.** During a trip to Windows, Discord isn't there unless it's installed
in Monet's Windows. Bridge's launchers don't include it.
**Fix:** offer Discord among the launchers that are installed and signed in
once. *Small to medium.*
**Done:** someone who uses Discord (or Vesktop) in Monet gets Discord's
Windows installer fetched at sign-in.
- **On the trip:** Play on Windows → Game launchers → Sign in… installs it in
  Windows as them first, then lists it to sign in to with the launchers.
- **From then on:** Windows starts it at sign-in, so a call carries on after the
  switch (it still drops for the restart itself).

Bridge builds, passes Clippy and its tests. **Not tried:** a real trip.

### 12. Games in the shared folder, on NTFS
**Check.** Proton games on Windows' NTFS drive can break on file names, letter
case, links and permissions, and Steam itself warns about NTFS libraries.
**Fix:** before 0.9.4 goes out, test the anti-cheat list and the most-played
Proton games from the shared folder on real hardware. If one fails, say so and
offer a copy on Monet's side. *Testing.*

### 13. Their own Windows, asleep (done)
**Seen.** When Windows was shut down with Fast Startup, its drive stays closed to
Monet, which keeps it safe. Settings says it opens again "after your next trip
to Windows". That's true for Monet's trips, but someone who also starts Windows
by hand and shuts it down normally is asleep again every time.
**Fix:** with the person's yes, Bridge switches Fast Startup off in their
Windows. *Small.*
**Done:** installing Monet in Windows already switches Fast Startup off (that's
the yes, given once, as part of installing it). Feature updates of Windows can
switch it back on. Monet Bridge now puts it back at every sign-in, along with
the clock in UTC, which Windows updates can reset too, and logs when it did.
Builds and passes Clippy. **Not tried:** on a Windows that a feature update
reset.

### 14. Windows' documents look different
**Check.** The image adds only Inter. Without metric-compatible fonts (Carlito
for Calibri, Caladea for Cambria, Liberation for Arial, Times New Roman and
Courier New), Word and PowerPoint files reflow in the office apps.
**Fix:** check what the base image has, and add what's missing. *Tiny.*
**Done:** the base has Liberation. The image now adds Carlito and Caladea.

### 15. Apps that don't look like Monet
**Seen.** Apps that draw their own frame (Bazaar, many Flatpak apps) have other
buttons and no glass edge. KDE apps show "File Edit Settings Help" menus and
their own dialogs. (Today Monet Snap stopped leaving a gap around the first kind
when they're snapped.)
**Fix:** not all fixable. Start with the store and the browser. *Ongoing.*
**Done for the Store:** it's Monet's own window now (9), drawn as Games and
Settings are. **Done for GTK 4 apps** (most of Flathub's): they never had
Monet's colors. KDE's own `gtk.css` for GTK 4 imports two files, so `monet-light`
took it for one someone wrote and left it alone. Now they get Monet's sheet:
- Monet's paper, cards and lily, and the sun for the button that goes ahead.
- Monet's switches.
- Window buttons drawn as the sign alone, with the title bars' dab of paint under
  the pointer.
- Titles in Fraunces.

Seen in the VM on Bazaar's pages, before the Store was Monet's own. The browser (Zen)
has worn Monet's look since 0.9.1.
**Menu bars:** Documents and the Text Editor now keep their menus behind the
toolbar's ≡, as Files and the Terminal do (Ctrl+M brings the bar back). Seen in
the VM, where both show the ≡. The Calculator keeps its bar, since it has no ≡.
**Still theirs:** the glass edge (GTK 4 always draws its own frame).

## People coming from Linux

### 16. Updates undo their tweaks
This is 2, the biggest one for them. Done.

### 17. KDE's own ways are replaced, with no way back (done)
**Seen.** Monet turns off KWin's edge tiling and top-edge maximize, takes
Windows+Z, and draws frames without KWin's borders. People who liked KDE's
versions can't easily get them back, and 2 resets them anyway.
**Fix:** a Monet Snap switch in Settings; turned off, it brings KDE's back.
*Small.*
**Done:** Settings → Light & Wallpaper → Snap layouts. Off, Monet Snap stops
snapping and KWin's own edge tiling and top-edge maximize come back, at once;
Windows+Z leaves Mouse & Keyboard's list. Updates keep the choice (2), and so
does Put back. Monet Snap stays loaded for the bar's islands (23). Tested in
the VM:
- Off: a drag to the left edge gave KWin's half, with no Snap Assist.
- On again: a drag to the right edge gave Monet's half and Snap Assist.
- The switch works from Settings itself.
**Not changed:** the frames stay Monet's, without KWin's borders; they're part
of the look, not of snapping.

### 18. Where the command-line tools go (done)
**Check.** The system is read-only (no `dnf install`). Layering packages slows
every update. Distrobox works, but nothing says so.
**Fix:** one line in About or the store ("tools for the command line: a
container"), and a container app in the store. *Small.*
**Done:** Settings → About Monet has Command-line tools: why the system can't
be changed, and Get BoxBuddy, which makes a Distrobox container in a few clicks
(Distrobox is in the system). BoxBuddy is on the store's Work & make row too,
and About's search finds "terminal", "distrobox" and "toolbox".

### 19. Renamed apps (done)
**Check.** Apps carry plain names (Files, Calculator) while guides online say
Dolphin and KCalc.
**Fix:** make sure the menu's search still finds the original names. *Tiny.*
**Seen since:** the menu's search is KDE's own, which also matches an app's file
name ("dolphin" finds Files).
**Done:** `monet-look` also puts an app's own name among the keywords of the
renamed entry, in every language's keyword line. So "Dolphin", "KCalc" and
"KDE Partition Manager" find Files, Calculator and Disks, even where the
program's name differs.

## Found while making it daily-usable (after the list above)

### 20. KDE's theme buttons took Monet's look away (done)
**Seen.** The Light and Dark buttons on More settings' first page re-applied
Monet's global theme, which named no app style: KDE wrote Qt's plain Windows
style as the default, and every window and right-click menu turned plain, with
no way back. And `monet-look` had never set the glass app style at all (its
Kvantum check failed on Fedora), so KDE's own style drew every app until now.
**Done:** the global themes name the glass style; `monet-light` puts it back at
every apply and right after KDE's buttons; the check is fixed; Light &
Wallpaper has **Monet's look → Put back** for anything else; choosing a painting
brings The Hours back where KDE's dialog put another wallpaper; More settings'
windows say "More settings"; Files' status bar keeps its words under the glass
style. *Test every built-in app with the glass style on hardware: it's new to all.*

### 21. The desktop's right-click menu speaks KDE (done)
**Seen.** "Desktop and Wallpaper", "Display Configuration", "Enter Edit Mode"
and "Show Logout Screen" open KDE's own dialogs. Windows has "Display
settings" and "Personalize", going to its Settings.
**Fix:** a Monet desktop-menu plugin (Plasma's containment actions), with
Personalize opening Light & Wallpaper and Display settings opening Display in
Monet Settings. *Medium.*
**Done, without a plugin:** The Hours adds Display settings and Personalize (a
wallpaper's entries go into Plasma's menu), opening Monet Settings' pages, and
`monet-fresh` takes KDE's Desktop and Wallpaper, Display Configuration, edit
mode, Lock Screen and Show Logout Screen out. Tested in the VM, lock screen
included. With another wallpaper the two entries go too (Put back brings them).

### 22. More settings' first page repeats Monet Settings (done)
**Seen.** KDE's Quick Settings page has its own theme buttons, wallpaper and
animation speed, and its pages keep KDE's names ("Display Configuration").
**Fix:** hide that page (and land on the most used one), and Monet's names for
the pages through the `@monet` catalogs. *Medium.*
**Seen while doing it:** Bazzite locks the hidden-pages group in
`/etc/xdg/kdeglobals` (`[$i]`, for its updater), so KDE ignored the list
`monet-look` writes in each account: KDE's Global Theme, colors, styles, frames
and the rest had been in reach all along.
**Done:** the list is one file (`share/monet/hidden-settings-pages`), which
`install.sh` adds to that locked group for everyone (uninstall takes Monet's
lines out again). Quick Settings, its wallpaper page, Activities and KDE Wallet
are on it too. More settings now always opens at a page: the one matching where
you are in Monet Settings, otherwise General Behavior. Its groups say Display,
Sound, Default Apps and Desktop, and its windows say "More settings". **Not
done:** the pages themselves keep KDE's names, which are built into each page
with no way to swap them. Tested in the VM with the list in a copy of `/etc/xdg`;
the real `/etc` needs a reinstall (or the bench's `sudo` script).

### 23. Plasma's edit mode stacks the islands (done)
**Seen.** While widgets are being edited, Plasma gives every panel room of its
own, and KWin stacks the three islands a bar's height apart until Done.
**Fix:** Monet's own widget editing without Plasma's panel edit mode, or edit
the desktop only. *Small to medium.*
**Done, more simply:** Monet Snap (KWin) puts each island back down as KWin
piles them up, so they stay on one row while editing. Plasma widens each island
for editing about a quarter second after piling them up, so the move uses the
coming width; the width an island still had would have been sent back to
Plasma (the middle island ended up off center). Tested in the VM: entering and
leaving edit mode, a notification during it, and Bar steps aside afterwards.
**Left:** while editing, notifications appear a little higher than usual,
because Plasma still keeps room for all three islands.

### 24. Small Windows habits (done)
**Done:** Num Lock on at sign-in on a desktop PC (not on laptops, whose number
pad can sit on letter keys); Windows+Tab shows all the windows, as Task View.

### 25. Notifications stuck out past the screen's edge (done)
**Seen** in the VM: every notification's right side was cut off by the screen's
edge, its close button and its last button with it. Plasma places a popup by its
content's width (x 1588 for 324 px), but Monet's glass frame adds 10 px on each
side, so the window ended at 1932 on a 1920 screen.
**Done:** Monet Snap keeps notifications inside their screen. Each now ends where
the right island does, the one already showing too. Seen in the VM, two at once.

### 26. The bar's Games button was gone (done)
**Seen** in the VM, once the test bench put 0.9.4's Games app there: the left
island showed only the sun, with an empty slot where Games should be, and
Windows+G did nothing. The 0.9.4 button only opens the app, so it had no popup
left. Without a full view of its own, Plasma took the button item itself as that
view and lifted it out of the bar.
**Done:** an empty full view, and a size as the bar's other buttons have. The
button shows and opens Games. A test had asked for no full view at all; it now
asks for the empty one.
**And Windows+G:** KWin's own Grid View held the key, so the button never got it.
`monet-look --keys` now frees it, before KWin starts, once for every account
(`keys-094`). The VM's sign-in still runs 0.9.3's `monet-look`, so this needs an
install, or a sign-in with 0.9.4, to try.

## Check on real hardware before 0.9.4 ships

- Desktop widget placement and the three bottom bars at 100/125/150/175/200%,
  including mixed-scale monitors and reconnecting a dock. The single-screen VM
  now passes these scales and restores its earlier placement on return to 100%.
  Widgets reflow within the logical work area; the middle bar fits between the
  side bars. An arbitrarily crowded desktop may still exceed the space available.
- Keyboard and Orca through every everyday app. Calendar arrows, Enter/Space,
  Home, Page Up/Down, Tab to note repetition and Escape have an initial tested
  implementation. This does not complete the full accessibility audit.

- The new window frames at 125% and 150% scaling: glass edges meeting when
  snapped, and the room to resize outside the glass.
- Monet Snap and Snap Assist on two screens.
- "0 B free" gone from Files. 0.9.3 still shows it; 0.9.4 switches to the small
  status bar, which the VM confirmed shows only the count.
- Bar steps aside, off and on: the islands stay level and alike (fixed in the
  VM: none of them keeps room of its own now; off, windows go below them).
- Monet's glass app style in every KDE app, in Mist, Smoke and each Glass level:
  the first release where it really applies.
- Resizing Settings by its glass edge with a real mouse: the edge should stay
  under the pointer from the first pixel or two on.
