# Monet: Project Plan

## 1. Vision

A desktop OS that is as easy to set up as Windows, as calm to use as macOS, and
plays every PC game:

- **Linux (Monet)** for everything: browsing, work, media, and every game that runs
  through Proton.
- **A hidden, minimal Windows** used only for games Linux can't run, mostly
  games with kernel-level anti-cheat.
- **Switching takes seconds and one click.** The user thinks in terms of games,
  not operating systems.

### What makes Monet different

Existing gaming distros (SteamOS, Bazzite, ChimeraOS, Nobara, CachyOS) are
good at running games *on Linux*, but they leave anti-cheat games unsolved.
Monet's unique parts are:

1. **"Play on Windows"**: anti-cheat games get a button that switches to
   Windows, starts the game, and returns to Monet when you quit.
2. **Windows as a game console**: Monet installs and strips Windows itself, so
   the user never has to deal with Windows setup, ads, or clutter.
3. **Fast switching**: one click restarts into the game in Windows, and
   quitting it restarts into Monet. Windows always shuts down fully, so Monet
   can safely use its drive.
4. **A simple, opinionated design** inspired by Apple's simplicity, with its
   own visual identity.

### Non-goals

- ❌ Bypassing, spoofing, or emulating anti-cheat. We use real Windows.
- ❌ Running Windows in a VM for anti-cheat games. Vanguard and Ricochet block VMs.
- ❌ Distributing Windows or a modified Windows ISO.
- ❌ Writing our own kernel, Wine, or drivers.

---

## 2. Name check: "Monet"

- No existing operating system called "Monet" turned up in a search.
- "MONET" is a trademark in a few unrelated software areas (contact-center
  scheduling, content rating). Trademarks are tied to a field, so an OS is
  probably fine, but **run a proper search** (USPTO, EUIPO, class 9 and 42)
  before a public launch.
- Android 12's color system was codenamed "Monet". That was an internal
  codename, not a product, so it isn't a conflict.
- Bonus: Claude Monet's paintings are in the public domain. Museums such as the
  Art Institute of Chicago publish CC0 images of them, so they can serve as
  default wallpapers, and releases can be named after paintings ("Water
  Lilies", "Impression", "Haystacks").

**Decision: keep "Monet."**

---

## 3. How it works

### 3.1 Disk layout

```
┌──────┬──────────────────────────┬─────┬────────────────────────┐
│ EFI  │ Monet (Linux, btrfs)     │ MSR │ Windows (NTFS)         │
│ 1 GB │ rest of the disk         │16 MB│ user picks, ≥ 64 GB    │
└──────┴──────────────────────────┴─────┴────────────────────────┘
```

- One shared EFI partition holds Monet's bootloader (shim + GRUB, signed for
  Secure Boot) and Windows Boot Manager.
- **Monet is the default boot entry.** Turning the PC on always lands in Monet.
  Windows boots only when asked to.
- Monet **never mounts Windows partitions read-write**, because writing to a
  hibernated Windows disk corrupts it. At most it mounts them read-only.
- Setup asks one question about space: *"How much space for Windows games?"*
  (a slider).

### 3.2 The switch: "Play on Windows"

```
Monet                                   Windows (game mode)
─────                                   ───────────────────
User clicks "Play on Windows: Valorant"
 │
 ├─ write launch request to an EFI variable
 │    MonetLaunch = { store: "riot", game: "valorant" }
 ├─ set one-time boot: BootNext = Windows
 └─ reboot ─────────────────────────────▶ Windows starts (~10–15 s)
                                          │
                                          ├─ Monet Bridge reads + clears MonetLaunch
                                          ├─ launches the game
                                          ├─ waits for the game to exit
                                          ├─ "Back to Monet in 10 s"  [Stay] [Go now]
                                          ├─ set one-time boot: Monet
                                          └─ restart ─────────────────┐
 Monet cold-boots (~10 s) ◀────────────────────────────────────────────┘
```

