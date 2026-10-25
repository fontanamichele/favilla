# Architecture

```
 ┌──────────────┐  ┌──────────────┐
 │ favilla (Qt) │  │  favillactl  │        clients
 └──────┬───────┘  └──────┬───────┘
        │   D-Bus (session bus, JSON payloads)
 ┌──────┴─────────────────┴───────┐
 │            favillad            │        user service
 │  config ─ lighting engine ─ devices
 └──────┬─────────────────┬───────┘
        │ hidraw          │ hidraw
   Apex Pro Mini     Aerox 5 Wireless       (via their USB dongles)
```

## Source map

| Path | What it does |
|---|---|
| `src/favilla/hid.py` | hidraw discovery through sysfs, report descriptor parsing, feature reports |
| `src/favilla/layout.py` | physical keyboard layouts: LED code, HID usage and geometry of every key |
| `src/favilla/lighting.py` | colors, backgrounds, reactive effects and the engine that renders frames |
| `src/favilla/config.py` | profiles: defaults, validation, storage |
| `src/favilla/devices/` | device drivers (`base.py` is the interface) and discovery |
| `src/favilla/daemon.py` | `favillad`: main loop, device lifecycle, settings and persistence |
| `src/favilla/dbus_service.py` | the D-Bus API, served from its own GLib thread |
| `src/favilla/client.py` | synchronous D-Bus client used by the CLI and the GUI |
| `src/favilla/cli.py` | `favillactl` |
| `src/favilla/gui/` | `favilla`: Qt Quick interface (`backend.py` bridges QML and D-Bus) |

## The daemon

`favillad` runs a single-threaded main loop built on `select()`:

1. every 3 s it looks for plugged and unplugged devices;
2. it waits for input from the keyboard and mouse HID interfaces (key presses
   and clicks are read from the devices' own interfaces, so no access to
   `/dev/input` is needed);
3. it renders a frame for every device: at 60 fps while something is animated,
   otherwise once, plus a keepalive every 5 s for keyboards that forget their
   colors when they wake up;
4. it runs the D-Bus calls queued by the D-Bus thread.

Devices are only touched from the main thread. The exception is each mouse's
writer thread: wireless mice accept one command at a time and must reply
before the next (see [the Aerox notes](protocols/aerox-5-wireless.md)), so
waiting for replies happens there, without slowing the keyboard down.

### Desk coordinates

Every LED has a position in a shared desk space measured in keys (1 unit =
19.05 mm). The keyboard spans x 0–15, y 0–5; the mouse center sits at
`(desk.mouse_x, 3)`. Effects only see positions, which is why a wave can
travel from one device to another.

### Writes to device memory

Animation frames are never saved. What is saved:

- the **resting colors** (the background without reactions) of devices that
  keep them, like the mouse, so they look right without Favilla. They are
  written 2 s after the last lighting change, and only if they differ from
  what was saved before;
- the **settings** of a profile, when it becomes active or when the user presses
  Apply, again only when they differ from what Favilla last wrote.

What was written is remembered in `~/.local/state/favilla/state.json`.

## Configuration

`~/.config/favilla/config.json`:

```json
{
  "version": 1,
  "active_profile": "Default",
  "desk": { "keyboard_layout": "iso_it", "mouse_x": 19.0 },
  "profiles": {
    "Default": {
      "lighting": {
        "brightness": 1.0,
        "background": { "effect": "static", "color": "#ff4400", "period": 4.0, "speed": 0.2, "spread": 0.03 },
        "reactive": { "effect": "ripple", "color": "#ffffff", "speed": 14.0, "width": 1.1, "life": 0.9, "life_cross": 1.8 }
      },
      "devices": {
        "aerox_5_wireless": { "sensitivity": [800, 1600, 3200], "polling_rate": "1000" }
      }
    }
  }
}
```

`devices` only holds values the user chose. Anything missing is left as it is
on the device: most devices cannot report their settings, and overwriting them
with defaults would lose what was configured elsewhere.

## D-Bus API

Bus name `io.github.fontanamichele.Favilla`, object
`/io/github/fontanamichele/Favilla`, interface
`io.github.fontanamichele.Favilla1`. Payloads are JSON strings.

| Member | Arguments → result | Notes |
|---|---|---|
| `GetVersion` | → `s` | |
| `GetDevices` | → `s` | connected devices with LEDs, geometry, settings schema and status, plus unsupported ones |
| `GetConfig` | → `s` | the whole configuration |
| `SetConfig` | `s` → | validated, saved and applied; errors come back as D-Bus errors |
| `SetActiveProfile` | `s` → | also applies the profile's device settings |
| `ApplyDeviceSettings` | `s device_id` → `s` | writes every setting of the active profile; returns a list of errors |
| `GetFrame` | → `s` | `{device_id: {led_id: "#rrggbb"}}`, the colors on screen right now |
| `SimulatePress` | `s device_id, s led_id` → | starts the reactive effect from a LED |
| `ConfigChanged` | signal `s` | |
| `DevicesChanged` | signal `s` | |

Try it from a terminal:

```bash
gdbus call --session --dest io.github.fontanamichele.Favilla \
  --object-path /io/github/fontanamichele/Favilla \
  --method io.github.fontanamichele.Favilla1.GetDevices
```
