One USB stick installs everything: Monet, and a games-only Windows that sets itself up.

**Start here: [Install Monet](https://github.com/HappyHamster135/Monet/blob/HEAD/docs/INSTALL.md)**

### Downloads

| File                               | What                                                                                                                                                   |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Monet-0.9.3-Make-USB-Stick.exe** | **Start here** (on Windows): makes the Monet USB stick for you.                                                                                        |
| Monet-0.9.3-Setup.iso              | Monet Setup, Monet's own installer: the USB stick's image, for writing it yourself (on Linux or a Mac). Here once it has installed Monet in a test PC. |
| Monet-0.9.3-Installer.iso          | Fedora's installer dressed as Monet: the stick's image when there's no Setup.iso.                                                                      |
| Monet-0.9.3-Windows.zip            | Monet Bridge for Windows: to update a Windows set up before 0.9.2, or for "next to my Windows" when Windows is encrypted                               |
| Monet-0.9.3-Linux.tar.gz           | Only for adding Monet to an existing Bazzite install                                                                                                   |

### New in 0.9.3: Windows looks like Monet, sticks that work

- **A trip to Windows looks like Monet.** While Windows starts a game, Monet's
  painting covers the screen with the game's name, and Back to Monet now if
  you change your mind. A launcher that needs you comes up over it. When you
  quit, Monet says Back to Monet and counts down: Go now, or Stay in Windows.
  A Windows that Monet installs from now on hides its taskbar until you
  point at it.

- **Sign in to your game launchers once.** Settings → Play on Windows → Game
  launchers → Sign in… restarts in Windows with Steam, Epic, Riot,
  Battle.net and the rest listed. Sign in to each, with Remember me ticked,
  and the games you play from Monet start without asking.

- **Windows games up to date.** Settings → Play on Windows → Update Windows
  games → Update & switch off. Windows updates itself and your games, then
  switches the PC off, so the next Play starts the game, not a download. Good
  before you go to bed.

- **The blue screen, in pictures.** Monet Setup's last page shows the blue
  screen at Monet's first start step by step, to take a photo of. And if
  Continue boot is chosen anyway, the PC asks again by itself and restarts
  into the blue screen: no USB stick needed.

- **Make-USB-Stick.exe works with more sticks.** It wiped the stick's
  partition table before writing, which made some sticks stop answering
  halfway and left them looking dead. Now it writes over what's there, closes
  every part of the stick first (with a drive letter or not), and tries a
  busy stick again. If writing still fails, it says so: the stick isn't
  broken, and Windows can format it again in Disk Management.

Updating from 0.9.2: Monet updates by itself within a day (or Settings →
Updates → Install, then restart), and Monet Bridge updates itself the next
time you come back from Windows. For a new install, download the new
**Monet-0.9.3-Make-USB-Stick.exe**.

### New in 0.9.2: set up your way, your phone in reach

- **Monet Setup asks what Fedora's installer did, the Monet way.** Hello
  has your time zone: a region, then a city, with the time there now. Setup
  guesses it from your language and, once online, from where the PC is,
  unless you chose one. Your password is typed twice, and any password will
  do. Or leave it empty: Monet then signs you in by itself and the screen
  doesn't lock, and Setup says so before you go on.

- **The blue screen, skipped by accident, isn't the end.** After
  installing, a blue screen asks to trust Monet, and it opens on "Continue
  boot", which leaves Monet unable to start. Start from the USB stick again:
  Setup sees it and offers **Ask again and restart**, and the blue screen
  is back.

- **Your phone.** Settings → Phone pairs your phone with the app (a QR code
  gets it), then shows its battery, rings it, sends it a file, and opens its
  texts and files on the PC.

- **Monet Bridge keeps itself up to date.** On the way back to Monet,
  Windows checks for a newer Monet Bridge, checks the download is whole,
  installs it and restarts as before. A Windows that Monet set up also wears
  the painting as its wallpaper.

- **A magnifier.** Settings → Accessibility → Magnifier: Windows key and
  plus or minus zooms in and out.

- **Your fingerprint.** With a fingerprint reader, Settings → Lock & Privacy
  sets up a finger, which then unlocks the screen and answers administrator
  prompts. (The sign-in screen still asks for the password.)

- **Text from a picture, in your language.** A screenshot's Extract Text
  reads every language Monet speaks, starting with yours.

- **Save a report.** Settings → About Monet → Save a report puts one file
  in Documents with what someone helping you needs: the PC, this start's
  errors, the start before, sleep and Monet's own records.

- **Make-USB-Stick.exe, sturdier.** It writes the start of the stick last,
  so Windows can't take over the stick halfway, and if writing fails it
  notes Windows' reason in Monet-USB-Stick.log in your temporary files. An
  ISO dropped on it is written as it is.

Updating from 0.9.1: Monet updates by itself within a day (or Settings →
Updates → Install, then restart). Monet Bridge updates itself from this
version on: once more, in Windows, download **Monet-0.9.2-Windows.zip**,
open it and double-click **Install Monet**. Setup's changes are for new
installs.

### New in 0.9.1: safe to update, at home on both sides

- **A new Monet that doesn't start goes back by itself.** If an update
  hasn't brought up the sign-in screen within five minutes of starting, the
  PC restarts into the Monet from before, Settings → Updates and the next
  sign-in say so, and the daily update waits for the next one.

- **Reset this PC.** Settings → Updates → Reset this PC puts Monet back
  as it came at the next restart: its settings, the desktop's look and the
  changes made to the system, for everyone. Files, games and apps stay, and
  so do accounts, Wi-Fi and printers. It asks for an administrator's
  password first, and keeps everyone's settings from before.

- **Your disk, encrypted.** On a PC with a security chip (TPM 2.0, which
  every Windows 11 PC has), Monet Setup encrypts Monet's disk, and Monet
  unlocks it by itself when it starts, as Windows does with BitLocker. Setup
  shows your recovery key once, eight groups of eight letters: keep it
  somewhere other than the PC. Monet asks for it only when the chip can't
  vouch for the start (after a big firmware update, or with the disk in
  another PC).

- **Controllers and headsets on both sides.** Pair a Bluetooth controller
  or headset in Monet, then once in Windows: Monet picks up Windows'
  pairing at its next start, so it works in both from then on, instead of
  each pairing undoing the other.

- **Back to Monet by itself.** Quitting a game in Windows restarts the PC
  into Monet. Before, Windows hibernated and the PC stayed off until you
  pressed the power button. And Windows' clock is right after a switch now,
  instead of off by your time zone.

- **A quicker sign-in.** Work that can wait (painting new apps' icons,
  Zen's look, games on a laptop's NVIDIA chip) runs a minute after you sign
  in, at the lowest priority, and only when something it looks at changed.
  Steps that only matter once, or after a trip to Windows, are skipped the
  rest of the time.

- **What you saw in 0.9.0, fixed:**
  - The desktop and the lock screen were black instead of showing the
    painting.
  - The bar could stay hidden, and pointing at the bottom of the screen
    rarely brought it back (in a virtual machine, never). It stays in view
    again; Light & Wallpaper → **Bar steps aside** still lets it slide away.

Updating from 0.9.0: Monet updates by itself within a day (or Settings →
Updates → Install, then restart). The painting is back at once, and the bar
at your next sign-in. Monet
Bridge, in Windows, doesn't update by itself yet: once, in Windows, download
**Monet-0.9.1-Windows.zip**, open it and double-click **Install Monet**.
Then quitting a game restarts into Monet and Windows' clock is right.
Encryption comes with Monet Setup, so it's for new installs.

### New in 0.9.0: your files kept safe, a painting for every season

- **Earlier versions of your files.** Every hour Monet keeps your files as
  they were: all from the last day, then one a day for two weeks and one a
  week for two months. Settings → Backups opens them as they were an hour,
  a day or a week ago, and in Files, right-click a file → **Earlier
  versions** to show one of its versions or put it back beside it. They
  only take room for what has changed since, and the oldest go first when
  the disk gets full.

- **A copy on a USB drive.** Pick a drive once in Settings → Backups.
  Whenever it's plugged in, at most once a day, Monet copies your files to
  "Monet Backup" on it, leaving out caches, the Trash and games. What a copy
  replaces or deletes is kept on the drive for three months, and a week
  without a copy says so once.

- **Keep your Windows and your files.** In Monet Setup, "Monet next to my
  Windows" no longer needs a full reset: with too little free space, Monet
  makes room by shrinking Windows' drive (Windows keeps what it uses and
  half its free space, at least 30 GB). Leave **Bring my files** ticked and
  your Desktop, Documents, Pictures, Music, Videos and Downloads (OneDrive's
  too) come along into your new folders, named in your language; they stay
  in Windows as well. A Windows left asleep by Fast Startup, a drive that
  needs a check, or BitLocker each say what to do instead. With Fedora's
  installer, **Install Monet next to my Windows** → **Free up space**
  shrinks Windows too, and your files stay on Windows' drive, a click away
  in Files.

