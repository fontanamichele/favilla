"""SteelSeries Apex Pro Mini keyboards: per-key RGB lighting.

The lighting protocol comes from the SignalRGB plugin for this keyboard and was
verified on the Apex Pro Mini Wireless 2.4 GHz dongle (1038:1624). See
docs/protocols/apex-pro-mini.md.
"""

from __future__ import annotations

from .. import hid, layout as layouts
from ..lighting import Color
from .base import Device, Led

# product id -> (name, lighting interface, lighting command, connection, tested)
MODELS = {
    0x1624: ("Apex Pro Mini Wireless", 3, 0x61, "wireless", True),   # 2.4 GHz dongle
    0x1626: ("Apex Pro Mini Wireless", 3, 0x21, "wired", False),     # same keyboard, USB cable
    0x161E: ("Apex Pro Mini", 1, 0x40, "wired", False),              # wired-only model
}

DEFAULT_PACKET_SIZE = 642  # report ID + 641 bytes feature report


def parse_key_report(report: bytes, previous: set[int]) -> set[int]:
    """Pressed keys (HID usages) from a boot (8 bytes) or NKRO (32 byte bitmap) report."""
    if len(report) == 8:
        modifiers = {0xE0 + i for i in range(8) if report[0] >> i & 1}
        return modifiers | {usage for usage in report[2:] if usage > 3}
    if len(report) >= 32:
        return {i for i in range(256) if report[i // 8] >> (i % 8) & 1}
    return previous


def build_color_packet(command: int, entries: list[tuple[int, Color]], size: int) -> bytes:
    """[report id 0, command, count, (led, r, g, b) * count], zero padded."""
    if 3 + 4 * len(entries) > size:
        raise ValueError("too many LEDs for one packet")
    packet = bytearray(size)
    packet[1], packet[2] = command, len(entries)
    for i, (led, (r, g, b)) in enumerate(entries):
        packet[3 + 4 * i:7 + 4 * i] = bytes((led, r, g, b))
    return bytes(packet)


class ApexProMini(Device):
    kind = "keyboard"
    model = "apex_pro_mini"
    max_fps = 60
    keepalive = 5.0

    def __init__(self, nodes, layout_id: str = layouts.DEFAULT_LAYOUT):
        super().__init__(nodes)
        self.name, interface, self.command, self.connection, self.tested = MODELS[self.product_id]
        light = next((n for n in nodes if n.interface == interface), None)
        if light is None:
            raise OSError(f"{self.name}: lighting interface {interface} not found")
        feature = hid.report_lengths(light.descriptor).get(("feature", 0))
        self.packet_size = 1 + feature if feature else DEFAULT_PACKET_SIZE
        try:
            self._light_fd = self._open(light.path, write=True)
            self._pressed = {self._open(n.path): set()
                             for n in nodes if n.is_keyboard and n.interface != interface}
        except OSError:
            self.close()
            raise
        self.set_layout(layout_id)

    def set_layout(self, layout_id: str) -> None:
        self.layout_id = layout_id
        keys = layouts.keys_for(layout_id)
        self._leds = [Led(f"k{key.led}", *key.center, key.label, key.rects, visible, key.outline)
                      for key, visible in keys]
        self._codes = {f"k{key.led}": key.led for key, _ in keys}
        self._usage_center = {key.usage: key.center for key, _ in keys if key.usage is not None}

    def leds(self):
        return self._leds

    def input_fds(self):
        return list(self._pressed)

    def read_input(self, fd):
        presses = []
        for report in hid.read_reports(fd):
            before = self._pressed[fd]
            now_down = parse_key_report(report, before)
            presses += [self._usage_center[u] for u in sorted(now_down - before)
                        if u in self._usage_center]
            self._pressed[fd] = now_down
        return presses

    def show(self, colors):
        entries = [(self._codes[led_id], color) for led_id, color in colors.items()
                   if led_id in self._codes]
        hid.send_feature_report(self._light_fd,
                                build_color_packet(self.command, entries, self.packet_size))

    def describe(self):
        info = super().describe()
        info.update(layout=self.layout_id, tested=self.tested,
                    layouts=[{"id": l.id, "name": l.name} for l in layouts.LAYOUTS.values()])
        return info
