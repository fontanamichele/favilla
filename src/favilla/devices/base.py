"""The interface every device driver implements."""

from __future__ import annotations

import os
from dataclasses import dataclass

from ..hid import HidNode
from ..lighting import Color

Rect = tuple[float, float, float, float]


@dataclass(frozen=True)
class Led:
    id: str                  # stable within the device, e.g. "k41" or "z0"
    x: float                 # center, device coordinates in key units
    y: float
    label: str = ""
    rects: tuple[Rect, ...] = ()   # drawing geometry, device coordinates
    visible: bool = True           # False: lit, but not part of the chosen layout
    outline: str = ""              # SVG path replacing the rects when drawing (ISO Enter)


class Device:
    """A connected device. All methods are called from the daemon main thread."""

    kind = "device"            # "keyboard" or "mouse"
    model = "unknown"          # model family; profiles store settings under this key
    name = "Unknown device"
    connection = "wired"       # or "wireless"
    max_fps = 60
    keepalive: float | None = None  # resend the frame every N s when idle (wake from sleep)
    body: Rect | None = None   # outline for drawing, device coordinates

    def __init__(self, nodes: list[HidNode]):
        self.nodes = nodes
        self.vendor_id = nodes[0].vendor_id
        self.product_id = nodes[0].product_id
        self.port = nodes[0].port
        self._fds: list[int] = []

    @property
    def id(self) -> str:
        return f"{self.model}@{self.port}"

    def leds(self) -> list[Led]:
        return []

    def input_fds(self) -> list[int]:
        """File descriptors to watch for key presses or clicks."""
        return []

    def read_input(self, fd: int) -> list[tuple[float, float]]:
        """Read pending input and return where presses happened (device coordinates)."""
        return []

    def show(self, colors: dict[str, Color]) -> None:
        """Display one animation frame. Not saved to the device memory."""

    def persist_colors(self, colors: dict[str, Color]) -> None:
        """Save colors to the device memory, shown when Favilla is not running."""

    def settings_schema(self) -> list[dict]:
        return []

    def apply_settings(self, values: dict) -> dict[str, str]:
        """Apply and save settings; return {setting: error} for the rejected ones."""
        return {name: "not supported" for name in values}

    def poll(self) -> None:
        """Periodic housekeeping (battery level...)."""

    def status(self) -> dict:
        return {}

    def describe(self) -> dict:
        return {
            "id": self.id, "kind": self.kind, "model": self.model, "name": self.name,
            "connection": self.connection,
            "usb_id": "%04x:%04x" % (self.vendor_id, self.product_id),
            "leds": [{"id": led.id, "x": led.x, "y": led.y, "label": led.label,
                      "rects": [list(r) for r in led.rects], "visible": led.visible,
                      "outline": led.outline}
                     for led in self.leds()],
            "body": list(self.body) if self.body else None,
            "settings": self.settings_schema(),
            "status": self.status(),
        }

    def _open(self, path: str, write: bool = False) -> int:
        fd = os.open(path, (os.O_RDWR if write else os.O_RDONLY) | os.O_NONBLOCK)
        self._fds.append(fd)
        return fd

    def close(self) -> None:
        for fd in self._fds:
            try:
                os.close(fd)
            except OSError:
                pass
        self._fds.clear()