**Why an EFI variable for the handoff?** It's a few bytes in firmware memory
that both systems can read and write: Linux through `efivarfs`, Windows through
`GetFirmwareEnvironmentVariable`. No shared disk means no risk of corruption.
It's written only once per switch, so wear on the firmware chip is negligible.

**Why doesn't anything hibernate?** Secure Boot must stay on for Windows
anti-cheat, and on Linux it turns on kernel "lockdown", which blocks
hibernation. Windows could hibernate, but a hibernated PC stays off until
someone presses the power button, writing its memory to disk slows the way
back, and Monet can't write to its drive while it's asleep. So both start
fresh: Monet with a fast cold boot and "Ready when you come back".

**Target times**

| Switch | Target |
|---|---|
| Click "Play on Windows" → game launching | < 30 s |
| Quit game → Monet desktop | < 20 s |

### 3.3 Windows Game Profile (the stripped-down Windows)

Applied during an unattended install of the **official** Windows ISO. Every
item is a reviewed entry in a list, not an ad-hoc script.

| Remove / disable | Keep (never remove) |
|---|---|
| Preinstalled apps, ads, "suggestions" | Windows Update |
| OneDrive, Copilot, Widgets, Teams | Defender / Windows Security |
| Search indexing, most startup items | TPM, Secure Boot, VBS components (Memory Integrity off by default, see 4.1) |
| Fast Startup (it leaves Windows' drive half asleep) | WebView2 (launchers need it) |
| Lock screen, login screen (auto-login to a local account) | DirectX and VC++ runtimes |
| Telemetry, as far as official settings allow | Gaming Services / Xbox app (for Game Pass) |

Goals: **< 25 GB disk use**, fast resume, nothing on screen except the game.
Performance settings for Windows are listed in section 4.1.

Every profile change must pass the anti-cheat test list (section 6) before it ships.

### 3.4 Setup flow

The approach: **install Monet first, then let Monet install Windows.** This
avoids writing a whole installer from scratch, makes Windows optional, and
keeps Windows from taking over the bootloader.

1. **Monet installer** (USB): language, disk, account, Windows-games space. Done.
2. **First boot**: a short welcome, then *"Set up Windows for anti-cheat
   games?"* [Set up] [Skip, I can do this later]
3. If the user chooses Set up, Monet:
   1. downloads the official Windows 11 ISO from Microsoft,
   2. creates the Windows partitions in the space set aside for them,
   3. copies Windows Setup to a temporary partition along with an
      `autounattend.xml` answer file (local account, Game Profile, Monet Bridge),
   4. reboots into Windows Setup, which runs with **no screens to click through**,
   5. on Windows' first login, Monet Bridge puts Monet back as the default
      boot entry and restarts into Monet,
   6. Monet deletes the temporary partition.
4. The user sees one progress screen: *"Setting up Windows for games… (about
   20 minutes)"*.

**License:** Windows runs unactivated, with a watermark and limited
personalization, which matters little for a games-only system. Setup offers to
enter a key and explains this plainly.

### 3.5 Monet Games (the game hub)

- One library for **Steam**, **Epic / GOG** (through Heroic or Legendary), and
  other launchers.
- Each game gets a badge: **Plays on Monet** · **Plays on Windows** · **Not supported**.
- Compatibility data comes from public sources: AreWeAntiCheatYet (anti-cheat
  status) and ProtonDB (how well each game runs).
- **Installing a Windows-only game:** v1 switches to Windows and installs it
  there. Downloading Windows games from Monet is a later research item, since it
  needs safe access to the Windows disk.

---

## 4. Technology choices

Rule: **when performance and convenience conflict, performance wins.** The
simple design is built on top through theming and locked-down settings.

