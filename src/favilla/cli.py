"""favillactl: command line access to the Favilla daemon."""

from __future__ import annotations

import argparse
import json
import sys

from .lighting import BACKGROUNDS, REACTIVES, parse_color, to_hex


def _active(config: dict) -> dict:
    return config["profiles"][config["active_profile"]]


def _set_lighting(client, change) -> None:
    config = client.config()
    change(_active(config)["lighting"])
    client.set_config(config)


def cmd_status(client, args):
    config = client.config()
    print(f"Profile: {config['active_profile']}")
    devices = client.devices()
    if not devices:
        print("No SteelSeries device found.")
    for device in devices:
        details = []
        if device.get("state") == "connected":
            details += [device["kind"], device["connection"]]
            battery = device.get("status", {}).get("battery")
            if battery:
                details.append(f"battery {battery['level']}%" + (" (charging)" if battery.get("charging") else ""))
            marker = "●"
        else:
            details.append(device.get("message") or device["state"].replace("_", " "))
            marker = "○"
        print(f"{marker} {device['name']:<26} {'  '.join(details)}")


def cmd_profiles(client, args):
    config = client.config()
    for name in config["profiles"]:
        print(("* " if name == config["active_profile"] else "  ") + name)


def cmd_use(client, args):
    client.set_active_profile(args.name)


def cmd_color(client, args):
    color = to_hex(parse_color(args.color))

    def change(lighting):
        if lighting["background"]["effect"] in ("off", "spectrum"):
            lighting["background"]["effect"] = "static"
        lighting["background"]["color"] = color
    _set_lighting(client, change)


def cmd_effect(client, args):
    _set_lighting(client, lambda lighting: lighting["background"].update(effect=args.effect))


def cmd_reactive(client, args):
    def change(lighting):
        lighting["reactive"]["effect"] = args.effect
        if args.color:
            lighting["reactive"]["color"] = to_hex(parse_color(args.color))
    _set_lighting(client, change)


def cmd_brightness(client, args):
    _set_lighting(client, lambda lighting: lighting.update(brightness=args.percent / 100))


def cmd_config(client, args):
    print(json.dumps(client.config(), indent=2, ensure_ascii=False))


def cmd_press(client, args):
    client.simulate_press(args.device, args.led)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="favillactl", description="Control the Favilla daemon.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    commands.add_parser("status", help="connected devices and active profile").set_defaults(run=cmd_status)
    commands.add_parser("profiles", help="list the profiles").set_defaults(run=cmd_profiles)
    use = commands.add_parser("use", help="switch to another profile")
    use.add_argument("name")
    use.set_defaults(run=cmd_use)
    color = commands.add_parser("color", help="background color of the active profile, e.g. '#ff4400'")
    color.add_argument("color")
    color.set_defaults(run=cmd_color)
    effect = commands.add_parser("effect", help="background effect")
    effect.add_argument("effect", choices=BACKGROUNDS)
    effect.set_defaults(run=cmd_effect)
    reactive = commands.add_parser("reactive", help="effect on key presses and clicks")
    reactive.add_argument("effect", choices=REACTIVES)
    reactive.add_argument("--color", help="color of the effect")
    reactive.set_defaults(run=cmd_reactive)
    brightness = commands.add_parser("brightness", help="overall brightness, 0-100")
    brightness.add_argument("percent", type=int, choices=range(0, 101), metavar="0-100")
    brightness.set_defaults(run=cmd_brightness)
    commands.add_parser("config", help="print the configuration as JSON").set_defaults(run=cmd_config)
    press = commands.add_parser("press", help="simulate a key press to preview the effect")
    press.add_argument("device", help="device id, see the GetDevices output")
    press.add_argument("led", help="LED id, e.g. k41 for Esc")
    press.set_defaults(run=cmd_press)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    from .client import Client, DaemonError

    try:
        args.run(Client(), args)
    except (DaemonError, ValueError) as error:
        print(f"favillactl: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
