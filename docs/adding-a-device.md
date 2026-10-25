# Adding a device

## Mice supported by rivalcfg

Mice in [rivalcfg](https://github.com/flozz/rivalcfg) are found automatically:
`favillactl status` lists them. What needs checking on real hardware:

- the LED zones light up and animate (zones are the `rgbcolor` settings of the
  rivalcfg profile; their position on the mouse is in `ZONE_POSITIONS` in
  `src/favilla/devices/rival.py`);
- clicks start the reactive effect;
- settings applied from the app stick after unplugging the mouse.

Please report the result, working or not, with the model and `favillactl status`.

## A new kind of device

1. **Find its interfaces.** With the device plugged in:

   ```bash
   PYTHONPATH=src python3 -c "
   from favilla import hid
   for n in hid.enumerate_nodes(0x1038):
       print(n.path, hex(n.product_id), n.interface, n.usage, hid.report_lengths(n.descriptor))"
   ```

   Vendor-defined usage pages (`0xFFxx`) are where commands go. A large feature
   report usually carries lighting.

2. **Learn the protocol.** Look for it in OpenRGB, the SignalRGB plugins or
   rivalcfg first. If nobody has it, capture it: see
   [reverse-engineering.md](reverse-engineering.md).

3. **Write a driver.** Subclass `Device` from `src/favilla/devices/base.py`:

   | Method | Purpose |
   |---|---|
   | `leds()` | LED ids and positions, in key units, device coordinates |
   | `show(colors)` | display one frame (not saved) |
   | `input_fds()` / `read_input(fd)` | report presses, so reactive effects work |
   | `persist_colors(colors)` | save resting colors, if the device keeps them |
   | `settings_schema()` / `apply_settings(values)` | settings the app can edit |
   | `poll()` / `status()` | battery and other periodic information |

   Keep protocol facts in a small table at the top of the module, like `MODELS`
   in `apex.py`, and add a page to `docs/protocols/`.

4. **Register it** in `discover()` and `open_device()` in
   `src/favilla/devices/__init__.py`, and decide where it sits on the desk in
   `Daemon._offset()`.

5. **Test it.** Add unit tests for packet building and report parsing (see
   `tests/test_keyboard.py`) and try it on the device.