- **A painting for every season.** **The Magpie** joins the wall, after
  Monet's *La Pie*: a farm under snow, trees white with frost and one
  magpie on the gate, with Monet's blue and violet shadows across the snow,
  in four lights like the others. **Through the year** in Light & Wallpaper
  hangs the season's painting: The Hours in spring, Water Lilies in summer,
  Haystacks in autumn, The Magpie in winter (the other way round south of
  the equator).

- **Every painting, repainted in oil.** All four are laid in strokes of a
  loaded flat brush now: its bristles streak the paint, and the end of each
  stroke breaks up where the brush runs dry. Water Lilies has lilies drawn
  by hand, no two alike, and pads that float apart instead of piling up;
  the Haystacks are rounder and looser; the people in The Hours' boats are
  a few quick strokes, as Monet put them down.

- **The painting follows your sun and your weather.** The Hours turns to
  dawn, midday, dusk and night at your own sunrise and sunset (from the
  Weather widget's town, or else your time zone's city), not at fixed hours.
  Rain, fog and snow where you are soften the painting with mist; Light &
  Wallpaper turns that off.

- **Focus, like a painter outdoors.** Timer → **Focus**, then start:
  notifications stay quiet until the timer ends, and The Hours runs a whole
  day, dawn to night, over the session.

- **Save the last 30 seconds.** Turn it on in Games & Controllers, then
  **Windows key + Alt + G** saves the last 30 seconds of the screen and its
  sound as a video in Videos, as Xbox Game Bar does. The first time, it
  installs its recorder and asks once which screen to record.

- **Which games play here.** Play on Windows' covers and the Windows Games
  widget mark the games that play in Monet too ("Plays here too"), and Games
  & Controllers lists the games installed here whose anti-cheat only allows
  Windows.

- **HDR and smoother games.** Settings → Display offers **HDR** and
  **Smoother games** (variable refresh rate) on a monitor that can do them.

- **Search finds Settings' pages.** Search the menu for "printers" or
  "Wi-Fi" and that page of Settings is there.

- **The bar steps aside.** The islands at the bottom slide away when a
  window comes over them, and back when you point at the bottom of the
  screen. Light & Wallpaper → **Bar steps aside** keeps them in view.

- **What you saw in 0.8.5, fixed:**
  - Make a Monet USB stick found no USB stick to write to.
  - Settings → Updates called the update "44.20261012.1"; it says "Monet
    0.9.0" now.
  - Settings can be made bigger and smaller from its edges and corner
    (double-click "Settings" to fill the screen), and keeps its size. Its
    scroll bar no longer runs into the highlighted page.
  - Settings, the popovers (Disks & Devices, Audio Volume, Notifications),
    the menu's search and the bar have the clear glass, like the desktop
    widgets, instead of a matte one.
  - Notes in the clock's calendar no longer leave it wide after they close,
    and a note shows in the Calendar widget at once instead of after a
    while. The clock's highlight in the bar fits it.

Updating from 0.8.5: Monet updates by itself within a day (or Settings →
Updates → Install, then restart). The first start after it takes a little
longer, once, while Monet gets your files ready for earlier versions. At your
next sign-in the bar starts stepping aside, and Windows key + Alt + G is
there for Save the last 30 seconds.

