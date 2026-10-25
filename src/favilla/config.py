"""User configuration: profiles with lighting and device settings.

Stored as JSON in $XDG_CONFIG_HOME/favilla/config.json. The device settings of
a profile only contain the values the user explicitly chose: anything missing
is left as it is on the device, because most devices cannot report their
current settings and overwriting them with defaults would lose what the user
configured elsewhere (for example in SteelSeries GG on Windows).
"""

from __future__ import annotations

import copy
import json
import logging
import os
import tempfile

from .layout import LAYOUTS
from .lighting import BACKGROUNDS, REACTIVES, parse_color, to_hex

log = logging.getLogger(__name__)

CONFIG_VERSION = 1
MAX_PROFILES = 32
MAX_PROFILE_NAME = 40

DEFAULT_LIGHTING = {
    "brightness": 1.0,
    "background": {"effect": "static", "color": "#ff4400", "period": 4.0, "speed": 0.2, "spread": 0.03},
    "reactive": {"effect": "ripple", "color": "#ffffff", "speed": 14.0, "width": 1.1,
                 "life": 0.9, "life_cross": 1.8},
}
DEFAULT_DESK = {"keyboard_layout": "iso_it", "mouse_x": 19.0}

# (section, key) -> (min, max)
_LIMITS = {
    ("lighting", "brightness"): (0.0, 1.0),
    ("background", "period"): (0.5, 30.0),
    ("background", "speed"): (0.01, 5.0),
    ("background", "spread"): (0.0, 1.0),
    ("reactive", "speed"): (1.0, 60.0),
    ("reactive", "width"): (0.2, 6.0),
    ("reactive", "life"): (0.1, 5.0),
    ("reactive", "life_cross"): (0.1, 8.0),
    ("desk", "mouse_x"): (15.5, 40.0),
}


class ConfigError(ValueError):
    pass


def default_profile() -> dict:
    return {"lighting": copy.deepcopy(DEFAULT_LIGHTING), "devices": {}}


def default_config() -> dict:
    return {"version": CONFIG_VERSION, "active_profile": "Default",
            "desk": dict(DEFAULT_DESK), "profiles": {"Default": default_profile()}}


def active_profile(config: dict) -> dict:
    return config["profiles"][config["active_profile"]]