| Area | Choice | Why |
|---|---|---|
| Base OS | **Fedora Atomic** via **Universal Blue** (bootc images) | Same base as Bazzite. Image-based updates with rollback. Builds on GitHub Actions. Speed comes from the kernel and gaming stack, not the base (see 4.1). |
| Desktop | **KDE Plasma 6** | Best gaming desktop on Linux: low-latency tearing in fullscreen, mature VRR and HDR, solid NVIDIA support. Its *Kiosk* system can hide advanced settings, which gives us the simple design. |
| Game Mode session | **Gamescope** (SteamOS-style fullscreen session) | Lowest overhead for controller and TV play, built-in frame limiting and FSR upscaling. Switch between Desktop and Game Mode with one click. |
| Monet apps (Linux) | **Rust core + Qt 6 / QML (Kirigami) UI** via CXX-Qt | Fast, native on KDE, easy to style |
| Monet Bridge (Windows) | **Rust** program run by scheduled tasks at sign-in | Tiny and fast, and it shares the handoff code with the Linux side. Not a Windows service: services can't start games on the user's desktop. |
| Gaming stack | Proton + Proton-GE/CachyOS builds, DXVK, VKD3D-Proton, latest Mesa, NVIDIA open kernel modules | Proven, maintained by others, always the latest versions |
| Windows install | Official ISO + `autounattend.xml` | No redistribution, fully supported by Microsoft |
| License | **GPL-3.0-or-later** | Anyone can use Monet, including other distros, but modified versions must stay open |

### 4.1 Performance tuning

**Linux side**