### New in 0.8.5: in your language, under clearer glass

- **Monet speaks your language.** Settings, Monet Setup, the widgets, the
  lock and shut-down screens, notifications and the Make a Monet USB stick
  tool come in 29 languages besides English, from Spanish, Chinese and
  Hindi to Swedish and Hebrew. Monet Setup's first page offers them all,
  each with its keyboard; a keyboard without Latin letters keeps the US one
  beside it (Alt+Shift switches), so Wi-Fi passwords can still be typed.
  Arabic and Hebrew read from right to left, and the layout with them.

- **Clearer glass, closer to Apple's.** You see the painting's brushstrokes
  through the widgets, the bar and the popovers now, only softened. Along the
  widgets', the bar's and the popovers' edges the glass bends the light a
  little, like a real pane, and the rim catches the light at the top left
  and bottom right. Quick Settings' tiles are pebbles of lighter glass, as
  in Control Center.

- **Monet for AMD and Intel too.** Monet now comes in two: one for NVIDIA
  graphics (RTX 20 series, GTX 16 and newer) and one for AMD and Intel,
  without NVIDIA's driver. The installer picks the right one for the PC by
  itself, and updates stay with it. PCs with an older NVIDIA card can now
  install Monet as well: it draws with the open driver, fine for everyday
  things, while games run best in Windows.

- **The everyday apps are built in.** Photos, Documents, Video, Music,
  Calculator and Archives are part of Monet now: there at your first
  sign-in, in Monet's look (Music's icon is a painted gramophone), and small (they share what the desktop already
  has). Pictures, PDFs, films, songs, archives and text each open in the
  right one from the start, and Files shows what's inside PDFs and videos.
  Before, Monet came with no apps beyond Steam, Lutris and the Text Editor.

- **Choose more while installing.** Monet Setup has a new step, Your apps:
  Zen Browser is ticked, and Office, Mail, Discord, Spotify, Heroic, Prism
  Launcher, OBS Studio and Krita are a click away. They download after your
  first sign-in and show up in the menu under their plain names. A PC set
  up before gets Zen once, by itself.

- **What other systems have, Monet's way.** The things you'd miss coming
  from Windows, a Mac or a phone:
  - **A welcome** at your first sign-in: where Quick Settings and the
    widgets are, Play on Windows, the light, and searching Settings, each
    with its way there.
  - **Each app's own volume**, in Settings → Sound, and a choice of where
    sound plays (speakers, headphones, a screen) under the volume in Quick
    Settings.
  - **A hotspot** in Settings → Wi-Fi: a phone or tablet can use this PC's
    internet; its name and password are right there.
  - **Protect the battery** in Power & Sleep, on laptops that can (ThinkPads
    and many more): charging stops at 80%, so the battery lasts more years.
  - **Batteries**, a new widget: this laptop, the mouse, the keyboard,
    controllers and headphones, each with how full it is.
  - **LocalSend** among Your apps in Monet Setup and in the Store: send
    files between the PC and your phone.
  - Recording the screen (Meta+Alt+R) is in the list of shortcuts.
  - **Ready when you come back** (Settings → Play on Windows, off until you
    turn it on): after Windows, Monet starts your desktop behind the lock
    screen, so it's there as soon as you type your password.
  - **Last start** in Settings → About: how long the PC, Monet and your
    desktop each took to start.
  - Quick Settings' All Settings is a pebble of glass like its tiles.

- **Four new widgets.** System, Recently Played, Timer and World Clock, in
  the widget gallery:
  - System: how hard the processor, the graphics and the memory are working,
    on dials that warm from lily to the sun, how hot they run, and what's
    downloading.
  - Recently Played: the games you played last, with their covers; one
    click and you're back in.
  - Timer: a few minutes on the sun's path, with a ring and a notification
    when they're up.
  - World Clock: the time in other towns, each on a little clock face,
    light by day and dark by night.

- **Notes for your days, on the desktop and in the bar.** The Calendar
  widget and the clock's month share the same notes:
  - Days with a note have a dot under them; point at one to read it. The
    line under the month shows the chosen day's note.
  - Notes (or a click on that line) brings out a panel beside the month to
    write the day's note, step to the day before or after, and see what's
    coming up. It's kept as you type.
  - The clock's month now turns too: ‹ ›, the wheel, or the arrow keys, and
    a click on the month's name comes back to today.
  - Make the Calendar wide and the notes sit beside the month.

- **Weather in more than one place.** Add another town or country from the
  card (or its settings), and the ‹ › beside the place's name go through
  them; each keeps its last forecast, so going back is instant.

- **Two more paintings.** Light & Wallpaper offers Monet's Water Lilies and
  Haystacks beside The Hours, each drifting through dawn, midday, dusk and
  night the same way.

- **More of Settings.** Three new pages, and one that says more:
  - **Games & Controllers** (new): your controllers and their batteries,
    pairing a new one and testing its buttons, the performance overlay over
    games, and where your games are kept.
  - **Lock & Privacy** (new): when the screen locks, the password after
    sleep, and whether Files and the menu remember what you opened (and
    forgetting it).
  - **Printers** (new): your printers, what's printing and waiting, and
    which one is the default. Printers on your network show up by
    themselves.
  - **Mouse & Keyboard** also lists the keyboard shortcuts worth knowing.
  The rarer settings are a "More…" away on each page.

- **What's new, after each update.** Once a new Monet has started, a note
  offers its highlights, and Settings → Updates keeps them.

- **At home on a laptop.** The battery, the keyboard's light and Wi-Fi on
  the move get their place:
  - Quick Settings and Power & Sleep show the battery: plugged in or
    charging, and how long it lasts.
  - A slider for the keyboard's light, and Monet's own signs when you
    press the brightness, keyboard-light and touchpad keys.
  - The arrow on the Wi-Fi and Bluetooth tiles opens their page, to pick a
    network or a device; the tile itself still switches it on and off.
  - Networks you've joined before join again without the password, and
    work and school networks (eduroam) ask for your name too.
  - Bluetooth switches back on even after KDE's own switch turned it off.
  - Settings scrolls its list of pages on a small screen.
  - Monet doesn't update over a phone's hotspot.
  - Brightness follows the laptop's own screen when a monitor is plugged in.

