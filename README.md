<p align="center">
  <img src="branding/monet-512.png" width="128" alt="Monet">
</p>

<h1 align="center">Monet</h1>

<p align="center"><b>Linux for everything. Windows only for the games that need it.</b></p>

<p align="center"><img src="branding/wallpaper-preview.jpg" width="720" alt="The Monet wallpaper: a painted harbor at dawn, an orange sun over the water"></p>

Monet is a calm, simple desktop built on Linux. The desktop is a painting that
changes light through the day, under glass. Most games run on it directly.
For the few that don't, mostly ones with anti-cheat like Valorant or Call of
Duty, press **Play** and Monet restarts in Windows, starts the game, and comes
back when you're done.

## Get it

1. On Windows, download **Make-USB-Stick.exe** from the [latest release](https://github.com/HappyHamster135/Monet/releases) and open it.
2. Choose a USB stick of 2 GB or more: it downloads Monet and writes the stick.
3. Restart from the stick and follow Monet Setup.

Monet installs itself, then downloads and installs a games-only Windows by
itself. On Linux or a Mac, write the release's Setup.iso with your disk tool.
The **[install guide](docs/INSTALL.md)** has every step.

The same USB maker works for supported x86-64 UEFI PCs with NVIDIA, AMD or Intel
graphics. The installer detects the destination PC, not the PC used to make the stick.
Monet is a preview; individual laptop hardware still needs testing.

Right-click the Home Bar and choose **Customize Home Bar → Layout** to switch
between **One bar** and **Three bars**. Monet keeps your pinned apps and widgets
and supplies any missing everyday controls. In the same editor, **Add panel →
Top-center notch** turns on the notch for that screen. Its controls are under
**Notch**. Choose **Add widgets** to put individual widgets on the current bar.
In **Transfers**, the **×** beside
an entry hides it from the list; the transfer continues and its files stay intact.

## How it works

```
 Monet                                 Windows
 ─────                                 ───────
 Press Play on Valorant
   → leaves a note for Windows
   → restarts in Windows      ───────▶ Windows starts
                                       Monet Bridge starts Valorant
                                       You play
                                       You quit
   Monet starts  ◀─────────────────── "Back to Monet in 15 seconds"
```

The note is a small UEFI variable that both systems can read, so no shared
drive is needed. Quitting the game restarts the PC into Monet by itself, and
Windows always shuts down fully, so its drive is safe to open from Monet.

## What's inside

| Folder | What |
|---|---|
| `crates/monet-core` | Shared Rust code: boot entries, the note, the games list |
| `crates/monet` | `monet` for Linux: Play, Windows, doctor, games |
| `crates/monet-bridge` | `monet-bridge.exe` for Windows: start the game, return to Monet |
| `linux/` | Installer, the look (paintings, Plasma style, widgets, glass app style), services |
| `windows/` | Installer, uninstaller, optional Game Profile |
| `image/` | Monet OS image (Bazzite with Monet built in) and the installer's kickstart |
| `tools/` | Packaging, and the generators for the paintings, icons and glass |
| `docs/` | [Install](docs/INSTALL.md) · [Design](docs/DESIGN.md) · [Testing](docs/TESTING.md) |

The full plan is in [PLAN.md](PLAN.md).

## Build

```sh
cargo test --workspace
cargo build --release -p monet --target x86_64-unknown-linux-musl   # Linux
cargo build --release -p monet-bridge                                # on Windows
```

Run the Python and Qt checks on Linux with `python3 tools/test.py`, or send them
to the configured test VM with `python tools/vm.py tests`. The Linux runner creates
a temporary home and private session bus. Each module has its own process and
timeout, so Qt fixtures cannot leave type registrations in another test app.
`--require-desktop` rejects missing desktop dependencies and unexpected skips;
the required CI desktop job supplies the matching Fedora Qt/KDE runtime and
the pinned browser test archive. See [test environments](docs/TESTING.md#automated-test-environments).

Linux release packaging also needs CMake, a C++17 compiler and Qt 6 Widgets/Test
development packages (`qt6-base-dev` on Debian/Ubuntu, `qt6-qtbase-devel` on Fedora).
`tools/package.sh linux …` builds and tests More Settings' private layout style;
the installed OS does not need these development packages. For a source install,
run `bash tools/build-settings-style.sh linux/lib/monet/qt` before `linux/install.sh`.

Pushing a new version number in `VERSION` builds everything (the apps, the
Monet OS image, and the installer ISO) and publishes a release.
Released image version tags stay fixed; scheduled base updates move only
`latest`. Installers use their versioned images. A locally qualified release
can instead publish its exact verified artifacts before advancing the default
branch; its existing version tag prevents an automatic replacement build.

Pushing to the branch named `beta` (`git push origin HEAD:beta`) publishes the
version in `VERSION` as its next beta instead (`tools/beta-release.py`): the same
signed images under their own tag (`0.9.8-7-beta.1`, then `beta`), never
`latest` or the version's tag, and a pre-release called "Monet 0.9.8-7 beta 1"
with the same downloads. Each push makes the next beta. When that same source
reaches the default branch, its release ships the beta's tested images instead
of building them again.

## Principles

- **Simple by default.** Good defaults instead of settings.
- **Performance first.** KDE Plasma, a gaming-tuned kernel, and Rust everywhere.
- **Honest about limits.** Monet never tries to bypass anti-cheat. It uses real Windows.
- **Legal.** Monet never ships Windows. You use your own copy and license.

## License

[GPL-3.0-or-later](LICENSE)
