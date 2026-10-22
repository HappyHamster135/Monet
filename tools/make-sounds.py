"""Writes Monet's sounds: one soft instrument, felt mallets on warm bars and a
little struck glass, in a small room. Notes go up for what arrives and down
for what leaves, all in F major, so two sounds at once never clash.

Writes a freedesktop sound theme to linux/share/sounds/monet: index.theme and
stereo/<name>.oga (Ogg Vorbis) for the names Plasma plays. A name not made
here comes from KDE's Ocean, which the theme inherits.

Needs numpy and soundfile (pip install soundfile).

Run from the repository root:  python3 tools/make-sounds.py
"""

from pathlib import Path

import numpy as np
import soundfile

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "linux" / "share" / "sounds" / "monet"
RATE = 48000

# KDE's sound settings preview a theme with its Example (without one, Ocean's
# theme-demo, through Inherits).
INDEX = """[Sound Theme]
Name=Monet
Comment=Soft felt and glass
Inherits=ocean,freedesktop
Directories=stereo
Example=desktop-login

[stereo]
OutputProfile=stereo
"""

# The overtones above each note: (times its pitch, how loud next to it, how long
# it rings next to it). Felt: a soft mallet on a warm bar, between a felt piano
# and a marimba. Glass: a struck glass bar, a little shimmer.
FELT = ((2, 0.2, 0.55), (3, 0.06, 0.4), (4, 0.1, 0.25), (9.9, 0.012, 0.08))
GLASS = ((2.76, 0.18, 0.4), (5.40, 0.05, 0.2), (8.93, 0.015, 0.1))

MESSAGE = ((0, "C5", 0.7), (0.11, "F5", 0.78))

# name: (voice, how long it rings, loudness in dBFS, notes as (seconds, note, velocity)).
SOUNDS = {
    # Signing in: the sun coming up, F major rising into a chord. Signing out: going down.
    "desktop-login": (FELT, 1.4, -8, [(0, "F3", 0.5), (0.11, "C4", 0.55), (0.22, "F4", 0.6), (0.33, "A4", 0.65),
                                      (0.44, "C5", 0.7), (0.62, "F5", 0.62), (0.62, "A5", 0.3)]),
    "desktop-logout": (FELT, 1.3, -9, [(0, "C5", 0.6), (0.15, "A4", 0.55), (0.3, "F4", 0.52), (0.46, "C4", 0.5),
                                       (0.64, "F3", 0.48)]),
    # Something new for you: up a fourth. Done: up to the home note. A timer: the message, three times.
    "message-new-instant": (FELT, 1, -9, MESSAGE),
    "complete": (FELT, 1, -9, [(0, "A4", 0.6), (0.09, "C5", 0.65), (0.18, "F5", 0.75)]),
    "alarm-clock-elapsed": (FELT, 1, -8, [(start + at, note, v) for start in (0, 0.55, 1.1) for at, note, v in MESSAGE]),
    # Dialogs: a drop of glass to tell you something; a question goes up; a warning
    # and errors come down, the serious ones further and darker.
    "dialog-information": (GLASS, 1, -10, [(0, "C6", 0.6)]),
    "dialog-question": (FELT, 1, -9, [(0, "A4", 0.62), (0.13, "D5", 0.72)]),
    "dialog-warning": (FELT, 1, -9, [(0, "D5", 0.75), (0.13, "A4", 0.7)]),
    "dialog-error": (FELT, 1, -9, [(0, "A4", 0.75), (0.14, "D4", 0.7), (0.14, "F4", 0.45)]),
    "dialog-error-serious": (FELT, 1, -9, [(0, "A4", 0.8), (0.14, "F4", 0.75), (0.28, "D4", 0.75), (0.28, "D3", 0.5)]),
    # An app or the terminal ringing the bell: a tap on glass.
    "bell": (GLASS, 0.6, -11, [(0, "F5", 0.6)]),
    # Each step of the volume: a short tap, never tiring when it repeats.
    "audio-volume-change": (FELT, 0.3, -12, [(0, "A5", 0.7)]),
    # A drive or device in and out: glass, up and down a fifth. Power: up and down an octave.
    "device-added": (GLASS, 1, -10, [(0, "C5", 0.6), (0.08, "G5", 0.65)]),
    "device-removed": (GLASS, 1, -10, [(0, "G5", 0.6), (0.08, "C5", 0.55)]),
    "power-plug": (FELT, 1, -9, [(0, "F4", 0.6), (0.1, "F5", 0.65)]),
    "power-unplug": (FELT, 1, -9, [(0, "F5", 0.6), (0.1, "F4", 0.55)]),
    # The battery low (KDE's caution), then very low (KDE's battery-low).
    "battery-caution": (FELT, 1, -9, [(0, "A4", 0.62), (0.13, "A4", 0.5), (0.28, "F4", 0.6)]),
    "battery-low": (FELT, 1, -8, [(0, "A4", 0.66), (0.13, "A4", 0.55), (0.28, "F4", 0.62), (0.45, "D4", 0.62)]),
    # Emptying the trash: a few notes tumbling away.
    "trash-empty": (FELT, 0.7, -10, [(0, "C6", 0.45), (0.045, "A5", 0.5), (0.09, "F5", 0.55), (0.135, "C5", 0.6),
                                     (0.18, "A4", 0.62)]),
}
# Other names KDE plays for the same things.
SOUNDS["dialog-error-critical"] = SOUNDS["dialog-error-serious"]
SOUNDS["bell-window-system"] = SOUNDS["bell"]


