"""Mice supported by rivalcfg (https://github.com/flozz/rivalcfg).

rivalcfg describes every mouse as data: commands, accepted values, the save
command and the battery query. Favilla reuses those descriptions but sends the
packets itself, from a single writer thread, so that animation frames and
settings never interleave. In 2.4 GHz mode the mouse replies to every command
(with the command byte as echo) and drops new commands until it has replied,
so the writer waits for each reply (about 8 ms). See
docs/protocols/aerox-5-wireless.md.
"""

from __future__ import annotations

import collections
import logging
import os
import re
import select
import threading
import time

from .. import hid
from ..lighting import Color
from .base import Device, Led

try:
    from rivalcfg import devices as rival_devices
    from rivalcfg import handlers as rival_handlers
    from rivalcfg import helpers as rival_helpers
except ImportError:  # rivalcfg is optional: without it no mouse is supported
    rival_devices = rival_handlers = rival_helpers = None

log = logging.getLogger(__name__)

REPORT_TYPE_FEATURE = 0x03     # rivalcfg.usbhid.HID_REPORT_TYPE_FEATURE (else: output report)
REPLY_TIMEOUT = 0.1            # s to wait for the reply of a wireless mouse
COMMAND_DELAY = 0.05           # rivalcfg's delay between commands for mice that do not reply
MAX_LED_ATTEMPTS = 3           # give up on a color the mouse does not confirm (asleep?)

# value_type -> how the GUI edits it. Other types (button mapping, gradients...)
# are not editable from Favilla yet.
SETTING_TYPES = {"choice": "choice", "range": "range", "range_choice": "range",
                 "multidpi_range": "dpi", "multidpi_range_choice": "dpi",
                 "reactive_rgbcolor": "color_or_off"}

# Device coordinates of known LED zones (key units, (0, 0) = mouse center).
ZONE_POSITIONS = {"z1_color": (0.0, -1.0), "z2_color": (0.0, 0.0), "z3_color": (0.0, 1.0),
                  "wheel_color": (0.0, -1.6), "color": (0.0, 0.0), "logo_color": (0.0, 1.6)}
BODY = (-1.8, -3.4, 3.6, 6.8)  # roughly an Aerox 5 (68 x 129 mm)


def profile_for(vendor_id: int, product_id: int) -> dict | None:
    if rival_devices is None:
        return None
    try:
        return rival_devices.get_profile(vendor_id, product_id)
    except Exception:  # rivalcfg raises UnsupportedDevice
        return None


def display_name(profile_name: str) -> str:
    """'SteelSeries Aerox 5 Wireless (2.4 GHz wireless mode)' -> 'Aerox 5 Wireless'."""
    return re.sub(r"\s*\(.*\)\s*$", "", profile_name).replace("SteelSeries", "").strip()


def model_key(profile_name: str) -> str:
    """Same key for the wired and wireless modes of a mouse: 'aerox_5_wireless'."""
    return re.sub(r"[^a-z0-9]+", "_", display_name(profile_name).lower()).strip("_")


def build_packet(info: dict, values=()) -> bytes:
    """The bytes rivalcfg would write for a command: report id 0, command,
    value, optional suffix, zero padded to packet_length when given."""
    data = rival_helpers.merge_bytes(info["command"], list(values), info.get("command_suffix", []))
    length = info.get("packet_length", 0)
    if length:
        data = data + [0] * (length - len(data))
    return bytes([0x00] + data)


def _jsonable_default(setting_type: str, value):
    if setting_type == "dpi" and isinstance(value, str):
        return [int(v) for v in value.replace(" ", "").split(",") if v]
    if isinstance(value, (str, int, float)) or value is None:
        return value
    return str(value)


