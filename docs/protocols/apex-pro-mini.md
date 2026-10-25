# Apex Pro Mini: what is known

## USB identities

| Product ID | What | Notes |
|---|---|---|
| `1038:1624` | Apex Pro Mini Wireless, 2.4 GHz dongle | tested |
| `1038:1626` | Apex Pro Mini Wireless, USB cable | from the SignalRGB plugin, untested |
| `1038:161e` | Apex Pro Mini (wired model) | from the SignalRGB plugin, untested |

## Interfaces of the dongle (`1038:1624`)

| Interface | Report descriptor | Use |
|---|---|---|
| 0 | mouse | unused |
| 1 | boot keyboard, 8 byte reports | key presses |
| 2 | consumer control | media keys |
| 3 | vendor page `0xFFC0`: 64 byte input and output, **641 byte feature report** | lighting |
| 4 | vendor page `0xFFC1`: 64 byte input | unknown |
| 5 | NKRO keyboard, 256 bit bitmap (32 bytes) | key presses |

## Per-key lighting

One feature report (`HIDIOCSFEATURE`) of 642 bytes on the lighting interface:

```
byte 0      report ID, always 0
byte 1      command: 0x61 dongle, 0x21 cable (1626), 0x40 wired model (161e, interface 1)
byte 2      number of entries
byte 3...   entries of 4 bytes: LED code, red, green, blue
            zero padded to 642 bytes
```

`0x61` is `0x21` with bit `0x40` set: the same "forward to the keyboard over
the radio" flag the Aerox mice use.

The LED codes are the HID usages of the keys, with two exceptions on the
bottom row: the **Fn** key is LED `231` (the usage of Right GUI, which this
keyboard does not have) and the **menu** key is LED `240`. Codes of keys the
keyboard does not have are accepted and ignored, so Favilla always sends both
the ANSI and the ISO keys.

The colors are not saved: after sleep the keyboard shows its own default until
it receives a packet again. Favilla resends the frame every 5 s when idle.

Sending frames at 60 fps works; the dongle accepted about 500 packets per
second in a quick test.

## Still unknown

Everything SteelSeries GG configures besides lighting: actuation point,
Rapid Trigger, key remapping, Fn layer, onboard profiles, battery level. See
[reverse-engineering.md](../reverse-engineering.md) for how to capture it.

## Sources

- SignalRGB plugin `Steelseries_Apex_Pro_Mini_Keyboard.js` (product IDs, packet
  layout, key codes).
- Tests on a real Apex Pro Mini Wireless with its dongle (command `0x61`,
  interfaces, report sizes).