def hz(note):  # "F4", "Bb3"; A4 is 440
    step = "C D EF G A B".index(note[0]) - 9 + note.count("#") - note.count("b")
    return 440 * 2 ** ((step + 12 * (int(note[-1]) - 4)) / 12)


def fade_out(sound, part):
    n = len(sound) // part
    sound[len(sound) - n:] *= np.linspace(1, 0, n)[:, None] ** 2


def strike(freq, velocity, voice, ring):
    """One note in stereo, a hair flat on the left and sharp on the right for
    warmth; low notes ring longer, soft ones are darker."""
    tau = 0.25 * ring * (440 / freq) ** 0.5
    t = np.arange(int(7 * tau * RATE)) / RATE

    def partial(f, level, rings):
        return level * np.exp(-t / (tau * rings)) * np.sin(2 * np.pi * f * t)

    overtones = sum(partial(freq * k, level * velocity, rings) for k, level, rings in voice)
    # And the felt's soft knock on the bar: a low thud of noise, gone in a few milliseconds.
    n = int(0.05 * RATE)
    thud = np.fft.irfft(np.fft.rfft(KNOCK.standard_normal(n)) * (np.fft.rfftfreq(n, 1 / RATE) < 1500), n)
    overtones[:n] += 0.03 * thud / thud.std() * np.minimum(t[:n] / 0.001, 1) * np.exp(-t[:n] / 0.008)
    note = np.stack([partial(freq * 0.9993, 1, 1) + overtones, partial(freq * 1.0007, 1, 1) + overtones], axis=1)
    # The felt meets the bar over a few milliseconds, softer notes more slowly.
    note *= (np.sin(np.minimum(t / (0.004 + 0.006 * (1 - velocity)), 1) * np.pi / 2) ** 2 * velocity ** 1.5)[:, None]
    fade_out(note, 10)
    # Low notes a little to the left and high ones to the right, as at a piano.
    pan = (np.clip(np.log2(freq / 440) * 0.2, -0.3, 0.3) + 1) * np.pi / 4
    return note * [np.cos(pan), np.sin(pan)]


def room(seed):
    """A small warm room's echo: noise dying away in about half a second, the highs first."""
    n = int(0.8 * RATE)
    t = np.arange(n) / RATE
    noise = np.fft.rfft(np.random.default_rng(seed).standard_normal(n))
    highs = np.fft.rfftfreq(n, 1 / RATE) > 2500
    echo = np.fft.irfft(noise * ~highs, n) * np.exp(-t / 0.09) + 0.5 * np.fft.irfft(noise * highs, n) * np.exp(-t / 0.04)
    echo[:int(0.01 * RATE)] = 0  # the sound reaches the walls and comes back
    return echo / np.sqrt(np.sum(echo ** 2))


ROOM = (room(1), room(2))  # a different echo in each ear, for space
KNOCK = np.random.default_rng(3)


def render(voice, ring, loudness, notes):
    struck = [(int(at * RATE), strike(hz(note), velocity, voice, ring)) for at, note, velocity in notes]
    dry = np.zeros((max(start + len(x) for start, x in struck), 2))
    for start, x in struck:
        dry[start:start + len(x)] += x
    n = len(dry) + len(ROOM[0])
    size = 1 << n.bit_length()
    sound = 0.12 * np.stack([np.fft.irfft(np.fft.rfft(dry[:, c], size) * np.fft.rfft(ROOM[c], size), size)[:n]
                            for c in (0, 1)], axis=1)
    sound[:len(dry)] += dry
    # Until it has died away (-54 dB), then faded out, so it never ends with a click.
    level = np.abs(sound).max(axis=1)
    sound = sound[:np.nonzero(level > level.max() / 500)[0][-1] + 1]
    fade_out(sound, 5)
    return sound * 10 ** (loudness / 20) / np.abs(sound).max()


def main():
    (OUT / "stereo").mkdir(parents=True, exist_ok=True)
    (OUT / "index.theme").write_text(INDEX)
    for name, spec in SOUNDS.items():
        sound = render(*spec)
        assert np.abs(sound[[0, -1]]).max() < 1e-6, name  # starts and ends in silence: no clicks
        soundfile.write(OUT / "stereo" / f"{name}.oga", sound, RATE, format="OGG", subtype="VORBIS",
                        compression_level=0.5)
        print(f"wrote {name}.oga, {len(sound) / RATE:.2f} s")


if __name__ == "__main__":
    main()
