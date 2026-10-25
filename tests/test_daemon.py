import json
import os
import tempfile
import threading
import time
import unittest

from favilla import config as cfg
from favilla.daemon import Daemon
from favilla.devices.base import Device, Led
from favilla.hid import HidNode

ORANGE = (255, 68, 0)


class FakeMouse(Device):
    kind = "mouse"
    model = "fake_mouse"
    name = "Fake mouse"

    def __init__(self):
        super().__init__([HidNode("/dev/null", 0x1038, 0xFFFF, 0, "9-9")])
        self.shown, self.persisted, self.applied = [], [], []

    def leds(self):
        return [Led("z0", 0.0, 0.0)]

    def show(self, colors):
        self.shown.append(dict(colors))

    def persist_colors(self, colors):
        self.persisted.append(dict(colors))

    def apply_settings(self, values):
        self.applied.append(dict(values))
        return {name: "bad value" for name, value in values.items() if value == "bad"}


class DaemonTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.tmp.name, "config.json")
        self.daemon = Daemon(cfg.ConfigStore(self.config_path),
                             cfg.StateStore(os.path.join(self.tmp.name, "state.json")))
        self.mouse = FakeMouse()
        self.daemon.devices["fake"] = self.mouse
        self.daemon._update_positions()

    def tearDown(self):
        self.tmp.cleanup()

    def config_with(self, **profiles):
        config = cfg.default_config()
        for name, devices in profiles.items():
            config["profiles"][name] = dict(cfg.default_profile(), devices=devices)
        return config

    def test_writes_the_default_config(self):
        with open(self.config_path) as f:
            self.assertEqual(json.load(f), cfg.default_config())

    def test_resting_frame_is_sent_once(self):
        self.daemon._render(100.0)
        self.daemon._render(100.5)
        self.assertEqual(self.mouse.shown, [{"z0": ORANGE}])
        self.assertEqual(self.daemon.get_frame(), {self.mouse.id: {"z0": "#ff4400"}})

    def test_a_wave_reaches_the_mouse(self):
        self.daemon._render(100.0)
        self.daemon.engine.press(14.0, 3.0, "keyboard@1-1", 100.0)   # key at the right edge
        self.daemon._idle = False
        self.daemon._render(100.35)    # the ring is ~5 keys away, where the mouse is
        self.assertGreater(self.mouse.shown[-1]["z0"][1], 150)
        self.daemon._render(103.0)
        self.assertEqual(self.mouse.shown[-1], {"z0": ORANGE})

    def test_simulate_press(self):
        self.daemon.simulate_press(self.mouse.id, "z0")
        self.daemon._render(time.monotonic())
        self.assertNotEqual(self.mouse.shown[-1]["z0"], ORANGE)
        with self.assertRaises(cfg.ConfigError):
            self.daemon.simulate_press(self.mouse.id, "nope")

    def test_invalid_config_is_rejected(self):
        before = self.daemon.get_config()
        with self.assertRaises(cfg.ConfigError):
            self.daemon.set_config({"profiles": {"A": {"lighting": {"brightness": 7}}}})
        self.assertIs(self.daemon.get_config(), before)

    def test_profile_switch_applies_settings_once(self):
        self.daemon.set_config(self.config_with(Work={"fake_mouse": {"polling_rate": 500}}))
        self.assertEqual(self.mouse.applied, [])          # Default is still active
        self.daemon.set_active_profile("Work")
        self.assertEqual(self.mouse.applied, [{"polling_rate": 500}])
        self.daemon.set_active_profile("Default")
        self.daemon.set_active_profile("Work")
        self.assertEqual(len(self.mouse.applied), 1)      # already on the device
        self.assertEqual(self.daemon.apply_device_settings(self.mouse.id), [])
        self.assertEqual(len(self.mouse.applied), 2)      # forced by the user

    def test_rejected_settings_are_reported_and_retried(self):
        config = self.config_with()
        config["profiles"]["Default"]["devices"] = {"fake_mouse": {"x": "bad", "y": 1}}
        self.daemon.set_config(config)
        self.assertEqual(self.daemon.apply_device_settings(self.mouse.id), ["Fake mouse x: bad value"])
        self.assertEqual(self.daemon.state["applied"]["fake_mouse"], {"y": 1})

    def test_resting_colors_are_saved_only_when_they_change(self):
        self.daemon._persist_lighting()
        self.daemon._persist_lighting()
        self.assertEqual(self.mouse.persisted, [{"z0": ORANGE}])
        config = cfg.default_config()
        config["profiles"]["Default"]["lighting"]["background"]["color"] = "#00ff00"
        self.daemon.set_config(config)
        self.assertIsNotNone(self.daemon._persist_at)
        self.daemon._persist_lighting()
        self.assertEqual(self.mouse.persisted[-1], {"z0": (0, 255, 0)})

    def test_signals(self):
        received = []
        self.daemon.add_listener(lambda name, payload: received.append((name, json.loads(payload))))
        self.daemon.set_config(self.config_with(Work={}))
        self.assertEqual(received[-1][0], "ConfigChanged")
        self.assertIn("Work", received[-1][1]["profiles"])

    def test_calls_from_other_threads_run_in_the_main_loop(self):
        result = {}
        caller = threading.Thread(target=lambda: result.update(config=self.daemon.submit(self.daemon.get_config)))
        caller.start()
        deadline = time.monotonic() + 2
        while caller.is_alive() and time.monotonic() < deadline:
            self.daemon._run_tasks()
            time.sleep(0.01)
        caller.join(1)
        self.assertEqual(result["config"]["active_profile"], "Default")


if __name__ == "__main__":
    unittest.main()
