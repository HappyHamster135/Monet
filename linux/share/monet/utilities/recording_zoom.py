"""Timed recording zooms in source coordinates, shared by preview and export."""
from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction
from math import isfinite


@dataclass(frozen=True)
class Zoom:
    start: int
    end: int
    x: float = .5
    y: float = .5
    amount: float = 1.8

    def __post_init__(self):
        if (not 0 <= self.start < self.end or not 0 <= self.x <= 1 or not 0 <= self.y <= 1
                or not 1.05 <= self.amount <= 4):
            raise ValueError("Invalid zoom position, interval or magnification")

    def ramps(self):
        half = (self.end - self.start) / 2
        return min(420, half), min(650, half)

    def travel(self, crop):
        x, y, w, h = crop
        fraction = 1 / self.amount
        def axis(focus, offset, length):
            ideal = ((focus - offset) / length - fraction / 2) / (1 - fraction)
            return min(1, max(0, ideal))
        return axis(self.x, x, w), axis(self.y, y, h)

    def viewport(self, ms, crop):
        rise, fall = self.ramps()
        t = max(0, min(1, (ms - self.start) / rise, (self.end - ms) / fall))
        fraction = 1 / (1 + (self.amount - 1) * t*t*(3 - 2*t))
        tx, ty = self.travel(crop)
        x, y, w, h = crop
        return x + tx*w*(1-fraction), y + ty*h*(1-fraction), w*fraction, h*fraction


FULL = (0., 0., 1., 1.)


def active_index(zooms, ms):
    idx = bisect_right(zooms, ms, key=lambda z: z.start) - 1
    return idx if idx >= 0 and ms < zooms[idx].end else None


def zoom_filters(zooms, start, end, size, crop, fps):
    """Sample the edits on the source clock before the playback speed changes."""
    items = [z for z in zooms if z.start < end and z.end > start]
    if not items:
        return None, []
    if any(a.end > b.start for a, b in zip(items, items[1:])):
        raise ValueError("Zooms must be ordered and cannot overlap")
    width, height = size
    if crop:
        _, _, w, h = crop
        width, height = max(2, int(width*w/2)*2), max(2, int(height*h/2)*2)
    if min(width, height) < 1:
        raise ValueError("No picture size for zoom export")
    # Screen captures can be variable-rate. Duplicate a still frame when it
    # needs to move through a ramp. Preserve high frame rates in imported video.
    rate = Fraction(fps if isfinite(fps) and fps > 0 else 30).limit_denominator(1001)
    # Some variable-rate files advertise the 1 kHz container clock as fps.
    rate = min(240, max(30, rate))

    def choose(values, lo, hi):
        if hi - lo == 1:
            return values[lo]
        mid = (lo + hi) // 2
        cut = (items[mid].start - start) / 1000
        return f"if(lt(it,{cut:.6f}),{choose(values,lo,mid)},{choose(values,mid,hi)})"

    levels, xs, ys = [], [], []
    for z in items:
        rise, fall = z.ramps()
        a, b = (z.start-start)/1000, (z.end-start)/1000
        levels.append(f"st(0,clip(min((it-({a:.6f}))/{rise/1000:.6f},"
                      f"({b:.6f}-it)/{fall/1000:.6f}),0,1));1+{z.amount-1:.6f}*ld(0)^2*(3-2*ld(0))")
        tx, ty = z.travel(crop or FULL)
        xs.append(f"{tx:.8f}")
        ys.append(f"{ty:.8f}")
    z, x, y = (choose(values, 0, len(items)) for values in (levels, xs, ys))
    return rate, ["format=yuv444p", f"zoompan=z='{z}':x='(iw-iw/zoom)*({x})':"
            f"y='(ih-ih/zoom)*({y})':d=1:s={width}x{height}:fps={rate}"]
