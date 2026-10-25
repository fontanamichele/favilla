"""Device discovery: group hidraw nodes by physical device and pick a driver.

Adding a device family means writing a Device subclass (see base.py) and
teaching discover() and open_device() about it. See docs/adding-a-device.md.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .. import hid
from . import apex, rival
from .base import Device, Led

STEELSERIES_VENDOR_ID = 0x1038


@dataclass(frozen=True)
class Candidate:
    """A connected SteelSeries device, before it is opened."""

    key: str                       # "1038:1624@1-9": stable while it stays plugged in
    vendor_id: int
    product_id: int
    port: str
    nodes: tuple[hid.HidNode, ...]
    driver: str | None             # "apex", "rival" or None if unsupported
    name: str


def discover(nodes: list[hid.HidNode] | None = None) -> list[Candidate]:
    if nodes is None:
        nodes = hid.enumerate_nodes(STEELSERIES_VENDOR_ID)
    groups: dict[tuple[int, int, str], list[hid.HidNode]] = defaultdict(list)
    for node in nodes:
        groups[(node.vendor_id, node.product_id, node.port)].append(node)

    candidates = []
    for (vid, pid, port), group in sorted(groups.items()):
        key = f"{vid:04x}:{pid:04x}@{port}"
        if vid == STEELSERIES_VENDOR_ID and pid in apex.MODELS:
            driver, name = "apex", apex.MODELS[pid][0]
        elif (profile := rival.profile_for(vid, pid)) is not None:
            driver, name = "rival", rival.display_name(profile["name"])
        else:
            driver, name = None, f"SteelSeries device {vid:04x}:{pid:04x}"
        candidates.append(Candidate(key, vid, pid, port, tuple(group), driver, name))
    return candidates


def open_device(candidate: Candidate, desk: dict) -> Device:
    nodes = list(candidate.nodes)
    if candidate.driver == "apex":
        return apex.ApexProMini(nodes, desk["keyboard_layout"])
    if candidate.driver == "rival":
        return rival.RivalMouse(nodes, rival.profile_for(candidate.vendor_id, candidate.product_id))
    raise ValueError(f"{candidate.name} is not supported yet")


__all__ = ["Candidate", "Device", "Led", "discover", "open_device", "STEELSERIES_VENDOR_ID"]