- **Laptop gaming.** On a laptop with an NVIDIA chip beside its built-in
  graphics, Minecraft (Prism Launcher), RetroArch, the console emulators and
  the other games in the Store's Play row start on the NVIDIA chip by
  themselves. Everything else, Steam's window too, stays on the built-in
  graphics, which saves the battery. The Store's Play row also has LACT, to
  watch and tune the graphics card: its fans, clock speeds and power.

- **Kinder to older PCs.** Monet runs well on an older laptop too:
  - Monet Setup checks the PC before anything is erased: too little memory
    is said on the first page, and Install waits. An older NVIDIA card, or
    4 to 6 GB of memory, is mentioned before installing.
  - Glass off (Light & Wallpaper) now reaches the desktop widgets and the
    lock screen too: they sit on paper instead of blurring the painting,
    much lighter for older graphics. Monet still turns it off by itself
    where there's no graphics driver.
  - On a PC with 8 GB of memory or less, or a spinning hard disk, Monet goes
    easier by itself: the widgets' glass leaves out its magnifying edge,
    Files searches by name instead of reading every file (unless you've
    chosen otherwise), and Steam starts a little after the desktop instead
    of with it, so signing in is quicker.

- **Ink signs in apps' toolbars and menus.** Save, print, zoom, rotate,
  crop and the rest are brushed in the same ink as the bar, and change with
  the light.

- **Tooltips on one clean pane.** The names that show when you point at
  something sit on a single sheet of glass, no longer a box within a box.

- **Zen, more at home.** The open tab sits on a pebble of paper, the address
  field rings in lily while you type, and Zen starts ready, without its
  welcome tour or asking to be the default.

- **Easier to find your way.** Small things that said too little:
  - Weather's place button now says "Add a place", and the place shown can
    be forgotten right there; when the weather can't be reached, a click
    tries again.
  - The widget gallery says how many of a widget are on your desktop, and
    "Remove all" when there's more than one.
  - Quick Settings says what Hours, Mist and Smoke do, Wi-Fi says "Not
    connected" instead of "On", and Night Light and Do Not Disturb have an
    arrow to their settings.
  - Pointing at the town in Weather, the cover in Now Playing, the Photo
    Frame, the Timer's minutes or your name in the menu says what a click
    (or the wheel) does. An empty Photo Frame says where photos come from.
  - World Clock has a + for another town while you point at it.
  - The lock screen names the painting that's really hanging, and a wrong
    password says so plainly, for longer.
  - "Windows & Games" in Settings is now "Play on Windows", so it isn't
    mixed up with Games & Controllers; if Windows doesn't finish starting,
    the note says where to check, not a command to type.
  - Monet Setup reminds you to take a photo of the blue screen's steps
    before restarting.
  - Clearing recent files says it's done.
  - Searching Settings works in your language, not only in English, and
    accents don't matter: "ecran" finds "Écran".

- **When an app closes unexpectedly.** A short note says so, with its name
  and picture, and Open it again starts it straight back. Before, it just
  vanished. When only a part of it stops, like a browser's tab or a game
  under Steam, nothing is said.

Updating from 0.8.3: Monet updates by itself within a day (or Settings →
Updates → Install, then restart). At your next sign-in the glass turns
clearer and the apps' names follow your language; your panels and widgets
stay as they are. A PC with AMD or Intel graphics stays on the Monet it
has; `sudo bootc switch ghcr.io/happyhamster135/monet-amd:latest` moves it
to the one made for it.

### New in 0.8.3: your apps, kept up to date

- **Choose your apps while installing.** Monet Setup has a new step, Your
  apps: the everyday ones are ticked (Zen Browser, Photos, Documents,
  Video, Music, Calculator), and Office, Mail, Discord, Spotify, OBS
  Studio and Krita are a click away. They download after your first
  sign-in and show up in the menu under their plain names. A PC set up
  before gets the everyday ones once, by itself. Before, Monet came with
  no apps beyond Steam, Lutris and the Text Editor.
- **Zen is the browser, in Monet's look.** Web links open in Zen
  Browser (Settings → Default Apps picks another). Its window sits on the
  painting, softened as behind glass, with lily for the accent, in Mist by
  day and Smoke by night like the rest of Monet, and a new tab opens on The
  Hours itself.
- **The big apps, painted.** Zen, Discord, Spotify, OBS Studio, Krita,
  LibreOffice, Thunderbird, Chrome, VLC, Telegram, Heroic, Prism Launcher,
  RetroArch, Bottles, GIMP, Blender, Kdenlive, Audacity, VS Code, Obsidian
  and Signal get icons in Monet's oil paint that keep their own marks, so
  you still know them at a glance.
- **Every app fits in.** An app Monet hasn't painted shows its own icon
  on a small painted canvas, with the brush's texture over it, as soon as
  it's installed. Your Steam games too.
- **Monet keeps itself up to date.** Once a day, in the background: your
  apps right away, and a new Monet ready for your next restart, never
  while you work. Settings → Updates → Update automatically turns it off.
  What apps leave behind as they update is cleared away too.
- **Go back to the Monet from before.** If something stops working after
  an update, Settings → Updates → Go back starts the one before at your
  next restart, with your files and apps as they are.
- **Every page of Settings is Monet's.** Mouse & Keyboard, Power & Sleep,
  Notifications and Default Apps no longer open KDE's settings:
  - **Mouse & Keyboard:** pointer speed, tap to click, natural scrolling,
    left-handed and "off while typing" for the mouse and the touchpad, and
    the languages you type in, found by name.
  - **Power & Sleep:** Power saver, Balanced or Performance, when the
    screen turns off and when the PC sleeps (plugged in and on battery),
    and what the power button and the lid do.
  - **Notifications:** Do Not Disturb, sounds, going quiet by itself while
    a game fills the screen or you share it, where popups appear and how
    long they stay, and which apps may pop up.
  - **Default Apps:** what opens web links, mail, folders, music, video,
    photos, PDFs and text, with the Store offered when nothing can.
  - **Accessibility** (new): the size of everything, a larger pointer,
    less motion, and the screen reader when there is one.
  - **Storage** (new): what fills the PC (games, apps, your files,
    Monet) in one bar, and room to make: empty the Trash, look through
    Downloads.
  The rarer settings are a "More…" away on each page.
