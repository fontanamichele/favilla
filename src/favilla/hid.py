"""Minimal hidraw helpers: device enumeration, report descriptor parsing and I/O.

Only the standard library is used: sysfs for discovery, ioctl() for feature
reports and plain read()/write() for input and output reports.
"""

from __future__ import annotations

import fcntl
import glob
import os
import re
from dataclasses import dataclass, field

BUS_USB = 0x03

USAGE_PAGE_GENERIC_DESKTOP = 0x01
USAGE_MOUSE = 0x02
USAGE_KEYBOARD = 0x06

READ_SIZE = 1024  # larger than any report we care about


@dataclass(frozen=True)
class HidNode:
    """One hidraw node, i.e. one HID interface of a USB device."""

    path: str            # /dev/hidrawN
    vendor_id: int
    product_id: int
    interface: int       # USB interface number
    port: str            # USB port path (e.g. "1-9"): groups the interfaces of one device
    descriptor: bytes = field(repr=False, default=b"")

    @property
    def usage(self) -> tuple[int, int]:
        """(usage page, usage) of the first top-level collection."""
        return top_level_usage(self.descriptor)

    @property
    def is_keyboard(self) -> bool:
        return self.usage == (USAGE_PAGE_GENERIC_DESKTOP, USAGE_KEYBOARD)

    @property
    def is_mouse(self) -> bool:
        return self.usage == (USAGE_PAGE_GENERIC_DESKTOP, USAGE_MOUSE)


def _hidraw_number(path: str) -> int:
    match = re.search(r"(\d+)$", path)
    return int(match.group(1)) if match else 0


def enumerate_nodes(vendor_id: int | None = None, sysfs: str = "/sys/class/hidraw") -> list[HidNode]:
    """List the USB hidraw nodes, optionally only those of one vendor."""
    nodes = []
    for entry in sorted(glob.glob(os.path.join(sysfs, "hidraw*")), key=_hidraw_number):
        device = os.path.realpath(os.path.join(entry, "device"))
        # .../usb1/1-9/1-9:1.3/0003:1038:1624.0007
        parts = os.path.basename(device).split(":")
        if len(parts) != 3:
            continue
        try:
            bus, vid = int(parts[0], 16), int(parts[1], 16)
            pid = int(parts[2].split(".")[0], 16)
        except ValueError:
            continue
        if bus != BUS_USB or (vendor_id is not None and vid != vendor_id):
            continue
        port, _, config_interface = os.path.basename(os.path.dirname(device)).partition(":")
        try:
            interface = int(config_interface.split(".")[1])
        except (IndexError, ValueError):
            continue
        try:
            with open(os.path.join(device, "report_descriptor"), "rb") as f:
                descriptor = f.read()
        except OSError:
            descriptor = b""
        nodes.append(HidNode("/dev/" + os.path.basename(entry), vid, pid, interface, port, descriptor))
    return nodes


# ---- Report descriptor parsing ------------------------------------------------

_MAIN_INPUT, _MAIN_OUTPUT, _MAIN_FEATURE, _MAIN_COLLECTION = 0x80, 0x90, 0xB0, 0xA0
_GLOBAL_USAGE_PAGE, _GLOBAL_REPORT_SIZE = 0x04, 0x74
_GLOBAL_REPORT_ID, _GLOBAL_REPORT_COUNT = 0x84, 0x94
_LOCAL_USAGE = 0x08
_REPORT_KINDS = {_MAIN_INPUT: "input", _MAIN_OUTPUT: "output", _MAIN_FEATURE: "feature"}


def _items(descriptor: bytes):
    """Yield (tag, value) for each short item of a HID report descriptor."""
    i = 0
    while i < len(descriptor):
        prefix = descriptor[i]
        if prefix == 0xFE:  # long item, never used by these devices: skip it
            if i + 1 >= len(descriptor):
                return
            i += 3 + descriptor[i + 1]
            continue
        size = (0, 1, 2, 4)[prefix & 0x03]
        yield prefix & 0xFC, int.from_bytes(descriptor[i + 1:i + 1 + size], "little")
        i += 1 + size


def report_lengths(descriptor: bytes) -> dict[tuple[str, int], int]:
    """Length in bytes (report ID excluded) of each report, keyed by (kind, report_id)."""
    bits: dict[tuple[str, int], int] = {}
    size = count = report_id = 0
    for tag, value in _items(descriptor):
        if tag == _GLOBAL_REPORT_SIZE:
            size = value
        elif tag == _GLOBAL_REPORT_COUNT:
            count = value
        elif tag == _GLOBAL_REPORT_ID:
            report_id = value
        elif tag in _REPORT_KINDS:
            key = (_REPORT_KINDS[tag], report_id)
            bits[key] = bits.get(key, 0) + size * count
    return {key: (value + 7) // 8 for key, value in bits.items()}


def uses_report_ids(descriptor: bytes) -> bool:
    return any(tag == _GLOBAL_REPORT_ID for tag, _ in _items(descriptor))


def top_level_usage(descriptor: bytes) -> tuple[int, int]:
    page = usage = None
    for tag, value in _items(descriptor):
        if tag == _GLOBAL_USAGE_PAGE:
            page = value
        elif tag == _LOCAL_USAGE and usage is None:
            usage = value
        elif tag == _MAIN_COLLECTION:
            break
    return page or 0, usage or 0


# ---- I/O ---------------------------------------------------------------------

def _ioc_readwrite(number: int, size: int) -> int:
    return (3 << 30) | (size << 16) | (ord("H") << 8) | number


def send_feature_report(fd: int, data: bytes) -> None:
    """Send a feature report; data[0] is the report ID (0 if the device uses none)."""
    fcntl.ioctl(fd, _ioc_readwrite(0x06, len(data)), bytearray(data))


def open_node(path: str, write: bool = False) -> int:
    return os.open(path, (os.O_RDWR if write else os.O_RDONLY) | os.O_NONBLOCK)


def read_reports(fd: int) -> list[bytes]:
    """Read every input report that is currently queued (non-blocking fd)."""
    reports = []
    while True:
        try:
            data = os.read(fd, READ_SIZE)
        except BlockingIOError:
            return reports
        if not data:
            return reports
        reports.append(data)
