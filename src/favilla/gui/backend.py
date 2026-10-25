"""Bridge between the QML interface and the daemon.

The configuration edited by the interface is a local copy: changes show up
immediately and are sent to the daemon shortly after the user stops dragging
(PUSH_DELAY). Device settings are only written when the user presses Apply,
because they end up in the device memory.
"""

from __future__ import annotations

import copy
import logging

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtGui import QColor

from ..client import Client, DaemonError, DaemonNotRunning
from ..config import MAX_PROFILE_NAME

log = logging.getLogger(__name__)

PUSH_DELAY = 120       # ms
FRAME_INTERVAL = 33    # ms, live preview
REFRESH_INTERVAL = 10000
RETRY_INTERVAL = 2000

_FAILED = object()  # returned by Backend._call when the call did not succeed


def _plain(value):
    """QML values -> JSON-friendly Python values."""
    if isinstance(value, QColor):
        return value.name()
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


class Backend(QObject):
    onlineChanged = Signal()
    devicesChanged = Signal()
    configChanged = Signal()
    frameChanged = Signal()
    previewEnabledChanged = Signal()
    notify = Signal(str, bool)  # message, is_error

    def __init__(self, parent=None):
        super().__init__(parent)
        self._client: Client | None = None
        self._online = False
        self._devices: list = []
        self._config: dict = {}
        self._frame: dict = {}
        self._preview = False
        self._push_timer = QTimer(self, singleShot=True, interval=PUSH_DELAY, timeout=self._push)
        self._frame_timer = QTimer(self, interval=FRAME_INTERVAL, timeout=self._poll_frame)
        self._refresh_timer = QTimer(self, interval=REFRESH_INTERVAL, timeout=self._refresh_devices)
        self._retry_timer = QTimer(self, interval=RETRY_INTERVAL, timeout=self._connect)
        self._connect()

    # ---- connection --------------------------------------------------------

    def _connect(self) -> None:
        try:
            if self._client is None:
                self._client = Client()
                self._client.subscribe(self._on_signal)
            config, devices = self._client.config(), self._client.devices()
        except DaemonError as error:
            log.debug("daemon unavailable: %s", error)
            self._set_online(False)
            return
        self._config, self._devices = config, devices
        self._set_online(True)
        self.configChanged.emit()
        self.devicesChanged.emit()

    def _set_online(self, online: bool) -> None:
        if online != self._online:
            self._online = online
            self.onlineChanged.emit()
        if online:
            self._retry_timer.stop()
            self._refresh_timer.start()
        else:
            self._retry_timer.start()
            self._refresh_timer.stop()
        self._update_frame_timer()

    def _call(self, method, *args, quiet=False):
        if self._client is None or not self._online:
            return _FAILED
        try:
            return method(*args)
        except DaemonNotRunning:
            self._set_online(False)
        except DaemonError as error:
            if not quiet:
                self.notify.emit(str(error), True)
        return _FAILED

    def _on_signal(self, name: str, payload) -> None:
        if name == "DevicesChanged":
            self._devices = payload
            self.devicesChanged.emit()
        elif name == "ConfigChanged" and not self._push_timer.isActive():
            self._config = payload  # local edits still pending win over the echo
            self.configChanged.emit()

    def _refresh_devices(self) -> None:
        devices = self._call(self._client.devices, quiet=True)
        if devices is not _FAILED and devices != self._devices:
            self._devices = devices
            self.devicesChanged.emit()

    def _update_frame_timer(self) -> None:
        if self._online and self._preview:
            self._frame_timer.start()
        else:
            self._frame_timer.stop()

    def _poll_frame(self) -> None:
        frame = self._call(self._client.frame, quiet=True)
        if frame is not _FAILED and frame != self._frame:
            self._frame = frame
            self.frameChanged.emit()

    # ---- configuration -----------------------------------------------------

    def _profile(self) -> dict:
        return self._config.get("profiles", {}).get(self._config.get("active_profile"), {})

    def _replace(self, config: dict, push_now: bool = True) -> bool:
        """Take a new local configuration; send it now or after PUSH_DELAY."""
        self._config = config
        self.configChanged.emit()
        if push_now:
            self._push_timer.stop()
            return self._push()
        self._push_timer.start()
        return True

    def _push(self) -> bool:
        if self._call(self._client.set_config, self._config) is not _FAILED:
            return True
        fresh = self._call(self._client.config, quiet=True)  # rejected: back to the daemon's copy
        if fresh is not _FAILED:
            self._config = fresh
            self.configChanged.emit()
        return False

    @Slot(str, "QVariant")
    def setLighting(self, path: str, value) -> None:
        if not self._config:
            return
        config = copy.deepcopy(self._config)
        node = config["profiles"][config["active_profile"]]["lighting"]
        *parents, key = path.split(".")
        for part in parents:
            node = node[part]
        node[key] = _plain(value)
        self._replace(config, push_now=False)

    @Slot(str, "QVariant")
    def setDesk(self, key: str, value) -> None:
        if not self._config:
            return
        config = copy.deepcopy(self._config)
        config["desk"][key] = _plain(value)
        self._replace(config, push_now=False)

    @Slot(str, str, "QVariantMap")
    def applyDeviceSettings(self, device_id: str, model: str, values) -> None:
        """values: {setting: value or None (forget the setting)}."""
        config = copy.deepcopy(self._config)
        devices = config["profiles"][config["active_profile"]]["devices"]
        settings = devices.setdefault(model, {})
        for name, value in _plain(dict(values)).items():
            if value is None:
                settings.pop(name, None)
            else:
                settings[name] = value
        if not settings:
            devices.pop(model, None)
        if not self._replace(config):
            return
        errors = self._call(self._client.apply_device_settings, device_id)
        if errors is _FAILED:
            return
        if errors:
            self.notify.emit("\n".join(errors), True)
        else:
            self.notify.emit(self.tr("Settings saved to the device"), False)

    # ---- profiles ----------------------------------------------------------

    def _check_name(self, name: str, ignore: str | None = None) -> str:
        if not name:
            return self.tr("The name cannot be empty")
        if len(name) > MAX_PROFILE_NAME:
            return self.tr("The name is too long")
        if name != ignore and name in self._config.get("profiles", {}):
            return self.tr("A profile with this name already exists")
        return ""

    @Slot(str)
    def switchProfile(self, name: str) -> None:
        if self._push_timer.isActive():
            self._push_timer.stop()
            self._push()
        if self._call(self._client.set_active_profile, name) is _FAILED:
            return
        fresh = self._call(self._client.config, quiet=True)
        if fresh is not _FAILED:
            self._config = fresh
            self.configChanged.emit()

    @Slot(str, result=str)
    def createProfile(self, name: str) -> str:
        name = name.strip()
        error = self._check_name(name)
        if error:
            return error
        config = copy.deepcopy(self._config)
        config["profiles"][name] = copy.deepcopy(self._profile())
        config["active_profile"] = name
        self._replace(config)
        return ""

    @Slot(str, str, result=str)
    def renameProfile(self, old: str, new: str) -> str:
        new = new.strip()
        error = self._check_name(new, ignore=old)
        if error or new == old:
            return error
        config = copy.deepcopy(self._config)
        config["profiles"] = {(new if k == old else k): v for k, v in config["profiles"].items()}
        if config["active_profile"] == old:
            config["active_profile"] = new
        self._replace(config)
        return ""

    @Slot(str, result=str)
    def deleteProfile(self, name: str) -> str:
        profiles = self._config.get("profiles", {})
        if len(profiles) <= 1:
            return self.tr("The last profile cannot be deleted")
        config = copy.deepcopy(self._config)
        del config["profiles"][name]
        if config["active_profile"] == name:
            config["active_profile"] = next(iter(config["profiles"]))
        self._replace(config)
        return ""

    @Slot(str, str)
    def simulatePress(self, device_id: str, led_id: str) -> None:
        self._call(self._client.simulate_press, device_id, led_id, quiet=True)

    # ---- properties --------------------------------------------------------

    @Property(bool, notify=onlineChanged)
    def online(self):
        return self._online

    @Property("QVariantList", notify=devicesChanged)
    def devices(self):
        return self._devices

    @Property("QVariantMap", notify=configChanged)
    def config(self):
        return self._config

    @Property("QVariantMap", notify=configChanged)
    def lighting(self):
        return self._profile().get("lighting", {})

    @Property("QVariantMap", notify=configChanged)
    def deviceSettings(self):
        """{model: {setting: value}} explicitly set in the active profile."""
        return self._profile().get("devices", {})

    @Property("QVariantMap", notify=configChanged)
    def desk(self):
        return self._config.get("desk", {})

    @Property("QStringList", notify=configChanged)
    def profileNames(self):
        return list(self._config.get("profiles", {}))

    @Property(str, notify=configChanged)
    def activeProfile(self):
        return self._config.get("active_profile", "")

    @Property("QVariantMap", notify=frameChanged)
    def frame(self):
        return self._frame

    def _get_preview(self):
        return self._preview

    def _set_preview(self, enabled: bool):
        if enabled != self._preview:
            self._preview = enabled
            self.previewEnabledChanged.emit()
            self._update_frame_timer()

    previewEnabled = Property(bool, _get_preview, _set_preview, notify=previewEnabledChanged)