def _number(section: str, key: str, value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{section}.{key} must be a number")
    low, high = _LIMITS[(section, key)]
    if not low <= value <= high:
        raise ConfigError(f"{section}.{key} must be between {low} and {high}")
    return float(value)


def _color(where: str, value) -> str:
    try:
        return to_hex(parse_color(value))
    except ValueError:
        raise ConfigError(f"{where} is not a valid color: {value!r}") from None


def _merge(defaults: dict, given) -> dict:
    if given is None:
        return copy.deepcopy(defaults)
    if not isinstance(given, dict):
        raise ConfigError("expected an object")
    return {**copy.deepcopy(defaults), **given}


def _normalize_lighting(given) -> dict:
    lighting = _merge(DEFAULT_LIGHTING, given)
    background = _merge(DEFAULT_LIGHTING["background"], lighting["background"])
    reactive = _merge(DEFAULT_LIGHTING["reactive"], lighting["reactive"])
    if background["effect"] not in BACKGROUNDS:
        raise ConfigError(f"unknown background effect {background['effect']!r}")
    if reactive["effect"] not in REACTIVES:
        raise ConfigError(f"unknown reactive effect {reactive['effect']!r}")
    background["color"] = _color("background color", background["color"])
    reactive["color"] = _color("reactive color", reactive["color"])
    for key in ("period", "speed", "spread"):
        background[key] = _number("background", key, background[key])
    for key in ("speed", "width", "life", "life_cross"):
        reactive[key] = _number("reactive", key, reactive[key])
    return {"brightness": _number("lighting", "brightness", lighting["brightness"]),
            "background": {k: background[k] for k in DEFAULT_LIGHTING["background"]},
            "reactive": {k: reactive[k] for k in DEFAULT_LIGHTING["reactive"]}}


def _normalize_devices(given) -> dict:
    """{model: {setting: value}}; values are checked by the drivers when applied."""
    if given is None:
        return {}
    if not isinstance(given, dict):
        raise ConfigError("profile devices must be an object")
    devices = {}
    for model, settings in given.items():
        if not isinstance(settings, dict):
            raise ConfigError(f"settings of {model!r} must be an object")
        for name, value in settings.items():
            if not isinstance(value, (str, int, float, list)) or isinstance(value, bool):
                raise ConfigError(f"{model}.{name} has an unsupported value: {value!r}")
        devices[str(model)] = dict(settings)
    return devices


def normalize(config) -> dict:
    """Validate a configuration and fill in missing values. Raises ConfigError."""
    if not isinstance(config, dict):
        raise ConfigError("the configuration must be an object")
    desk = _merge(DEFAULT_DESK, config.get("desk"))
    if desk["keyboard_layout"] not in LAYOUTS:
        raise ConfigError(f"unknown keyboard layout {desk['keyboard_layout']!r}")
    desk = {"keyboard_layout": desk["keyboard_layout"],
            "mouse_x": _number("desk", "mouse_x", desk["mouse_x"])}

    profiles_in = config.get("profiles")
    if profiles_in is None:
        profiles_in = {"Default": {}}
    if not isinstance(profiles_in, dict) or not profiles_in:
        raise ConfigError("there must be at least one profile")
    if len(profiles_in) > MAX_PROFILES:
        raise ConfigError(f"too many profiles (maximum {MAX_PROFILES})")
    profiles = {}
    for name, profile in profiles_in.items():
        clean = str(name).strip()
        if not 0 < len(clean) <= MAX_PROFILE_NAME:
            raise ConfigError(f"profile names must have 1 to {MAX_PROFILE_NAME} characters")
        if clean in profiles:
            raise ConfigError(f"duplicate profile name {clean!r}")
        if not isinstance(profile, dict):
            raise ConfigError(f"profile {clean!r} must be an object")
        try:
            profiles[clean] = {"lighting": _normalize_lighting(profile.get("lighting")),
                               "devices": _normalize_devices(profile.get("devices"))}
        except ConfigError as error:
            raise ConfigError(f"profile {clean!r}: {error}") from None

    active = str(config.get("active_profile", "")).strip()
    if active not in profiles:
        active = next(iter(profiles))
    return {"version": CONFIG_VERSION, "active_profile": active, "desk": desk, "profiles": profiles}


# ---- Storage -------------------------------------------------------------------

def _xdg(variable: str, fallback: str) -> str:
    return os.environ.get(variable) or os.path.join(os.path.expanduser("~"), fallback)


def config_path() -> str:
    return os.path.join(_xdg("XDG_CONFIG_HOME", ".config"), "favilla", "config.json")


def state_path() -> str:
    return os.path.join(_xdg("XDG_STATE_HOME", ".local/state"), "favilla", "state.json")


def _write_json(path: str, data: dict) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


class ConfigStore:
    def __init__(self, path: str | None = None):
        self.path = path or config_path()

    def load(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                return normalize(json.load(f))
        except FileNotFoundError:
            return default_config()
        except (OSError, ValueError) as error:  # ConfigError is a ValueError too
            backup = self.path + ".broken"
            log.error("cannot use %s (%s): starting from defaults, old file kept as %s",
                      self.path, error, backup)
            try:
                os.replace(self.path, backup)
            except OSError:
                pass
            return default_config()

    def save(self, config: dict) -> None:
        _write_json(self.path, config)


class StateStore:
    """What the daemon already wrote to each device, to avoid useless writes to
    the device memory: {"applied": {model: {setting: value}}, "persisted": {model: digest}}."""

    def __init__(self, path: str | None = None):
        self.path = path or state_path()

    def load(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                state = json.load(f)
        except (OSError, ValueError):
            state = {}
        if not isinstance(state, dict):
            state = {}
        for key in ("applied", "persisted"):
            if not isinstance(state.get(key), dict):
                state[key] = {}
        return state

    def save(self, state: dict) -> None:
        _write_json(self.path, state)
