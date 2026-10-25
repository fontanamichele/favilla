"""Physical keyboard layouts, in key units (1 unit = one 19.05 mm key).

Every key has the LED code used by the lighting protocol, the HID usage the
keyboard reports when it is pressed, a label and one or more rectangles (the
ISO Enter key needs two). Coordinates start at the top-left corner of the
keyboard; y grows downwards.
"""

from __future__ import annotations

from dataclasses import dataclass

Rect = tuple[float, float, float, float]  # x, y, width, height

# LED codes are the HID usages of the keys, except where the firmware reuses a
# code for a key that never reaches the host (Fn) or for the menu key.
_USAGE_OF_LED = {
    231: None,  # Fn: handled by the keyboard itself, never reported
    240: 101,   # Menu key LED -> "Application" usage
}


@dataclass(frozen=True)
class Key:
    led: int
    usage: int | None
    label: str
    rects: tuple[Rect, ...]
    outline: str = ""   # SVG path for drawing keys that are not rectangles (ISO Enter)

    @property
    def center(self) -> tuple[float, float]:
        x0 = min(r[0] for r in self.rects)
        y0 = min(r[1] for r in self.rects)
        x1 = max(r[0] + r[2] for r in self.rects)
        y1 = max(r[1] + r[3] for r in self.rects)
        return (x0 + x1) / 2, (y0 + y1) / 2


@dataclass(frozen=True)
class Layout:
    id: str
    name: str
    keys: tuple[Key, ...]
    width: float = 15.0
    height: float = 5.0


def _row(y: float, specs) -> list[Key]:
    keys, x = [], 0.0
    for spec in specs:
        led, label, width = spec if len(spec) == 3 else (*spec, 1.0)
        keys.append(Key(led, _USAGE_OF_LED.get(led, led), label, ((x, y, width, 1.0),)))
        x += width
    return keys


_DIGITS = [(30 + i, str((i + 1) % 10)) for i in range(10)]          # 1 2 ... 9 0
_QWERTY = [(20, "Q"), (26, "W"), (8, "E"), (21, "R"), (23, "T"),
           (28, "Y"), (24, "U"), (12, "I"), (18, "O"), (19, "P")]
_ASDF = [(4, "A"), (22, "S"), (7, "D"), (9, "F"), (10, "G"),
         (11, "H"), (13, "J"), (14, "K"), (15, "L")]
_ZXCV = [(29, "Z"), (27, "X"), (6, "C"), (25, "V"), (5, "B"), (17, "N"), (16, "M")]


def _bottom_row(right_alt: str) -> list[Key]:
    return _row(4, [(224, "Ctrl", 1.25), (227, "Win", 1.25), (226, "Alt", 1.25),
                    (44, "", 6.25), (230, right_alt, 1.25), (231, "Fn", 1.25),
                    (240, "☰", 1.25), (228, "Ctrl", 1.25)])


# The L-shaped ISO Enter, inset by the same 0.07 gap the GUI leaves around keys.
_ISO_ENTER_OUTLINE = (
    "M 13.74 1.07 L 14.76 1.07 Q 14.93 1.07 14.93 1.24 L 14.93 2.76 Q 14.93 2.93 14.76 2.93 "
    "L 13.99 2.93 Q 13.82 2.93 13.82 2.76 L 13.82 2.01 Q 13.82 1.93 13.74 1.93 "
    "L 13.69 1.93 Q 13.57 1.93 13.57 1.81 L 13.57 1.24 Q 13.57 1.07 13.74 1.07 Z")

ISO_IT = Layout("iso_it", "ISO (Italian)", tuple(
    _row(0, [(41, "Esc"), *_DIGITS, (45, "'"), (46, "ì"), (42, "⌫", 2.0)])
    + _row(1, [(43, "⇥", 1.5), *_QWERTY, (47, "è"), (48, "+")])
    + [Key(40, 40, "⏎", ((13.5, 1.0, 1.5, 1.0), (13.75, 2.0, 1.25, 1.0)), _ISO_ENTER_OUTLINE)]
    + _row(2, [(57, "⇪", 1.75), *_ASDF, (51, "ò"), (52, "à"), (50, "ù")])
    + _row(3, [(225, "⇧", 1.25), (100, "<"), *_ZXCV, (54, ","), (55, "."), (56, "-"),
               (229, "⇧", 2.75)])
    + _bottom_row("AltGr")
))

ANSI_US = Layout("ansi_us", "ANSI (US)", tuple(
    _row(0, [(41, "Esc"), *_DIGITS, (45, "-"), (46, "="), (42, "⌫", 2.0)])
    + _row(1, [(43, "⇥", 1.5), *_QWERTY, (47, "["), (48, "]"), (49, "\\", 1.5)])
    + _row(2, [(57, "⇪", 1.75), *_ASDF, (51, ";"), (52, "'"), (40, "⏎", 2.25)])
    + _row(3, [(225, "⇧", 2.25), *_ZXCV, (54, ","), (55, "."), (56, "/"), (229, "⇧", 2.75)])
    + _bottom_row("Alt")
))

LAYOUTS = {layout.id: layout for layout in (ISO_IT, ANSI_US)}
DEFAULT_LAYOUT = ISO_IT.id


def keys_for(layout_id: str) -> list[tuple[Key, bool]]:
    """Every key known to any layout, with a flag telling whether it is part of
    the chosen one. Keys of the other layouts are kept (with their own position)
    so that they are still lit if the physical keyboard differs from the setting."""
    chosen = LAYOUTS.get(layout_id, LAYOUTS[DEFAULT_LAYOUT])
    result = [(key, True) for key in chosen.keys]
    seen = {key.led for key in chosen.keys}
    for layout in LAYOUTS.values():
        for key in layout.keys:
            if key.led not in seen:
                result.append((key, False))
                seen.add(key.led)
    return result
