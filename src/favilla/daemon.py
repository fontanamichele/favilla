"""favillad: the Favilla daemon.

It owns every supported device: it reads key presses and clicks, renders the
lighting effect, applies the profile settings and serves the D-Bus API used by
the GUI and favillactl. Devices are only touched from the main thread (plus
each mouse's writer thread); D-Bus calls are queued and run between frames.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import queue
import select
import signal
import threading
import time

from . import __version__
from . import config as cfg
from . import devices as devmod
from .lighting import LightingEngine, to_hex

log = logging.getLogger("favilla")

FRAME_RATE = 60
SCAN_INTERVAL = 3.0       # look for plugged/unplugged devices
BATTERY_INTERVAL = 60.0
PERSIST_DELAY = 2.0       # wait for the user to stop dragging sliders before writing device memory
CALL_TIMEOUT = 5.0

MOUSE_CENTER_Y = 3.0      # the mouse center is level with the middle of the keyboard (rows 0..5)


class Daemon:
    def __init__(self, store: cfg.ConfigStore, state_store: cfg.StateStore):
        self.store, self.state_store = store, state_store
        self.config = store.load()
        if not os.path.exists(store.path):
            try:
                store.save(self.config)  # so that users find it where the docs say
            except OSError as error:
                log.warning("cannot write %s: %s", store.path, error)
        self.state = state_store.load()
        self.devices: dict[str, devmod.Device] = {}   # candidate key -> device
        self.others: dict[str, dict] = {}             # unsupported devices or devices that failed to open
        self.engine = LightingEngine(cfg.active_profile(self.config)["lighting"])
        self.frames: dict[str, dict] = {}             # device id -> last frame
        self._positions: dict[str, list] = {}         # device id -> [(led id, desk x, desk y)]
        self._last_sent: dict[str, float] = {}
        self._idle = False                            # resting frame already sent
        self._persist_at: float | None = None
        self._tasks: queue.SimpleQueue = queue.SimpleQueue()
        self._wake_r, self._wake_w = os.pipe()
        os.set_blocking(self._wake_r, False)
        os.set_blocking(self._wake_w, False)
        self._listeners = []
        self._running = True

    # ---- called from other threads -------------------------------------------

    def submit(self, fn, *args):
        """Run fn(*args) in the main loop and return its result."""
        done, box = threading.Event(), {}

        def task():
            try:
                box["result"] = fn(*args)
            except BaseException as error:  # handed back to the caller
                box["error"] = error
            finally:
                done.set()

        self._tasks.put(task)
        self._wake()
        if not done.wait(CALL_TIMEOUT):
            raise TimeoutError("the daemon did not answer in time")
        if "error" in box:
            raise box["error"]
        return box.get("result")

    def stop(self) -> None:
        self._running = False
        self._wake()

    def add_listener(self, callback) -> None:
        """callback(signal_name, payload_json), called from the main thread."""
        self._listeners.append(callback)

    def _wake(self) -> None:
        try:
            os.write(self._wake_w, b"x")
        except BlockingIOError:
            pass  # already awake

    # ---- API (main thread) -----------------------------------------------------

    def get_devices(self) -> list[dict]:
        listed = [dict(device.describe(), state="connected") for device in self.devices.values()]
        return listed + list(self.others.values())

    def get_config(self) -> dict:
        return self.config

    def set_config(self, raw: dict) -> None:
        new = cfg.normalize(raw)
        old, self.config = self.config, new
        self.store.save(new)
        if new["desk"] != old["desk"]:
            for device in self.devices.values():
                if hasattr(device, "set_layout"):
                    device.set_layout(new["desk"]["keyboard_layout"])
            self._update_positions()
            self._emit("DevicesChanged", self.get_devices())
        if (cfg.active_profile(new)["lighting"] != cfg.active_profile(old)["lighting"]
                or new["desk"] != old["desk"]):
            self._lighting_changed()
        if new["active_profile"] != old["active_profile"]:
            log.info("profile: %s", new["active_profile"])
            self._apply_profile_settings()
        self._emit("ConfigChanged", new)

    def set_active_profile(self, name: str) -> None:
        if name not in self.config["profiles"]:
            raise cfg.ConfigError(f"there is no profile called {name!r}")
        self.set_config(dict(self.config, active_profile=name))

    def apply_device_settings(self, device_id: str) -> list[str]:
        """Apply every setting of the active profile to one device, even unchanged ones."""
        device = self._device(device_id)
        return self._apply_settings(device, force=True)

    def get_frame(self) -> dict:
        return {device_id: {led: to_hex(color) for led, color in frame.items()}
                for device_id, frame in self.frames.items()}

    def simulate_press(self, device_id: str, led_id: str) -> None:
        device = self._device(device_id)
        for led, x, y in self._positions.get(device.id, []):
            if led == led_id:
                self.engine.press(x, y, device.id, time.monotonic())
                self._idle = False
                return
        raise cfg.ConfigError(f"{device.name} has no LED {led_id!r}")

    # ---- internals ---------------------------------------------------------------

    def _device(self, device_id: str) -> devmod.Device:
        for device in self.devices.values():
            if device.id == device_id:
                return device
        raise cfg.ConfigError(f"no connected device {device_id!r}")

    def _emit(self, name: str, payload) -> None:
        text = json.dumps(payload)
        for callback in self._listeners:
            try:
                callback(name, text)
            except Exception:
                log.exception("signal listener failed")

    def _offset(self, device: devmod.Device) -> tuple[float, float]:
        if device.kind == "mouse":
            return self.config["desk"]["mouse_x"], MOUSE_CENTER_Y
        return 0.0, 0.0

    def _update_positions(self) -> None:
        self._positions = {}
        for device in self.devices.values():
            dx, dy = self._offset(device)
            self._positions[device.id] = [(led.id, led.x + dx, led.y + dy) for led in device.leds()]

    def _lighting_changed(self) -> None:
        self.engine = LightingEngine(cfg.active_profile(self.config)["lighting"])
        self._idle = False
        self._persist_at = time.monotonic() + PERSIST_DELAY

    def _save_state(self) -> None:
        try:
            self.state_store.save(self.state)
        except OSError as error:
            log.warning("cannot save %s: %s", self.state_store.path, error)

    def _apply_settings(self, device: devmod.Device, force: bool = False) -> list[str]:
        wanted = cfg.active_profile(self.config)["devices"].get(device.model, {})
        applied = self.state["applied"].setdefault(device.model, {})
        changes = {k: v for k, v in wanted.items() if force or applied.get(k) != v}
        if not changes:
            return []
        try:
            errors = device.apply_settings(changes)
        except OSError as error:
            self._drop(device, error)
            return [f"{device.name}: {error}"]
        for name, value in changes.items():
            if name not in errors:
                applied[name] = value
        self._save_state()
        log.info("%s: applied %s", device.name, ", ".join(sorted(set(changes) - set(errors))) or "nothing")
        return [f"{device.name} {name}: {message}" for name, message in errors.items()]

    def _apply_profile_settings(self) -> None:
        for device in list(self.devices.values()):
            for error in self._apply_settings(device):
                log.warning("%s", error)

    def _persist_lighting(self) -> None:
        """Store the resting colors in the devices that keep them (the mouse), so
        that they show the right colors when Favilla is not running."""
        for device in list(self.devices.values()):
            if type(device).persist_colors is devmod.Device.persist_colors:
                continue
            colors = self.engine.resting(self._positions.get(device.id, []))
            digest = hashlib.sha1(json.dumps(sorted(colors.items())).encode()).hexdigest()
            if self.state["persisted"].get(device.model) == digest:
                continue
            try:
                device.persist_colors(colors)
            except OSError as error:
                self._drop(device, error)
                continue
            self.state["persisted"][device.model] = digest
            self._save_state()
            log.info("%s: saved the resting colors in the device memory", device.name)

    def _scan(self) -> None:
        try:
            candidates = devmod.discover()
        except OSError as error:
            log.warning("device scan failed: %s", error)
            return
        present = {c.key for c in candidates}
        changed = False
        for key in [k for k in self.devices if k not in present]:
            self._close(key, "unplugged")
            changed = True
        others = {}
        for candidate in candidates:
            if candidate.key in self.devices:
                continue
            if candidate.driver is None:
                others[candidate.key] = {"id": candidate.key, "name": candidate.name,
                                         "state": "unsupported"}
                continue
            try:
                device = devmod.open_device(candidate, self.config["desk"])
            except PermissionError:
                path = candidate.nodes[0].path
                others[candidate.key] = {"id": candidate.key, "name": candidate.name,
                                         "state": "no_permission",
                                         "message": f"permission denied on {path}: install the udev rules"}
                continue
            except (OSError, ValueError) as error:
                others[candidate.key] = {"id": candidate.key, "name": candidate.name,
                                         "state": "error", "message": str(error)}
                continue
            self.devices[candidate.key] = device
            log.info("connected: %s (%s, %s)", device.name, device.id, device.connection)
            changed = True
            self._update_positions()
            self._idle = False
            self._apply_profile_settings()
            self._persist_at = self._persist_at or time.monotonic()
        if others != self.others:
            self.others = others
            changed = True
        if changed:
            self._update_positions()
            self._emit("DevicesChanged", self.get_devices())

    def _close(self, key: str, reason: str) -> None:
        device = self.devices.pop(key)
        log.info("disconnected: %s (%s)", device.name, reason)
        self.frames.pop(device.id, None)
        self._last_sent.pop(device.id, None)
        device.close()

    def _drop(self, device: devmod.Device, error: Exception) -> None:
        for key, value in list(self.devices.items()):
            if value is device:
                self._close(key, str(error))
                self._update_positions()
                self._emit("DevicesChanged", self.get_devices())
                return

    def _send(self, device: devmod.Device, frame: dict, now: float) -> None:
        try:
            device.show(frame)
        except OSError as error:
            self._drop(device, error)
            return
        self.frames[device.id] = frame
        self._last_sent[device.id] = now

    def _render(self, now: float) -> None:
        animated = self.engine.animated(now)
        if not animated and self._idle:
            for device in list(self.devices.values()):
                last = self._last_sent.get(device.id, 0.0)
                if device.keepalive and now - last >= device.keepalive and device.id in self.frames:
                    self._send(device, self.frames[device.id], now)
            return
        for device in list(self.devices.values()):
            if animated and now - self._last_sent.get(device.id, 0.0) < 1.0 / device.max_fps:
                continue
            self._send(device, self.engine.frame(device.id, self._positions.get(device.id, []), now), now)
        self._idle = not animated

    def _timeout(self, now: float, deadlines: list[float]) -> float:
        if self.engine.animated(now) or not self._idle:
            return 1.0 / FRAME_RATE
        for device in self.devices.values():
            if device.keepalive:
                deadlines.append(self._last_sent.get(device.id, now) + device.keepalive)
        if self._persist_at is not None:
            deadlines.append(self._persist_at)
        return max(0.0, min(deadlines) - now)

    def _run_tasks(self) -> None:
        try:
            while os.read(self._wake_r, 4096):
                pass
        except BlockingIOError:
            pass
        while True:
            try:
                task = self._tasks.get_nowait()
            except queue.Empty:
                return
            task()

    def run(self) -> None:
        next_scan = 0.0
        next_battery = time.monotonic() + 3.0
        while self._running:
            now = time.monotonic()
            if now >= next_scan:
                self._scan()
                next_scan = now + SCAN_INTERVAL
            if now >= next_battery:
                for device in list(self.devices.values()):
                    try:
                        device.poll()
                    except OSError as error:
                        self._drop(device, error)
                next_battery = now + BATTERY_INTERVAL

            owners = {fd: device for device in self.devices.values() for fd in device.input_fds()}
            timeout = self._timeout(now, [next_scan, next_battery])
            ready = select.select([self._wake_r, *owners], [], [], timeout)[0]
            now = time.monotonic()
            for fd in ready:
                if fd == self._wake_r:
                    self._run_tasks()
                    continue
                device = owners[fd]
                if device not in self.devices.values():
                    continue  # dropped while handling an earlier fd
                try:
                    presses = device.read_input(fd)
                except OSError as error:
                    self._drop(device, error)
                    continue
                dx, dy = self._offset(device)
                for x, y in presses:
                    self.engine.press(x + dx, y + dy, device.id, now)
                    self._idle = False
            self._render(time.monotonic())
            if self._persist_at is not None and time.monotonic() >= self._persist_at:
                self._persist_at = None
                self._persist_lighting()
        self.shutdown()

    def shutdown(self) -> None:
        """Leave the devices showing the resting colors, then release them."""
        for key, device in list(self.devices.items()):
            try:
                device.show(self.engine.resting(self._positions.get(device.id, [])))
                time.sleep(0.05)
            except OSError:
                pass
            self._close(key, "daemon stopped")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="favillad", description="Favilla daemon: lighting and settings "
                                     "for SteelSeries devices.")
    parser.add_argument("--debug", action="store_true", help="verbose logging")
    parser.add_argument("--version", action="version", version=f"favillad {__version__}")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    from .dbus_service import DBusService  # needs PyGObject

    daemon = Daemon(cfg.ConfigStore(), cfg.StateStore())
    service = DBusService(daemon)
    try:
        service.start()
    except RuntimeError as error:
        log.error("%s", error)
        return 1
    daemon.add_listener(service.emit)
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: daemon.stop())
    log.info("favillad %s started, profile %r", __version__, daemon.config["active_profile"])
    try:
        daemon.run()
    finally:
        service.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