- **The Calendar opens its days.** Click a day for its page: the date in
  Fraunces, ‹ › to the day before or after, Today to come back, and a note
  for that day, kept as you type. Days with a note have a dot of lily under
  them. Make the widget wide and the month and the day sit side by side;
  the wheel turns the months.
- **Now Playing starts the music.** With nothing playing it offers your
  music apps, the PC's own first, or the Store to find one. While something
  plays, a line shows how far along it is, with the time gone and the time
  left: click or drag it to go there. The cover brings the player forward.
- **The Photo Frame fades and steps.** Pictures fade from one to the next,
  ‹ › appear while you point at the frame, and a click opens the picture in
  Photos.
- **Account pictures from Monet's world.** Change Avatar offers pieces of
  The Hours (sunrise, midday on the water, dusk, the moon, a boatman, the
  harbor's lights) and small paintings (a water lily, poppies, the Japanese
  bridge, a haystack, the magpie, irises, a parasol, a sailboat) instead of
  KDE's dragon and photos.
- **One switch for the light.** Brightness and Night Light are in Quick
  Settings, beside Mist and Smoke, so KDE's own Brightness panel, with its
  second "Dark Mode" switch, leaves the bar.
- **The bar's highlight keeps to its icon.** The pebble behind an open icon
  in the bar no longer reaches over the icons beside it.
- **Trash is the garden pot again.** 0.8.1's sign for Trash in menus had
  taken the dock's painting; menus keep the sign and the dock the pot.
- **Date & Time and Accounts are Monet's own.** Settings shows the time as
  your clocks will, sets it from the internet, finds your time zone by its
  city and switches to 24-hour time (from your next sign-in). Accounts shows
  you with your picture and name, changes your name and your password on
  Monet's paper, and lists the other people on the PC. Before, both opened
  KDE's settings; the face in the menu now opens Accounts here too.
- **Monet's own sounds.** Messages, warnings and errors, a drive or the
  charger plugged in or out, a low battery, the volume step and emptying the
  trash sound like Monet now: soft felt and glass, quiet and warm. Before,
  they were KDE's.

Updating from 0.8.2: Settings → Updates → Install, then restart. After
that Monet updates by itself. At your next sign-in KDE's Brightness panel
leaves the bar, Monet's sounds take over from KDE's, and the everyday apps
start downloading.

### New in 0.8.2: the everyday screens

- **Monet's own menu.** The sun in the left island opens your pinned apps
  and the files you opened last, a search for apps, files and settings that
  starts as you type, all your apps from A to Z, and you at the foot with
  Lock and the power sign. The pins you had stay. Before, this was KDE's
  menu in Monet's colors.
- **Restart and shut down on Monet's screen.** The desktop softens behind
  one question, "Restart now?" with the sun on Restart and a countdown, and
  the screen fades to night before the PC goes. From the power sign,
  Ctrl+Alt+Del or the PC's power button, it offers sleep, restart, shut down
  and sign out, and says see you soon.
- **Monet's password prompt.** When an app needs more rights, Monet says
  what it wants and asks for your password on its own paper, with Cancel
  and the sun to allow it. A wrong password shakes it.
- **Widgets the way a Mac does them.** Right-click the desktop and choose
  Add or Manage Widgets (or Settings → Light & Wallpaper → Edit widgets): a
  gallery opens beside your desktop, with Monet's widgets down the side and
  big cards showing each one as it looks, + Add on each, and Remove for the
  ones already out. Click one to add it, or drag it where you want it; Done
  when you're finished. KDE's widgets are a list under More widgets.
- **Editing the desktop is light.** While you add or move widgets the
  desktop steps back into a frame on a wash of mist or smoke, instead of
  KDE's blur of the whole desktop, which stuttered wherever the processor
  draws the screen, as in a virtual machine.
- **Widgets from the start.** The placard, Weather and Calendar
  could miss a desktop when Plasma started slowly, and then never came. Now
  a new account starts with Monet's layout, and any desktop without them gets
  them once, trying again at the next sign-in if Plasma wasn't ready.
- **The weather breathes.** The next four days have room under today.
- **Choose the weather's place on the card.** "Where are you?": type your
  town and pick it, right on the widget, instead of a settings window. Click
  the place's name for another. Fahrenheit comes on by itself where the PC's
  region uses it.
- **Just the widgets in the gallery.** Each card shows the widget itself
  with its shadow, without the painting around it, and the list down the
  side has an icon for each, Weather and Placard newly painted.
- **Plainer questions and errors.** Monet asks "Set up Windows?" as a
  question, not a warning. When Windows can't be set up, the box says why
  (not enough room, for one) with the details behind a button, and
  cancelling the password quietly stops instead of reporting a failure.
  Message boxes in every app have Monet's ink signs instead of KDE's
  triangle.

Updating from 0.8.1: Settings → Updates → Install, then restart. At your
next sign-in Monet's menu takes the place of KDE's in your panel, with your
pins, the widgets come if your desktop has none, and the right-click menu
offers Add or Manage Widgets.

### New in 0.8.1: just Monet

- **The painting goes with the light.** Choosing Mist or Smoke now changes
  the painting too, on the desktop and the lock screen: Mist drifts between
  dawn and midday, Smoke between dusk and night (or stays on midday or
  night with The Hours off). Before, only the colors changed.
- **Smoke, not Dark Mode.** KDE's own Global Theme page, with its "Switch to
  Dark Mode at Night" and Day-Night Cycle, is gone from More settings; its
  first page offers Mist and Smoke, and its Automatic means Follow the hours.
