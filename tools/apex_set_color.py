#!/usr/bin/env python3
"""Paint a whole Apex Pro Mini with one color, without the daemon.

Handy to test the lighting protocol. Stop favillad first, or it will repaint
the keyboard a moment later:

    systemctl --user stop favilla
    PYTHONPATH=src tools/apex_set_color.py ff4400
    PYTHONPATH=src tools/apex_set_color.py 00ff00 --command 0x21
"""

import argparse
import os
import sys

from favilla import hid, layout
from favilla.devices import apex, discover
from favilla.lighting import parse_color


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("color", help="e.g. ff4400")
    parser.add_argument("--command", type=lambda v: int(v, 0),
                        help="lighting command byte (default: the one known for the model)")
    args = parser.parse_args()

    keyboard = next((c for c in discover() if c.driver == "apex"), None)
    if keyboard is None:
        print("No Apex Pro Mini found", file=sys.stderr)
        return 1
    _, interface, command, _, _ = apex.MODELS[keyboard.product_id]
    node = next(n for n in keyboard.nodes if n.interface == interface)
    color = parse_color(args.color)
    leds = sorted({key.led for key, _ in layout.keys_for(layout.DEFAULT_LAYOUT)})
    size = 1 + hid.report_lengths(node.descriptor).get(("feature", 0), apex.DEFAULT_PACKET_SIZE - 1)
    packet = apex.build_color_packet(args.command or command, [(led, color) for led in leds], size)
    fd = os.open(node.path, os.O_RDWR)
    try:
        hid.send_feature_report(fd, packet)
    finally:
        os.close(fd)
    print(f"Sent {len(leds)} keys, command 0x{args.command or command:02x}, to {node.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