| Tuning | What it does |
|---|---|
| **Performance kernel** (CachyOS-patched, signed for Secure Boot) | Lower latency and better CPU scheduling under gaming load |
| **sched_ext scheduler** (`scx_lavd`, developed with Valve's funding for gaming) | Prioritizes the game's threads, so fewer stutters when other apps run |
| **NTSYNC** (kernel 6.14+) | Native Windows-style thread syncing for Wine/Proton. Faster and more accurate than esync/fsync. |
| **GameMode** + automatic performance power profile while gaming | Full CPU/GPU clocks during games, power saving otherwise |
| **Shader pre-caching** (Steam) + Mesa shader cache kept across updates | Less stutter the first time you play |
| **zram** swap, tuned `vm` settings | Smooth even when RAM is full, without slow disk swapping |
| Lean startup: only needed services, fast firmware boot | Faster cold boot, which matters because Monet cold-boots on every switch back |

**Considered and rejected:** basing Monet on CachyOS (Arch packages compiled for
newer CPUs). Its extra gains mostly show up in CPU-heavy tasks, not GPU-bound
games, and it gives up Fedora Atomic's rollback updates. We take CachyOS's
kernel instead, which is where most of the gaming benefit comes from.

**Windows side** (part of the Game Profile)

| Tuning | What it does |
|---|---|
| High-performance power plan | No CPU downclocking while gaming |
| Hardware-accelerated GPU scheduling + Windows Game Mode on | Lower latency |
| **Memory Integrity (HVCI) off by default** | Recovers a few percent of FPS (Microsoft itself says gamers can turn it off). Turned on automatically for any game that requires it. |
| No background apps, indexing, or startup items | All CPU and RAM go to the game |

### 4.2 First supported hardware

| Part | Supported in the first beta | Why |
|---|---|---|
| GPU | **AMD Radeon RX 6000 and newer** (best experience), **NVIDIA RTX 20-series and newer** | AMD's open Mesa drivers are the fastest on Linux. NVIDIA RTX 20+ supports the open kernel modules. Intel Arc comes later. |
| CPU / board | Any x86-64 PC that meets Windows 11 requirements (TPM 2.0, Secure Boot) | Needed for Windows anti-cheat anyway |
| Storage | NVMe SSD | Fast boot and switching. HDDs not supported for the system. |

**Development machines**

| Machine | GPU | What it means for Monet |
|---|---|---|
| Laptop | NVIDIA RTX 2080 (Turing) | Oldest supported generation. Hybrid graphics: games must run on the NVIDIA GPU, not the built-in one. Battery and lid behavior matter. |
| Desktop | NVIDIA RTX 5080 (Blackwell) | Only works with NVIDIA's open kernel modules (driver 570+). Bazzite's `nvidia-open` image covers both machines. |

---

## 5. Roadmap

Each phase ends with something that works on its own. The riskiest ideas are
tested first.

### Status: v0.1 (preview)

v0.1 delivers Phase 1 as an add-on for **Bazzite** (`bazzite-nvidia-open`), so
it works on both development machines with Secure Boot right away:

- `monet` (Rust, Linux): Play on Windows, open Windows, `doctor`, games list,
  app-menu shortcuts. Elevates through a polkit rule, so no password prompts.
- `monet-bridge` (Rust, Windows): starts the game as the normal user, waits
  for it to close, offers to return, restarts into Monet, and repairs the boot order.
- The handoff is a UEFI variable (`MonetLaunch`). The games list travels on the
  EFI partition, which Windows mounts only while writing it.
- A Plasma panel widget (QML) and the Monet look (wallpaper, accent color).
- `image/Containerfile`: the first Monet OS image, Bazzite with Monet built in.

Built and unit-tested, **not yet tested on real hardware**. That is Phase 0
below, with the checklist in [docs/TESTING.md](docs/TESTING.md).

The CachyOS kernel (section 4.1) is not in v0.1. Bazzite's kernel already
carries most gaming patches and is signed for Secure Boot. Switching kernels
waits for the Phase 2 benchmarks.

### Status: v0.5 (preview)

v0.5 gives Monet its own look, "Impression" (see [docs/DESIGN.md](docs/DESIGN.md)):

- **The Hours**: a generated impressionist harbor in four lights, as a Plasma
  wallpaper plugin that drifts between them through the day
- three glass islands instead of a panel; a placard with the time
- glass everywhere: a generated Plasma style, Kvantum themes for app windows,
  see-through title bars, glass Konsole; mist by day, smoke after dark
- the Monet icon theme, Fraunces and Inter, a sunrise splash, the night
  painting at sign-in and on the lock screen
- Windows Games as a gallery with covers and a sunset when you play; Quick
  Settings with Wi-Fi, Bluetooth, Night Light, sound, brightness and the light
- `monet update`, and Wi-Fi from the installer carried into Windows
- Slay the Spire is always listed, for testing: Windows installs it from Steam
  the first time and then starts it

v0.5.1 adds Monet Settings (one glass sheet in front of KDE's System
Settings), painted folders and app icons, Files on paper with glass edges,
and switches for the Hours, the placard and glass.

v0.6.1 shows the download (a Monet page over the installer, restarted when
it stalls), puts Anaconda's own font and sizes back so everything fits, and
fixes the start menu's theme on PCs without Secure Boot.

v0.6 gives the installer Monet's look from the USB stick's start menu on
(a GRUB theme, Anaconda's stylesheet loaded from conf.d), makes it sturdier (Wi-Fi wait, retried checks, Monet
downloaded ahead with retries, a fixed USB-stick guard), and moves the
Windows download to after the first sign-in.

v0.5.2 makes the switch reliable on PCs with leftover boot entries (choose a
Windows entry that can start, add one if missing, verify, log, and check the
result at the next start), makes updates manual, adds the Monet Smoke global
theme for KDE's Dark mode, and evens out the icons.

### Status: v0.3 (preview)

v0.3 makes the installer do everything. The USB stick's default choice,
**Install Monet and Windows**, erases the PC and:

- plans the disk itself (the internal disk, about one third for Windows)
- installs Monet, then downloads Windows 11 from Microsoft (same API as a
  browser) in Monet's language, and stages it on a temporary setup partition
- boots that partition once, where Monet's own script replaces the Setup
  wizard: DISM applies Windows, `bcdboot` adds it to the shared EFI partition
- answers every first-start question with an answer file: local account
  with the user's name and no password, no Microsoft account, no BitLocker
  (`PreventDeviceEncryption`), UTC hardware clock, Monet Bridge and the Game
  Profile installed on first sign-in
- removes the setup partition and gives its space to Windows, makes Monet the
  default again, and returns to Monet

**Install Monet next to my Windows** keeps the v0.2 behavior.

Known limits: PCs with Intel VMD/RST storage may need a driver Windows
Setup's environment lacks; Microsoft can block automatic downloads (Monet
then asks for a downloaded ISO); the MOK confirmation screen can't be skipped.

