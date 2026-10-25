"""Lighting engine: one effect that spans every device on the desk.

All devices share a "desk" coordinate space measured in key units: the
keyboard occupies x 0..15, y 0..5 and the mouse sits to its right. An effect is
a background (static, breathing, spectrum, off) plus a reactive layer (ripple,
key fade, none) driven by key presses and mouse clicks.
"""

from __future__ import annotations

import colorsys
import math
from dataclasses import dataclass

Color = tuple[int, int, int]
BLACK: Color = (0, 0, 0)


def parse_color(value) -> Color:
    """Accept "#rrggbb", "rrggbb", "#rgb" or an (r, g, b) sequence."""
    if isinstance(value, (tuple, list)) and len(value) == 3 and all(
            isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in value):
        return tuple(value)
    if isinstance(value, str):
        text = value.strip().lstrip("#")
        if len(text) == 3:
            text = "".join(c * 2 for c in text)
        if len(text) == 6:
            try:
                return tuple(bytes.fromhex(text))
            except ValueError:
                pass
    raise ValueError(f"not a valid color: {value!r}")


def to_hex(color: Color) -> str:
    return "#%02x%02x%02x" % tuple(color)


def mix(a: Color, b: Color, t: float) -> Color:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def scale(color: Color, k: float) -> Color:
    return tuple(int(c * k) for c in color)


# ---- Backgrounds ---------------------------------------------------------------

class Background:
    animated = False

    def color(self, x: float, y: float, now: float) -> Color:
        raise NotImplementedError

    def resting(self, x: float, y: float) -> Color:
        """Color to store in the device memory, shown when nothing drives the LEDs."""
        return self.color(x, y, 0.0)


class Static(Background):
    def __init__(self, color):
        self.base = parse_color(color)

    def color(self, x, y, now):
        return self.base


class Off(Static):
    def __init__(self):
        super().__init__(BLACK)


class Breathing(Background):
    animated = True

    def __init__(self, color, period: float = 4.0):
        self.base = parse_color(color)
        self.period = period

    def color(self, x, y, now):
        level = 0.5 - 0.5 * math.cos(2 * math.pi * now / self.period)
        return scale(self.base, 0.12 + 0.88 * level)

    def resting(self, x, y):
        return self.base


class Spectrum(Background):
    """Rainbow flowing from the keyboard towards the mouse."""
    animated = True

    def __init__(self, speed: float = 0.2, spread: float = 0.03):
        self.speed = speed    # color cycles per second
        self.spread = spread  # hue shift per key unit

    def color(self, x, y, now):
        r, g, b = colorsys.hsv_to_rgb((x * self.spread - now * self.speed) % 1.0, 1.0, 1.0)
        return int(r * 255), int(g * 255), int(b * 255)


# ---- Reactive layers -----------------------------------------------------------

@dataclass(frozen=True)
class Press:
    x: float
    y: float
    time: float
    origin: str  # id of the device that was pressed


class Reactive:
    lifetime = 0.0

    def __init__(self, color=BLACK):
        self.color = parse_color(color)
        self.presses: list[Press] = []

    def press(self, x: float, y: float, origin: str, now: float) -> None:
        self.presses.append(Press(x, y, now, origin))

    def active(self, now: float) -> bool:
        self.presses = [p for p in self.presses if now - p.time < self.lifetime]
        return bool(self.presses)

    def glow(self, x: float, y: float, device: str, now: float) -> float:
        """How much of the reactive color to show at (x, y), from 0 to 1."""
        return 0.0


class NoReactive(Reactive):
    def press(self, x, y, origin, now):
        pass


class Ripple(Reactive):
    """A ring that expands from the pressed key (or the clicked mouse).

    It fades faster on the device where it starts (life) than on the other
    devices it reaches (life_cross), otherwise it would vanish before arriving.
    """

    def __init__(self, color, speed=14.0, width=1.1, life=0.9, life_cross=1.8):
        super().__init__(color)
        self.speed, self.width = speed, width
        self.life, self.life_cross = life, life_cross
        self.lifetime = max(life, life_cross)

    def glow(self, x, y, device, now):
        glow = 0.0
        for p in self.presses:
            age = now - p.time
            life = self.life if p.origin == device else self.life_cross
            if age >= life or age < 0:
                continue
            d = math.hypot(x - p.x, y - p.y)
            ring = math.exp(-((d - age * self.speed) / self.width) ** 2)
            center = math.exp(-(d / 0.6) ** 2) * max(0.0, 1 - age / 0.25)
            glow = max(glow, max(ring, center) * (1 - age / life) ** 1.5)
        return min(glow, 1.0)


class KeyFade(Reactive):
    """Only the pressed key lights up, then slowly fades out."""

    def __init__(self, color, life=1.2, radius=0.6):
        super().__init__(color)
        self.life, self.radius = life, radius
        self.lifetime = life

    def glow(self, x, y, device, now):
        glow = 0.0
        for p in self.presses:
            age = now - p.time
            if p.origin != device or not 0 <= age < self.life:
                continue
            d = math.hypot(x - p.x, y - p.y)
            glow = max(glow, math.exp(-(d / self.radius) ** 2) * (1 - age / self.life) ** 1.5)
        return min(glow, 1.0)


BACKGROUNDS = ("static", "breathing", "spectrum", "off")
REACTIVES = ("ripple", "keyfade", "none")


def build_background(settings: dict) -> Background:
    effect = settings["effect"]
    if effect == "static":
        return Static(settings["color"])
    if effect == "breathing":
        return Breathing(settings["color"], settings["period"])
    if effect == "spectrum":
        return Spectrum(settings["speed"], settings["spread"])
    if effect == "off":
        return Off()
    raise ValueError(f"unknown background effect: {effect!r}")


def build_reactive(settings: dict) -> Reactive:
    effect = settings["effect"]
    if effect == "ripple":
        return Ripple(settings["color"], settings["speed"], settings["width"],
                      settings["life"], settings["life_cross"])
    if effect == "keyfade":
        return KeyFade(settings["color"], settings["life"])
    if effect == "none":
        return NoReactive()
    raise ValueError(f"unknown reactive effect: {effect!r}")


class LightingEngine:
    def __init__(self, settings: dict):
        self.background = build_background(settings["background"])
        self.reactive = build_reactive(settings["reactive"])
        self.brightness = settings.get("brightness", 1.0)

    def press(self, x: float, y: float, origin: str, now: float) -> None:
        self.reactive.press(x, y, origin, now)

    def animated(self, now: float) -> bool:
        return self.background.animated or self.reactive.active(now)

    def _finish(self, color: Color) -> Color:
        return color if self.brightness >= 1.0 else scale(color, self.brightness)

    def frame(self, device: str, leds, now: float) -> dict[str, Color]:
        """Colors for the LEDs of one device; leds = [(led_id, desk_x, desk_y), ...]."""
        reacting = bool(self.reactive.presses)
        colors = {}
        for led_id, x, y in leds:
            color = self.background.color(x, y, now)
            if reacting:
                glow = self.reactive.glow(x, y, device, now)
                if glow > 0:
                    color = mix(color, self.reactive.color, glow)
            colors[led_id] = self._finish(color)
        return colors

    def resting(self, leds) -> dict[str, Color]:
        return {led_id: self._finish(self.background.resting(x, y)) for led_id, x, y in leds}
