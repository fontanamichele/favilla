# Aerox 5 Wireless: what is known

The protocol is described by [rivalcfg](https://github.com/flozz/rivalcfg)
(`rivalcfg/devices/aerox5_wireless_*.py`); Favilla reuses those descriptions.
This page records what matters for Favilla, including what was found while
animating the LEDs.

## USB identities

| Product ID | Mode |
|---|---|
| `1038:1852` | 2.4 GHz dongle (tested) |
| `1038:1854` | USB cable |

## Interfaces of the dongle

| Interface | Use |
|---|---|
| 0 | mouse reports: byte 0 is the button bitmap (no report ID), used for clicks |
| 3 | vendor page `0xFFC0`: commands (64 byte output reports) and replies (64 byte input reports) |

## Commands

Output reports on interface 3: `[0x00 report ID, command, arguments...]`. In
2.4 GHz mode the command byte has bit `0x40` set compared with the cable.

| Command (dongle) | Arguments | Meaning |
|---|---|---|
| `0x61 0x01 zone` | `r g b` | color of a LED zone: 0 top, 1 middle, 2 bottom |
| `0x66` | `0x01 0x00 r g b`, or five zeros for off | flash color on click (done by the mouse itself) |
| `0x6d` | DPI presets | see rivalcfg's `multidpi_range_choice` |
| `0x6b` | polling rate choice | |
| `0x69` | 3 byte little endian ms | sleep timer |
| `0x63 0x0f 0x01 0x00 0x00` | 3 byte little endian ms | dim timer |
| `0x51 0x00` | | save the current settings to the mouse memory |
| `0xd2` | | battery: reply byte 1 = `(level / 5) + 1`, bit 7 = charging |

## One command at a time

In 2.4 GHz mode **every command gets a reply**: an input report on interface 3
whose first byte echoes the command (`61 ...`, `d2 0b ...`). It arrives about
8 ms later. A command sent before the reply arrives **is dropped**.

Sending the three zone colors back to back, as a naive animation would, leaves
some zones with old colors. Favilla's mouse writer sends one command, waits for
the reply with the matching first byte (up to 100 ms), then sends the next.
With three zones this allows about 40 frames per second; Favilla uses 30.

If the mouse sleeps, no reply comes: after three attempts the writer gives up
on that color instead of retrying forever, so it does not keep the mouse awake.

## Saving

Zone colors sent without `0x51` are temporary: Favilla animates with them and
only saves the resting colors, once, after the user stops changing them.