### Status: v0.2 (preview)

v0.2 brings Phase 3's core early: **one download, one USB stick.**

- `Monet-Installer.iso` (about 1 GB) is Fedora's network installer with a
  Monet kickstart. It installs the Monet OS image from GitHub Packages, so it
  stays under GitHub's 2 GB release limit. A full offline ISO would be about 7 GB.
- Monet prepares Windows by itself: at startup it copies Monet Bridge into
  `C:\ProgramData\Monet\Setup` and adds a one-time Startup script. The
  first time Windows starts, one UAC "Yes" installs Bridge, and the PC goes
  back to Monet. It never writes to a hibernated or BitLocker-encrypted Windows.
- The Monet OS image is rebuilt weekly to pick up Bazzite updates.

Still to do for a fully Windows-like setup: Monet branding in the installer
(it still says Fedora), a Windows app that makes the USB stick (or installs
without one), and BitLocker support for the automatic Windows setup.

### Phase 0: Prove it (research and prototypes)
Goal: show that the core ideas work on real hardware before building anything polished.

- [ ] Test PC: Fedora Atomic + Windows 11 dual boot, **Secure Boot on**
- [ ] Manual switch with `efibootmgr --bootnext` (Linux) and
      `bcdedit /set {fwbootmgr} bootsequence` (Windows); measure the time
- [ ] Hibernate Windows → boot Linux → resume Windows: does **Valorant,
      Call of Duty, Fortnite, or a FACEIT game** still work after resuming?
- [ ] Hand off data with an EFI variable, written from Linux and read from Windows
- [ ] Unattended Windows install from an `autounattend.xml` with a local account
      (check this against the current Windows 11 build)
- [ ] First draft of the Game Profile, followed by the anti-cheat test list
- [ ] Check BitLocker / device encryption behavior with BootNext switching

**Exit:** the switch works by hand, the anti-cheat games run, and the times are measured.

### Phase 1: Monet Switch MVP
Goal: one-click switching on any existing Fedora/Bazzite + Windows dual boot.

- [x] `monet` CLI + games sync service (Linux), v0.1
- [x] Monet Bridge: read the request, launch, wait, return, hibernate, v0.1
- [x] Launch support for Steam, Epic, and Riot, v0.1. Battle.net through custom entries for now
- [x] Panel widget (Linux) and "Back to Monet" shortcut (Windows), v0.1
- [x] Safety: a normal power-on always starts Monet; a failed switch leaves the boot order untouched
- [ ] All of the above confirmed on the laptop (RTX 2080) and desktop (RTX 5080)

**Exit:** a non-technical tester can play Valorant from Linux with one click.

### Phase 2: Monet OS image
- [ ] Universal Blue custom image (Fedora Atomic + KDE Plasma) with the CachyOS-patched kernel, built by GitHub Actions
- [ ] AMD/Intel image + NVIDIA image variant
- [ ] Monet Switch included
- [ ] Performance tuning from section 4.1, each one benchmarked against stock Bazzite
- [ ] Gamescope "Game Mode" session at login
- [ ] Design layer: Plasma theme, icons, fonts, Monet wallpapers, simplified settings
- [ ] Secure Boot works out of the box (signed kernel, enrolled MOK key)

**Exit:** a bootable Monet image that people can rebase to or install.

### Phase 3: Monet Setup
- [x] One-download installer ISO (network install of the Monet OS image), v0.2
- [x] Windows half set up from Monet automatically (one UAC click), v0.2
- [x] "Install Monet and Windows": fresh, unattended, games-only Windows, v0.3
- [ ] "Monet Setup" for Windows: makes the USB stick, or installs without one
- [x] Branded installer (Monet name, artwork, start menu, fewer screens), v0.4
- [ ] Monet Setup: our own installer app (Wi-Fi, your name, Install)
- [ ] First-boot wizard
- [ ] Windows ISO download, partitioning, temporary setup partition, unattended install
- [ ] Final Game Profile applied and verified automatically
- [ ] Recovery: "Repair Windows game mode" and "Remove Windows" options