- **More settings looks like Monet Settings.** KDE's settings, one click
  away as More settings, get the same painted marks as Monet Settings'
  list, leave out the pages Monet looks after (themes, colors, window
  frames, icons, splash and sign-in screens, effects, KDE's updater, About
  this System), and Help menus no longer offer About KDE.
- **Apps by plain names.** Files, Terminal, Text Editor, Photos, Documents,
  Screenshot, Calculator, Music, Phone... instead of Dolphin, Konsole and
  the rest. KDE's and Bazzite's own tools leave the menu, and nothing
  greets you from Bazzite anymore: no portal or announcements at sign-in,
  no welcome in Terminal, no KDE Welcome Center after updates. KDE's
  About page says Monet.
- **The Store's front page is Monet's:** Play, Talk & stream, Music & film,
  Work & make and Everyday, each under a strip of The Hours (by daylight in
  Mist, by night in Smoke), without Bazzite's notes.
- **The window buttons are back.** In 0.8, minimize, maximize and close on
  Monet's window frames were there but invisible. Their pictures were named
  the way KDE doesn't look for them.
- **Updates draw from the new pictures.** KDE remembers what it measured in
  each of Monet's pictures, by file and time, and on Monet's image every
  file keeps its time from one version to the next. Now the first sign-in
  after an update starts KDE afresh, so frames and buttons come out right.
- **Monet's sign-in screen.** Bazzite's desktop signs in with KDE's Plasma
  Login Manager, not the SDDM that 0.8 dressed, so the sign-in still showed
  Bazzite's picture. Now it's the harbor at night, with Monet's colors,
  icons, type and pointer.
- **A clock of Monet's own** in the panel: the time over the date, and a
  click opens the day and its month on the glass, today on a dab of the sun.
- **The widgets after updating.** Desktops that kept their layout from
  before Monet had widgets get the weather and the month, once.
- **Files shows how much room is left** on the drive, in its status bar.
- **Menus and toolbars in ink.** The desktop's right-click menu, Files'
  toolbar and the power buttons get signs written with a brush, instead of
  KDE's.
- **The bar's icons are Monet's.** Sound, network, Bluetooth, brightness,
  media, notifications, the clipboard, drives and the battery were KDE's (or,
  for the volume, a music note from Monet's file icons). Plasma 6.7 takes
  them from the icon theme, so that's where Monet's ink signs are now,
  tinted for Mist or Smoke like the rest.
- **Straight glass edges.** The light along the glass's rim jumped a pixel
  where each corner met a straight edge, and the blur behind ran past the
  rounded corners in steps. The rim now follows the corner's curve, the
  blur stays inside it, and the shadow's edge under the glass is smooth.
- **Smoother in a virtual machine.** Where nothing but the processor draws
  the screen, Monet starts without glass, which made everything lag; turn
  it on in Settings → Light & Wallpaper to see it anyway.

Updating from 0.8: Settings → Updates → Install, then restart. Monet's look
freshens when you sign in (the plain names, More settings, the painting
for your light, the clock, the widgets); your panels stay as they are.

### New in 0.8: Monet's own, down to the pointer

- **Every icon is a small oil painting,** in short strokes the way Monet
  painted, with violet shadows and warm light. Settings is a painter's
  palette, Terminal a night canvas on an easel, System Monitor the harbor's
  masts at sunset, the Store a market bouquet, Trash a garden pot. KDE's
  apps (Gwenview, Okular, Kate, Ark, Spectacle, ...) and the app menu's
  categories get paintings too.
- **The rest of the dock and the menu too.** The browser is a window thrown
  open onto the harbor, Steam a locomotive steaming into Saint-Lazare,
  Lutris a rowing boat, Bazzite Portal the Japanese footbridge at Giverny,
  and the Flatpak tools, Waydroid and Input Remapper have paintings of their
  own.
- **Files and drives are painted.** Text, code, pictures, music, films,
  PDFs, spreadsheets, programs and archives each have their own painted
  sheet; disks are a paint box, USB sticks a tube of paint.
- **Monet's own window frames.** Title bars are the same glass as the
  window. The buttons are signs brushed in ink, and a dab of paint swells
  up under the one you point at: lily, ochre, or the sun to close.
- **Monet's pointer:** ink with a paper edge, and Monet's sun breathing
  over its reflection while something works.
- **Clearer glass.** The painting's color comes through the panels and
  popovers more, and their edges catch the light like a pane of glass:
  brightest along the top, fading down the sides.
- **Widgets on the desktop.** Weather, Calendar, Now Playing, a Note and a
  Photo Frame, as glass cards that frost the painting behind them. A new
  desktop starts with the weather and the month at the top right; the rest
  are in the widget gallery. The weather comes from Open-Meteo once you
  choose a place (no account; only the place is sent).
- **Monet's own lock screen.** At rest, the painting and its placard: the
  date, the time in Fraunces, which light it is. Touch a key and the
  painting softens behind a sheet of glass with your name, a well for the
  password and the sun to go back in. If it ever can't load, KDE's lock
  screen takes its place, so you can always unlock.
- **The bar's signs** for sound, Wi-Fi, battery, notifications, the
  clipboard, drives and power are brushed in ink. Sleep is the moon, shut
  down the setting sun.
- **Starting and signing in are Monet's.** The boot screen is the harbor at
  dawn (and asks for a disk password there), and the sign-in screen has
  Monet's fields, buttons, colors and pointer.
- **Monet's own installer on the USB stick.** Make-USB-Stick.exe now writes
  Monet Setup whenever the release has it, and Fedora's installer only
  otherwise. Monet Setup couldn't be built before: a check in its build
  stopped it every time.
- **Firmware updates in Settings.** Updates now also finds new firmware for
  the PC's own parts (its UEFI, disks, docks), from their makers, and
  installs it when you press Install, never by itself. It says when one
  installs during the next restart, and what's in the way (like "Plug in
  the charger first").

- **The first start can't be missed.** Both installers now say, before you
  restart, what the blue screen at the first start wants: Enroll MOK, then
  `monetsetup`. Choosing Continue boot there left Monet unable to start with
  Secure Boot on ("bad shim signature"); the install guide says how to
  recover if it happened.

