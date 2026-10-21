# Monet design

Monet should feel calm and obvious. If something needs explaining, the design
isn't finished.

## Principles

1. **It just works.** Good defaults instead of settings. No terminal for
   everyday use.
2. **One thing at a time.** One main action per screen, one question per dialog.
3. **Plain words.** Say what will happen, in the user's words.
4. **Quiet.** No ads, no badges, no numbers nobody asked for.
5. **Honest.** Say what didn't work and what to do next. Never pretend.

## Words

Short sentences. Sentence case. Talk about games and the PC, not boot entries.

| Write | Not |
|---|---|
| Restart in Windows? | Set BootNext to Boot0000 and reboot? |
| Play on Windows | Launch via Windows Boot Manager |
| Back to Monet | Return to Linux bootloader |
| Windows wasn't found on this PC. | ERROR: no EFI load option matching bootmgfw.efi |
| Your PC will restart. Open apps will close. | Unsaved data may be lost. Continue? (Y/N) |

Buttons name the action: **Restart**, **Play**, **Cancel**. Never "OK" when a
word would be clearer, except where Windows forces it.

## Color

Taken from *Impression, Sunrise* (Claude Monet, 1872): a sun over water.

| Name | Hex | Use |
|---|---|---|
| Monet Blue | `#3D6FB6` | Accent: buttons, selection, links |
| Sunrise | `#F28A3C` | The logo's sun. Sparingly, for the one thing that matters |
| Sky | `#9DB3DF` | Light gradients |
| Blush | `#F1C7B8` | Light gradients, near the horizon |
| Deep Water | `#2E4A7E` | Dark gradients |
| Night | `#141B2E` | Dark wallpaper sky |

Light and dark mode both use Breeze with Monet Blue as the accent.

## Type

The system font (Noto Sans in Plasma) for now. **Inter** is the target: clean,
neutral, and open source (SIL OFL). Two weights only: regular and semibold.

## Icons

- Rounded square, soft vertical gradient, one simple symbol.
- **Monet** (`branding/monet.svg`): the sun over water.
- **Windows Games** (`branding/monet-windows.svg`): a window with a play button.
  It doesn't use Microsoft's logo.
- Everything else follows the Breeze icon theme.

## Wallpaper

`linux/share/wallpapers/Monet`: an impressionist sunrise, light by day and
dark at night. Made by `tools/make-branding.py`, so it can be changed and
re-rendered.

## Not Apple

Monet takes Apple's *simplicity*, not its look. No Apple logos, icons, fonts
(San Francisco), wallpapers, or product names.
