"""Synchronous client for the daemon's D-Bus API (used by favillactl and the GUI)."""

from __future__ import annotations

import json
import re

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

from .dbus_service import BUS_NAME, INTERFACE, OBJECT_PATH  # noqa: E402

NOT_RUNNING = "the Favilla daemon is not running (start it with: systemctl --user start favilla)"


class DaemonError(Exception):
    pass


class DaemonNotRunning(DaemonError):
    pass


class Client:
    def __init__(self, timeout_ms: int = 4000):
        self.timeout_ms = timeout_ms
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error as error:
            raise DaemonError(f"cannot connect to the session bus: {error.message}") from None

    def call(self, method: str, *args: str):
        parameters = GLib.Variant("(" + "s" * len(args) + ")", args) if args else None
        try:
            reply = self.bus.call_sync(BUS_NAME, OBJECT_PATH, INTERFACE, method, parameters,
                                       None, Gio.DBusCallFlags.NONE, self.timeout_ms, None)
        except GLib.Error as error:
            remote = Gio.DBusError.get_remote_error(error) or ""
            if remote in ("org.freedesktop.DBus.Error.ServiceUnknown",
                          "org.freedesktop.DBus.Error.NameHasNoOwner"):
                raise DaemonNotRunning(NOT_RUNNING) from None
            # "GDBus.Error:io.github...Error: message" -> "message"
            raise DaemonError(re.sub(r"^GDBus\.Error:[\w.]+:\s*", "", error.message)) from None
        values = reply.unpack()
        return values[0] if values else None

    def version(self) -> str:
        return self.call("GetVersion")

    def devices(self) -> list[dict]:
        return json.loads(self.call("GetDevices"))

    def config(self) -> dict:
        return json.loads(self.call("GetConfig"))

    def set_config(self, config: dict) -> None:
        self.call("SetConfig", json.dumps(config))

    def set_active_profile(self, name: str) -> None:
        self.call("SetActiveProfile", name)

    def apply_device_settings(self, device_id: str) -> list[str]:
        return json.loads(self.call("ApplyDeviceSettings", device_id))

    def frame(self) -> dict:
        return json.loads(self.call("GetFrame"))

    def simulate_press(self, device_id: str, led_id: str) -> None:
        self.call("SimulatePress", device_id, led_id)

    def subscribe(self, callback) -> int:
        """callback(signal_name, payload_dict); delivered by the default GLib main context."""
        def on_signal(connection, sender, path, interface, name, parameters):
            callback(name, json.loads(parameters.unpack()[0]))
        return self.bus.signal_subscribe(BUS_NAME, INTERFACE, None, OBJECT_PATH, None,
                                         Gio.DBusSignalFlags.NONE, on_signal)