def _integers(value):
    """JSON (and QML) turn integers into floats: give rivalcfg integers back."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, list):
        return [_integers(v) for v in value]
    return value


class _Job:
    def __init__(self, packet: bytes, report_type: int, wants_reply: bool, on_reply=None):
        self.packet, self.report_type, self.wants_reply = packet, report_type, wants_reply
        self.on_reply = on_reply


class RivalMouse(Device):
    kind = "mouse"
    max_fps = 30
    body = BODY

    def __init__(self, nodes, profile: dict):
        super().__init__(nodes)
        self.profile = profile
        self.name = display_name(profile["name"])
        self.model = model_key(profile["name"])
        self.connection = "wireless" if "wireless mode" in profile["name"] else "wired"
        command_node = next((n for n in nodes if n.interface == profile["endpoint"]), None)
        if command_node is None:
            raise OSError(f"{self.name}: command interface {profile['endpoint']} not found")
        buttons = next((n for n in nodes if n.is_mouse), None)
        try:
            self._cmd_fd = self._open(command_node.path, write=True)
            self._button_fd = self._open(buttons.path) if buttons else None
        except OSError:
            self.close()
            raise
        self._button_offset = 1 if buttons and hid.uses_report_ids(buttons.descriptor) else 0
        self._buttons = 0

        zones = [(name, info) for name, info in profile["settings"].items()
                 if info.get("value_type") == "rgbcolor"]
        self._zone_info = {}
        self._leds = []
        for i, (name, info) in enumerate(zones):
            x, y = ZONE_POSITIONS.get(name, (0.0, i - (len(zones) - 1) / 2))
            led_id = f"z{i}"
            self._zone_info[led_id] = info
            self._leds.append(Led(led_id, x, y, info.get("label", name),
                                  ((x - 0.26, y - 0.42, 0.52, 0.84),)))   # drawn as a light strip

        self._battery: dict | None = None
        self.error: OSError | None = None
        self._cond = threading.Condition()
        self._target: dict[str, Color] = {}     # latest colors asked for
        self._confirmed: dict[str, Color] = {}  # colors the mouse acknowledged
        self._jobs: collections.deque[_Job] = collections.deque()
        self._closed = False
        self._thread = threading.Thread(target=self._writer, name=f"favilla-{self.model}",
                                        daemon=True)
        self._thread.start()

    # ---- writer thread -----------------------------------------------------

    def _pending_leds(self) -> dict[str, Color]:
        return {k: c for k, c in self._target.items() if self._confirmed.get(k) != c}

    def _writer(self) -> None:
        failures: dict[str, int] = {}
        try:
            while True:
                with self._cond:
                    while not (self._closed or self._jobs or self._pending_leds()):
                        self._cond.wait()
                    if self._closed:
                        return
                    job = self._jobs.popleft() if self._jobs else None
                    leds = None if job else self._pending_leds()
                if job:
                    reply = self._transmit(job.packet, job.report_type, job.wants_reply)
                    if job.on_reply:
                        job.on_reply(reply)
                    continue
                for led_id, color in leds.items():
                    info = self._zone_info[led_id]
                    wants_reply = bool(info.get("readback_length"))
                    reply = self._transmit(build_packet(info, color), info["report_type"], wants_reply)
                    ok = reply is not None
                    failures[led_id] = 0 if ok else failures.get(led_id, 0) + 1
                    if ok or failures[led_id] >= MAX_LED_ATTEMPTS:
                        failures[led_id] = 0
                        with self._cond:
                            self._confirmed[led_id] = color
                    with self._cond:
                        if self._jobs or self._closed:   # settings go first
                            break
        except OSError as error:
            self.error = error

    def _transmit(self, packet: bytes, report_type: int, wants_reply: bool) -> bytes | None:
        """Send one command; return the reply (b"" if none is expected) or None."""
        hid.read_reports(self._cmd_fd)  # drop stale replies
        if report_type == REPORT_TYPE_FEATURE:
            hid.send_feature_report(self._cmd_fd, packet)
        else:
            os.write(self._cmd_fd, packet)
        if not wants_reply:
            time.sleep(COMMAND_DELAY)
            return b""
        deadline = time.monotonic() + REPLY_TIMEOUT
        while (left := deadline - time.monotonic()) > 0:
            if select.select([self._cmd_fd], [], [], left)[0]:
                for reply in hid.read_reports(self._cmd_fd):
                    if reply[:1] == packet[1:2]:  # the reply echoes the command byte
                        return reply
        return None

    def _queue(self, jobs: list[_Job]) -> None:
        if self.error:
            raise self.error
        with self._cond:
            self._jobs.extend(jobs)
            self._cond.notify()

    def _command(self, info: dict, values=(), on_reply=None) -> _Job:
        return _Job(build_packet(info, values), info["report_type"],
                    bool(info.get("readback_length")), on_reply)

    # ---- Device interface ---------------------------------------------------

    def leds(self):
        return self._leds

    def input_fds(self):
        return [self._button_fd] if self._button_fd is not None else []

    def read_input(self, fd):
        clicked = False
        for report in hid.read_reports(fd):
            if len(report) > self._button_offset:
                buttons = report[self._button_offset]
                clicked |= bool(buttons & ~self._buttons)
                self._buttons = buttons
        return [(0.0, 0.0)] if clicked else []

    def show(self, colors):
        if self.error:
            raise self.error
        with self._cond:
            self._target.update(colors)
            self._cond.notify()

    def persist_colors(self, colors):
        jobs = [self._command(self._zone_info[led_id], color)
                for led_id, color in colors.items() if led_id in self._zone_info]
        save = self.profile.get("save_command")
        if jobs and save:
            jobs.append(self._command(save))
        with self._cond:
            self._target.update(colors)
            self._confirmed.update(colors)
        self._queue(jobs)

    def settings_schema(self):
        schema = []
        for name, info in self.profile["settings"].items():
            kind = SETTING_TYPES.get(info.get("value_type"))
            if kind is None:
                continue
            entry = {"name": name, "type": kind, "label": info.get("label", name),
                     "description": info.get("description", ""),
                     "default": _jsonable_default(kind, info.get("default"))}
            if kind == "choice":
                entry["choices"] = [str(choice) for choice in info["choices"]]
                entry["default"] = str(entry["default"])
            elif kind in ("range", "dpi"):
                entry["min"], entry["max"], entry["step"] = info["input_range"]
                if kind == "dpi":
                    entry["max_count"] = info.get("max_preset_count", 1)
            schema.append(entry)
        return schema

    def apply_settings(self, values):
        errors, jobs = {}, []
        for name, value in values.items():
            info = self.profile["settings"].get(name)
            if info is None or info.get("value_type") not in SETTING_TYPES:
                errors[name] = "not a setting Favilla can change on this mouse"
                continue
            try:
                handler = getattr(rival_handlers, info["value_type"])
                data = handler.process_value(info, _integers(value))
            except (ValueError, TypeError, KeyError, AttributeError) as error:
                errors[name] = str(error) or "invalid value"
                continue
            jobs.append(self._command(info, data))
        save = self.profile.get("save_command")
        if jobs and save:
            jobs.append(self._command(save))
        self._queue(jobs)
        return errors

    def poll(self):
        info = self.profile.get("battery_level")
        if not info:
            return

        def on_reply(reply):
            if not reply:
                self._battery = None
                return
            data = list(reply[:info.get("response_length", len(reply))])
            try:
                level = info["level"](data)
                charging = bool(info["is_charging"](data)) if "is_charging" in info else None
            except Exception:
                self._battery = None
                return
            self._battery = {"level": level, "charging": charging} if 0 <= level <= 100 else None

        self._queue([self._command(info, on_reply=on_reply)])

    def status(self):
        return {"battery": dict(self._battery)} if self._battery else {}

    def close(self):
        cond = getattr(self, "_cond", None)  # absent if opening the device failed
        if cond is not None:
            deadline = time.monotonic() + 0.5   # let the last colors and settings go out
            while (self._jobs or self._pending_leds()) and self.error is None \
                    and self._thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.02)
            with cond:
                self._closed = True
                cond.notify()
        thread = getattr(self, "_thread", None)
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(1.0)
        super().close()
