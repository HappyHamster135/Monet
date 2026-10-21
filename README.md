# Monet

**Linux for everything. Windows only for the games that need it.**

Monet is a planned desktop operating system built on Linux, with a simple, calm
design. Most games run on Monet directly through Proton. For the games that
don't, mainly ones with kernel-level anti-cheat such as Valorant or Call of
Duty, Monet keeps a small, stripped-down copy of Windows in the background and
switches to it with one click, in seconds.

> Status: **planning**. Nothing is built yet. See [PLAN.md](PLAN.md) for the full plan.

## The idea in one picture

```
 ┌──────────────────────── Monet (Linux) ────────────────────────┐
 │  Browsing, work, media, and most games (Proton)               │
 │                                                               │
 │  Monet Games:  [ Elden Ring  ▶ Play ]                         │
 │                [ Valorant    ▶ Play on Windows ]  ──┐         │
 └─────────────────────────────────────────────────────│─────────┘
                                                       │ ~15–25 s
 ┌──────────── Windows "game mode" (hidden) ───────────▼─────────┐
 │  Minimal Windows, resumes from hibernation, game starts       │
 │  automatically. Quit the game → back to Monet.                │
 └───────────────────────────────────────────────────────────────┘
```

## Main parts

| Part | What it does |
|---|---|
| **Monet OS** | The Linux system: image-based, auto-updating, simple design |
| **Monet Setup** | A Windows-like installer that also sets up Windows for games |
| **Monet Switch** | One-click switching between Monet and Windows |
| **Monet Bridge** | Small Windows service that launches the game and returns to Monet |
| **Monet Games** | One game library for Steam, Epic, and GOG, which picks the right system for each game |
| **Windows Game Profile** | The safe list of what Monet removes from Windows and what it keeps |

## Principles

- **Simple by default.** Good defaults instead of settings. No terminal needed.
- **Honest about limits.** Monet never tries to bypass or fool anti-cheat. It
  uses real Windows for the games that need it.
- **Legal.** Monet never ships Windows. It downloads the official image from
  Microsoft, and the user provides their own license.
- **Built from proven parts.** Fedora Atomic, Universal Blue, Proton, and Mesa. Our
  work goes into the experience, not into reinventing them.
