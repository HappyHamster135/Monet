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

Monet is a preview for PCs with NVIDIA (RTX 20-series or newer), AMD or Intel graphics.

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

Pushing a new version number in `VERSION` builds everything (the apps, the
Monet OS image, and the installer ISO) and publishes a release.

## Principles

- **Simple by default.** Good defaults instead of settings.
- **Performance first.** KDE Plasma, a gaming-tuned kernel, and Rust everywhere.
- **Honest about limits.** Monet never tries to bypass anti-cheat. It uses real Windows.
- **Legal.** Monet never ships Windows. You use your own copy and license.

## License

[GPL-3.0-or-later](LICENSE)
