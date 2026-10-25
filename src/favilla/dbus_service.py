"""The daemon's D-Bus API on the session bus, served from its own GLib thread.

Every method takes and returns JSON strings: the payloads (devices, the whole
configuration, animation frames) are nested structures that are much easier
to evolve and to use from any language as JSON. See docs/architecture.md.
"""

from __future__ import annotations

import json
import logging
import threading

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

from . import APP_ID, __version__  # noqa: E402
from .config import ConfigError  # noqa: E402

log = logging.getLogger(__name__)

BUS_NAME = APP_ID
OBJECT_PATH = "/" + APP_ID.replace(".", "/")
INTERFACE = APP_ID + "1"
ERROR_NAME = INTERFACE + ".Error"

INTROSPECTION = f"""<node>
  <interface name="{INTERFACE}">
    <method name="GetVersion"><arg direction="out" type="s" name="version"/></method>
    <method name="GetDevices"><arg direction="out" type="s" name="devices"/></method>
    <method name="GetConfig"><arg direction="out" type="s" name="config"/></method>
    <method name="SetConfig"><arg direction="in" type="s" name="config"/></method>
    <method name="SetActiveProfile"><arg direction="in" type="s" name="name"/></method>
    <method name="ApplyDeviceSettings">
      <arg direction="in" type="s" name="device_id"/>
      <arg direction="out" type="s" name="errors"/>
    </method>
    <method name="GetFrame"><arg direction="out" type="s" name="frame"/></method>
    <method name="SimulatePress">
      <arg direction="in" type="s" name="device_id"/>
      <arg direction="in" type="s" name="led_id"/>
    </method>
    <signal name="ConfigChanged"><arg type="s" name="config"/></signal>
    <signal name="DevicesChanged"><arg type="s" name="devices"/></signal>
  </interface>
</node>"""


class DBusService:
    def __init__(self, daemon):
        self.daemon = daemon
        self._interface = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION).interfaces[0]
        self._connection = None
        self._loop = None
        self._ready = threading.Event()
        self._failure: str | None = None

    def start(self, timeout: float = 10.0) -> None:
        threading.Thread(target=self._run, name="favilla-dbus", daemon=True).start()
        if not self._ready.wait(timeout):
            raise RuntimeError("timed out while connecting to the session bus")
        if self._failure:
            raise RuntimeError(self._failure)

    def stop(self) -> None:
        if self._loop is not None:
            self._loop.quit()

    def emit(self, name: str, payload: str) -> None:
        if self._connection is not None:
            self._connection.emit_signal(None, OBJECT_PATH, INTERFACE, name,
                                         GLib.Variant("(s)", (payload,)))

    def _run(self) -> None:
        context = GLib.MainContext.new()
        context.push_thread_default()
        self._loop = GLib.MainLoop.new(context, False)
        Gio.bus_own_name(Gio.BusType.SESSION, BUS_NAME, Gio.BusNameOwnerFlags.DO_NOT_QUEUE,
                         self._on_bus_acquired, self._on_name_acquired, self._on_name_lost)
        self._loop.run()

    def _on_bus_acquired(self, connection, name):
        self._connection = connection
        connection.register_object(OBJECT_PATH, self._interface, self._on_call, None, None)

    def _on_name_acquired(self, connection, name):
        self._ready.set()

    def _on_name_lost(self, connection, name):
        if not self._ready.is_set():
            self._failure = f"cannot own {name} on the session bus: is favillad already running?"
            self._ready.set()
        else:
            log.error("lost the D-Bus name %s, stopping", name)
            self.daemon.stop()

    def _on_call(self, connection, sender, path, interface, method, parameters, invocation):
        handler = getattr(self, "_method_" + method, None)
        try:
            if handler is None:
                raise ConfigError(f"unknown method {method}")
            result = handler(*parameters.unpack())
        except (ConfigError, TimeoutError) as error:
            invocation.return_dbus_error(ERROR_NAME, str(error))
            return
        except Exception as error:
            log.exception("D-Bus method %s failed", method)
            invocation.return_dbus_error(ERROR_NAME, f"internal error: {error}")
            return
        invocation.return_value(None if result is None else GLib.Variant("(s)", (result,)))

    # ---- methods ---------------------------------------------------------------

    def _method_GetVersion(self):
        return __version__

    def _method_GetDevices(self):
        return json.dumps(self.daemon.submit(self.daemon.get_devices))

    def _method_GetConfig(self):
        return json.dumps(self.daemon.submit(self.daemon.get_config))

    def _method_SetConfig(self, text):
        try:
            data = json.loads(text)
        except ValueError as error:
            raise ConfigError(f"invalid JSON: {error}") from None
        self.daemon.submit(self.daemon.set_config, data)

    def _method_SetActiveProfile(self, name):
        self.daemon.submit(self.daemon.set_active_profile, name)

    def _method_ApplyDeviceSettings(self, device_id):
        return json.dumps(self.daemon.submit(self.daemon.apply_device_settings, device_id))

    def _method_GetFrame(self):
        return json.dumps(self.daemon.submit(self.daemon.get_frame))

    def _method_SimulatePress(self, device_id, led_id):
        self.daemon.submit(self.daemon.simulate_press, device_id, led_id)
