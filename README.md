<p align="center">
  <img src="branding/monet-512.png" width="128" alt="Monet">
</p>

<h1 align="center">Monet</h1>

<p align="center"><b>Linux for everything. Windows only for the games that need it.</b></p>

<p align="center"><img src="branding/wallpaper-preview.jpg" width="720" alt="The Monet wallpaper"></p>

Monet is a calm, simple desktop built on Linux. Most games run on it directly.
For the few that don't, mostly ones with anti-cheat like Valorant or Call of
Duty, press **Play** and Monet restarts in Windows, starts the game, and comes
back when you're done.

## Get it

**[Download Monet 0.1](https://github.com/HappyHamster135/Monet/releases)** ·
**[Install guide](docs/INSTALL.md)**

Monet 0.1 is a preview for Bazzite with an NVIDIA RTX 20-series or newer GPU.

## How it works

```
 Monet                                 Windows
 ─────                                 ───────
 Press Play on Valorant
   → leaves a note for Windows
   → restarts in Windows      ───────▶ Windows wakes up (hibernated, so it's fast)
                                       Monet Bridge starts Valorant
                                       You play
                                       You quit
   Monet starts  ◀─────────────────── "Back to Monet in 15 seconds"
```

The note is a small UEFI variable that both systems can read, so no shared
drive is needed. Windows hibernates instead of shutting down, so it resumes in
seconds with the anti-cheat already running.

## What's inside

| Folder | What |
|---|---|
| `crates/monet-core` | Shared Rust code: boot entries, the note, the games list |
| `crates/monet` | `monet` for Linux: Play, Windows, doctor, games |
| `crates/monet-bridge` | `monet-bridge.exe` for Windows: start the game, return to Monet |
| `linux/` | Installer, panel widget, wallpaper, services |
| `windows/` | Installer, uninstaller, optional Game Profile |
| `image/` | Monet OS image: Bazzite with Monet built in |
| `docs/` | [Install](docs/INSTALL.md) · [Design](docs/DESIGN.md) · [Testing](docs/TESTING.md) |

The full plan is in [PLAN.md](PLAN.md).

## Build

```sh
cargo test --workspace
cargo build --release -p monet --target x86_64-unknown-linux-musl   # Linux
cargo build --release -p monet-bridge                                # on Windows
```

Pushing a new version number in `VERSION` builds both and publishes a release.

## Principles

- **Simple by default.** Good defaults instead of settings.
- **Performance first.** KDE Plasma, a gaming-tuned kernel, and Rust everywhere.
- **Honest about limits.** Monet never tries to bypass anti-cheat. It uses real Windows.
- **Legal.** Monet never ships Windows. You use your own copy and license.

## License

[GPL-3.0-or-later](LICENSE)