Updating from 0.7: Settings → Updates → Install, then restart. The new look
arrives when you sign in; your panels stay as they are, and the weather and
the other widgets are in the desktop's widget gallery.

### New in 0.7: Monet all the way through

- **Quick Settings and Monet Settings open.** In 0.6.4 they didn't load at
  all ("Sorry! There was an error loading Quick Settings"). Now they do,
  and Settings → Windows & Games → Check Monet works again.
- **Make-USB-Stick.exe opens.** It closed right after asking for
  administrator rights. Now its window shows, and if something ever goes
  wrong it says what, instead of disappearing.
- **The bar is Monet's everywhere.** Running apps get a small dab of sun
  under them: longer for the window you're in, faint when it's minimized.
  The app menu, search, notifications, the popovers, the lock screen and
  Alt+Tab use Monet's buttons, switches, sliders and highlights instead of
  KDE's. When a window touches the islands they turn solid but stay
  Monet's, instead of becoming plain KDE panels.
- **Menus float.** Right-click menus and tooltips in apps like Files and
  Terminal cast a soft shadow, have dividers between groups again and a
  lily highlight.
- **The Store and other Flathub apps in Monet's colors.** Paper or smoke,
  lily for choices, the sun for the button that goes ahead. Before, newer
  apps like the Store kept their own grey and blue, older ones lost KDE's
  colors, and dark mode was bluish. The Store's icon in the dock is
  Monet's painted bag.
- **Settings is clearer.** Each page shows its painting and how things
  stand ("Connected to Harbor"), the list glides to the page you're on,
  pages that open KDE's settings are marked ↗, Bluetooth devices show what
  they are, secured networks show a lock, and updates show they're
  working. Everything fits again: "More settings in KDE" had slipped off
  the bottom.
- **Terminal** has a thin cursor, more room around the text, and its menu
  behind a button instead of a menu bar.
- **Window shadows** are softer and wider, in ink instead of black.

Updating from 0.6: Settings → Updates didn't open in 0.6.4, so open
Terminal and run `monet update`, then restart. The new look arrives when
you sign in; your panels stay as they are.

### New in 0.6.4: make the USB stick with one click

- **Monet-0.6.4-Make-USB-Stick.exe.** On Windows, double-click it, choose the
  USB stick, and it does the rest: downloads Monet (picking up where it
  stopped if the connection drops), writes the stick and checks it. Only
  USB sticks are offered, never the disk Windows runs from, and it asks
  before erasing. Nothing else to download or install: no Rufus, no
  Etcher, no Fedora Media Writer.

### New in 0.6.3: Monet's own switches

- **No more blue switches.** Apps that drew the usual blue toggles (Bazaar,
  Flatseal, Bottles and other GTK apps) now use Monet's: a pill that turns
  lily green when on, with a white knob. Checkboxes, radio buttons, sliders
  and progress bars match, in Mist and in Smoke.
- **Store is Bazaar when Bazzite has it**, otherwise Discover, and the dock's
  store button opens it.

### New in 0.6.2: more of Monet, everywhere

