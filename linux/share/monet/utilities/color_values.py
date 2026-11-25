"""sRGB color values shared by the screen picker and Command Bar."""
import colorsys
import math
import re
from typing import NamedTuple


class Color(NamedTuple):
    red: float
    green: float
    blue: float
    alpha: float = 1.0

    def bytes(self):
        return bytes(math.floor(channel * 255 + 0.5) for channel in self)

    def text(self, form):
        red, green, blue, alpha = self.bytes()
        include_alpha = self.alpha != 1 or form in ("rgba", "hsla")
        def decimal(value):
            return f"{value:.4f}".rstrip("0").rstrip(".")
        if form in ("rgb", "rgba"):
            channels = f"{red}, {green}, {blue}"
            return f"rgba({channels}, {decimal(self.alpha)})" if include_alpha else f"rgb({channels})"
        if form in ("hsl", "hsla"):
            hue, light, saturation = colorsys.rgb_to_hls(self.red, self.green, self.blue)
            channels = f"{decimal(hue * 360)}, {decimal(saturation * 100)}%, {decimal(light * 100)}%"
            return f"hsla({channels}, {decimal(self.alpha)})" if include_alpha else f"hsl({channels})"
        if form in ("swift", "swiftui"):
            channels = f"red: {decimal(self.red)}, green: {decimal(self.green)}, blue: {decimal(self.blue)}"
            opacity = f", opacity: {decimal(self.alpha)}" if include_alpha else ""
            return f"Color({channels}{opacity})"
        prefix = "" if form == "bare" else "#"
        return f"{prefix}{red:02X}{green:02X}{blue:02X}" + (f"{alpha:02X}" if include_alpha else "")


def color_text(rgb, form):
    return Color(*(channel / 255 for channel in rgb.to_bytes(3, "big"))).text(form)


NUMBER = r"[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)"
TARGETS = {"hex", "rgb", "rgba", "hsl", "hsla", "swift", "swiftui"}
CONNECTORS = {"to", "as", "in", "into", "till", "som", "en", "a", "à", "em", "para", "pra",
              "nach", "zu", "su", "->", ">", "→"}


def channel(token, maximum, *, percent=True):
    scale = maximum
    if percent and token.endswith("%"):
        token, scale = token[:-1], 100
    if not re.fullmatch(NUMBER, token) or not 0 <= (value := float(token)) <= scale:
        raise ValueError
    return value / scale


def css_color(name, body):
    if "," in body:
        parts = [part.strip() for part in body.split(",")]
        if len(parts) != (4 if name.endswith("a") else 3):
            return None
        components = parts[:3]
        alpha = channel(parts[3], 1) if len(parts) == 4 else 1
    else:
        channels, slash, opacity = body.partition("/")
        components = channels.split()
        if len(components) != 3:
            return None
        alpha = channel(opacity.strip(), 1) if slash else 1
    if name.startswith("rgb"):
        return Color(*(channel(component, 255) for component in components), alpha)
    angle, saturation, lightness = components
    match = re.fullmatch(f"({NUMBER})(deg|rad|turn|grad)?", angle)
    if not match or not saturation.endswith("%") or not lightness.endswith("%"):
        return None
    period = {None: 360, "deg": 360, "rad": math.tau, "turn": 1, "grad": 400}[match[2]]
    hue = (float(match[1]) % period) / period
    return Color(*colorsys.hls_to_rgb(hue, channel(lightness, 100), channel(saturation, 100)), alpha)


def parse_color(value):
    if len(value) > 160:
        return None
    value = value.strip().lower()
    if re.fullmatch(r"#(?:[0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})", value):
        digits = value[1:]
        if len(digits) <= 4:
            digits = "".join(c * 2 for c in digits)
        return Color(*(channel / 255 for channel in bytes.fromhex(digits)))
    function = re.fullmatch(r"(rgba?|hsla?|color)\(([^()]*)\)", value)
    if not function:
        return None
    name, body = function.groups()
    try:
        if name != "color":
            return css_color(name, body)
        fields = [field.partition(":") for field in body.split(",")]
        labels = [label.strip() for label, _, _ in fields]
        if labels not in (["red", "green", "blue"], ["red", "green", "blue", "opacity"]):
            return None
        return Color(*(channel(value.strip(), 1, percent=False) for _, _, value in fields))
    except ValueError:
        return None


def conversion(query):
    if len(query) > 160:
        return None
    parts = query.lower().rsplit(None, 2)
    if len(parts) != 3 or parts[1] not in CONNECTORS or parts[2] not in TARGETS:
        return None
    color = parse_color(parts[0])
    if color is not None:
        return color, color.text(parts[2])
    return None