**Exit:** USB to working Monet and Windows game mode with only a few questions answered.

### Phase 4: Monet Games
- [ ] Unified library (Steam first, then Heroic for Epic/GOG)
- [ ] Compatibility badges from AreWeAntiCheatYet and ProtonDB
- [ ] "Play" vs "Play on Windows" chosen automatically
- [ ] Installing Windows-only games through Windows

### Phase 5: Beta
- [ ] Hardware test matrix (AMD, Intel, and NVIDIA GPUs; several motherboard vendors)
- [ ] Public beta, feedback, bug fixing
- [ ] Documentation and website

---

## 6. Anti-cheat test list

Every release of Monet Switch and the Game Profile must pass on Windows game mode:

| Game | Anti-cheat | Why it's on the list |
|---|---|---|
| Valorant / League of Legends | Riot Vanguard | Strictest: needs TPM 2.0, Secure Boot, and a driver loaded at boot |
| Call of Duty | Ricochet | Kernel-level, blocks VMs |
| Fortnite | EasyAntiCheat (Windows-only setup) | Very popular |
| Counter-Strike 2 via FACEIT | FACEIT AC | Kernel-level, strict |
| Apex Legends | EasyAntiCheat | Linux support was removed in 2024 |

---

## 7. Risks

| Risk | Impact | Plan |
|---|---|---|
| Windows Update overwrites the boot order or bootloader | User lands in Windows | Monet Bridge checks and repairs the boot order on every Windows boot |
| BitLocker asks for a recovery key | Scary for users | Test in Phase 0. Save the recovery key in Monet, or turn off device encryption in the profile |
| Microsoft changes how unattended installs or local accounts work | Setup breaks | Pin a tested Windows build. Re-test the setup on every new Windows release |
| Stripping Windows breaks a game | Game won't run | Conservative profile + anti-cheat test list + per-game "restore component" fixes |
| Wide hardware variety | Bugs on unusual PCs | Start with a small supported-hardware list and grow it |
| Too much work for a small team | Project stalls | Reuse Universal Blue/Bazzite work. Ship Monet Switch alone first (Phase 1) |
| Anti-cheat vendors flag Monet Bridge | Bans or blocks | Bridge only launches games and never touches game processes. Talk to vendors before the beta |

---

## 8. Decisions

| Decision | Choice | Why |
|---|---|---|
| Desktop | **KDE Plasma 6 (Wayland)** | Best gaming performance and features (see section 4) |
| Base | **Bazzite** for v0.1; **Fedora Atomic** (Universal Blue) + **CachyOS-patched kernel** to be benchmarked in Phase 2 | Bazzite works today on NVIDIA with Secure Boot. The CachyOS kernel only goes in if it measurably helps (see 4.1) |
| Language | **Rust** everywhere | Native speed like C/C++, memory-safe, one codebase for Linux and Windows |
| UI | **Qt 6 / QML (Kirigami)**. v0.1 is a QML panel widget that calls the Rust CLI; a full app via CXX-Qt comes with Monet Games | Fast, GPU-rendered, native on KDE |
| License | **GPL-3.0-or-later** | Keeps Monet and its forks open source. Same family as Linux and KDE |
| First beta hardware | See section 4.2 | Best-supported GPUs on Linux. TPM 2.0 is required by Windows 11 and Vanguard |
| Leaving Windows | **Restart, not hibernate** (since 0.9.1) | A hibernated PC stays off until the power button is pressed. Restarting comes back to Monet by itself and sooner, every game starts from a cold boot as its anti-cheat expects, and Windows' drive stays safe to write from Monet |

| Branding | Sun-over-water logo, Monet Blue accent, impressionist wallpaper. See [docs/DESIGN.md](docs/DESIGN.md) | Apple's simplicity, our own look |

### Still open

- [ ] **Typeface:** move from the system font to Inter