- **Apps from Flathub look like Monet.** GTK apps (Flathub's and the
  system's) use Monet's paper and ink, lily for choices and the sun for the
  button that goes ahead, and turn to Smoke after dark with the rest of
  Monet. A gtk.css you wrote yourself is left alone.
- **Store.** Discover is called Store in the dock and the app menu, and no
  longer pops up about updates: those stay in Settings, when you ask.
- **More in Settings:** Mouse & Keyboard, Power & Sleep, Notifications,
  Date & Time, Accounts and Default Apps, each with its swatch from the
  paintings. They open the matching page in KDE's settings.

Updating: sign out and in again after the update.

### Fixed in 0.6.1

- **The download shows itself.** Monet is a 5.7 GB download, and the installer
  only said "Running pre-installation scripts" the whole time, so it looked
  stuck. Now a Monet page covers it: how much is downloaded, how long is
  left, and a note that it picks up again if the connection drops.
- **A download that stops moving starts again by itself** after four minutes,
  keeping what it already has. Before, a stalled connection could hang there
  for hours.
- **Everything fits again.** 0.6 swapped the installer's font for a wider one
  and made its buttons roomier, but its screens are laid out for its own font
  and sizes, so labels and buttons spilled out of their boxes. The installer
  keeps Monet's colors and painting and its own font and sizes.
- **The painted start menu shows** on PCs without Secure Boot (GRUB gave up
  on it because the big title font was too wide for its text layer). With
  Secure Boot on, GRUB doesn't accept fonts from the stick, so the plain
  menu shows; Monet Setup, coming next, skips the menu altogether.

### New in 0.6: Monet's own installer

- **Monet from the first second.** The USB stick is called Monet, and its
  start menu is the harbor at dawn with the choices on smoked glass. The
  installer says "Loading Monet", and its pages are Monet's paper and ink:
  Inter for reading, Fraunces for titles, lily for your choices and the sun
  for the button that goes ahead, with the harbor rising along the bottom of
  the welcome and progress pages. (Before, only the side picture was Monet's;
  the rest of its look never loaded.)
- **Fewer "unknown error"s.** The installer waits for Wi-Fi, checks Monet can
  be downloaded (trying a few times), and downloads it in a way that picks up
  again when the connection drops, instead of failing on the first hiccup.
  It never mistakes the USB stick for the PC's disk, even when the stick
  doesn't say it's USB, and it waits for every disk to show up first.
- **A shorter install.** Windows no longer downloads at the end of the
  install, where 7 GB looked like the installer had stopped. It downloads
  after your first sign-in, with its progress showing, and Monet asks before
  restarting to install it.
- **Monet's name everywhere.** The PC's boot menu, KDE's About page, the
  sign-in screen (with Monet's mark) and the PC's network name say Monet.
- **A personal touch.** The placard on the desktop greets you by name:
  good morning, good evening, and "still up?" after midnight.

### Fixed in 0.5.2

- **Play goes to Windows.** Many PCs keep their old Windows boot entry after
  the disk is wiped, and Monet picked that one, so the PC came straight back
  to Monet. Monet now only starts a Windows entry whose partition is really
  there, and makes one if the PC has none. A Windows that's still finishing
  its own setup goes first for the trip, so its own restarts don't land in
  Monet. Monet checks that the switch was saved before restarting, always
  restarts through the PC's firmware, and the first trip after Windows set
  itself up no longer turns straight back before the game starts.
- **If a trip doesn't reach Windows,** Monet says why at the next sign-in
  (and in Settings → Windows & Games), and tries another way next time.
  Every trip is logged in `/var/lib/monet/switch.log`.
- **Dark mode keeps Monet's look.** KDE's Light and Dark choices now pick
  Monet Mist and the new **Monet Smoke**, instead of Breeze. Choosing a Monet
  theme in KDE's settings no longer resets the glass or the painting. If dark
  mode already broke your desktop, it's mended at the next sign-in.
- **Updates only when you ask.** Monet no longer updates in the background.
  Settings → Updates checks, installs Monet and app updates when you say so,
  then offers a restart.
- **Icons in step.** Settings, System Monitor, Store and Trash are redrawn on
  the same grid as Files and Terminal, so the dock reads evenly.
- **Smoother light changes.** Hours, Mist and Smoke switch once, right after
  the toggle moves, instead of stuttering it.

Sleep works normally on Monet. What Monet can't do is hibernate (Secure
Boot's lockdown blocks it), which is why Windows is the one that hibernates
to switch fast.

### New in 0.5.1: Settings and Files

- **Monet Settings.** One glass sheet with the settings you actually change:
  Light & Wallpaper, Wi-Fi, Bluetooth, Display, Sound, Windows & Games,
  Updates and About. The pages sit on paper so they're easy to read, and each
  is marked with a swatch cut from the paintings. Open it from Settings in the
  dock or the app menu, or All Settings in Quick Settings. Everything else is
  one click away under **More settings in KDE**.
- **Painted folders and icons.** Folders are cut from the paintings (Home and
  Documents in dawn light, Downloads at night, Pictures, Music and Videos at
  dusk), with a small white mark for what's inside. Files, Terminal,
  Settings, Store, System Monitor and Trash are painted marks with nothing
  behind them, instead of icons on tiles.
- **Files** keeps its glass at the edges only: your files sit on paper, with
  a soft Lily selection, bigger icons and previews.
- **New switches** in Settings → Light & Wallpaper: keep one painting all day
  instead of following the hours, hide the placard, or turn glass off for
  solid panels and windows.
- **Window titles** are set in Fraunces, like the clock.
- **Windows & Games** in Settings shows whether Windows is ready, plays a game
  from its cover, and checks that everything is set up.

Updating from 0.5: restart after the update. Your panels stay as they are,
and Settings in the dock opens Monet Settings.

### New in 0.5: Impression

Monet has its own look now, after Claude Monet's _Impression, soleil levant_.

- **The Hours.** The wallpaper is one painted harbor in four lights: dawn,
  midday, dusk and night. It drifts from one to the next as the day goes.
- **Glass.** The bar is three glass islands along the bottom, and panels,
  popovers, title bars, the terminal and app windows like Files are
  see-through, with the painting blurred behind them. Mist while it's light
  out, smoke after dark. Choose Hours, Mist or Smoke in Quick Settings.
- **A placard** on the desktop with the time, the date and the painting's name.
- **Windows Games** is a gallery of covers. Play asks once, then the screen
  fades to night as the sun sets, and the PC restarts in Windows.
- **Quick Settings** in the clock island: Wi-Fi, Bluetooth, Night Light,
  Do Not Disturb, sound, brightness and the light.
- **New icons and fonts:** the sun mark, painted pebbles for Monet's own apps,
  Fraunces for the clock and titles, Inter for reading.
- **A sunrise** when Monet starts, and the night harbor at sign-in.
- **The installer** uses the dawn painting and the sun for its main button.

Also new:

- **`monet update`** gets the newest Monet right away (it also updates by itself).
- **Wi-Fi carries over:** the network you used while installing works in Windows too.
- **For testing:** Slay the Spire is always in Windows Games. The first time,
  Windows installs it from Steam (sign in to Steam once), then starts it.

Updating from 0.4: restart after the update and your desktop changes to the
new look by itself.

### New in 0.4

- **Monet's own installer look.** The installer says Monet instead of Fedora,
  with Monet's sunrise artwork, logo and colors.
- **Monet's start menu on every PC.** The USB stick's menu now shows "Install
  Monet and Windows" (selected) and "Install Monet next to my Windows". Before,
  most PCs still showed Fedora's menu, with "Test this media" selected.
- **One screen less.** No root password screen: the person installing is the
  administrator.

### Fixed in 0.3.1

- "Test this media" on the USB stick works again (the installer's checksum was missing).
- If Monet can't be downloaded during the install, the installer now says why
  (no internet, or the Monet package isn't public) instead of "unknown error".

### New in 0.3

- **Install Monet and Windows.** The default choice on the USB stick. Monet
  splits the disk, installs itself, then downloads Windows 11 from Microsoft
  and installs it by itself. Nothing to prepare in Windows first.
- **Windows sets itself up.** No setup questions, no Microsoft account, no
  BitLocker, no Fast Startup. Monet Bridge and the Game Profile are
  installed automatically, and preinstalled apps games don't need are removed.
- **Matches Monet.** Windows uses your name, language, keyboard and time zone
  from the Monet install.
- **If the download fails,** choosing Windows in Monet tries again, or installs
  from a Windows file you downloaded yourself.
- **Install Monet next to my Windows** is still there for keeping an existing
  Windows.

### Good to know

- **Preview.** Not tested on real hardware yet.
- The installer's wording ("Installation Summary", "Begin Installation") is
  Fedora's own and can't be changed; everything around it is Monet's.
- "Install Monet and Windows" **erases the PC**.
- Windows activates by itself if the PC came with Windows. Otherwise it runs
  unactivated (small watermark).
- One blue screen at the first start can't be skipped: it's how the PC's
  firmware confirms the NVIDIA driver may run with Secure Boot on.
