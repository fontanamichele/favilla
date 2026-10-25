import json
import os
import tempfile
import unittest

from favilla import config


class NormalizeTest(unittest.TestCase):
    def test_defaults_are_valid(self):
        self.assertEqual(config.normalize(config.default_config()), config.default_config())

    def test_missing_sections_are_filled(self):
        result = config.normalize({"profiles": {"Gaming": {"lighting": {"background": {"color": "#00f"}}}}})
        self.assertEqual(result["active_profile"], "Gaming")
        profile = result["profiles"]["Gaming"]
        self.assertEqual(profile["lighting"]["background"]["color"], "#0000ff")
        self.assertEqual(profile["lighting"]["background"]["effect"], "static")
        self.assertEqual(profile["lighting"]["reactive"], config.DEFAULT_LIGHTING["reactive"])
        self.assertEqual(profile["devices"], {})
        self.assertEqual(result["desk"], config.DEFAULT_DESK)

    def test_rejects_bad_values(self):
        bad_profiles = [
            {"lighting": {"background": {"color": "orange"}}},
            {"lighting": {"background": {"effect": "disco"}}},
            {"lighting": {"brightness": 2}},
            {"lighting": {"brightness": True}},
            {"lighting": {"reactive": {"speed": "fast"}}},
            {"devices": {"aerox_5_wireless": {"polling_rate": {"nested": 1}}}},
            {"devices": {"aerox_5_wireless": "fast"}},
        ]
        for profile in bad_profiles:
            with self.assertRaises(config.ConfigError, msg=profile):
                config.normalize({"profiles": {"P": profile}})
        with self.assertRaises(config.ConfigError):
            config.normalize({"profiles": {}})
        with self.assertRaises(config.ConfigError):
            config.normalize({"desk": {"keyboard_layout": "dvorak"}})
        with self.assertRaises(config.ConfigError):
            config.normalize({"profiles": {" ": {}}})
        with self.assertRaises(config.ConfigError):
            config.normalize({"profiles": {"A": {}, "A ": {}}})

    def test_active_profile_must_exist(self):
        result = config.normalize({"active_profile": "Nope", "profiles": {"A": {}, "B": {}}})
        self.assertEqual(result["active_profile"], "A")

    def test_device_settings_are_kept(self):
        settings = {"sensitivity": [800, 1600], "polling_rate": 1000, "reactive_color": "#ffffff"}
        result = config.normalize({"profiles": {"A": {"devices": {"aerox_5_wireless": settings}}}})
        self.assertEqual(result["profiles"]["A"]["devices"]["aerox_5_wireless"], settings)


class StoreTest(unittest.TestCase):
    def test_roundtrip_and_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "favilla", "config.json")
            store = config.ConfigStore(path)
            self.assertEqual(store.load(), config.default_config())

            changed = config.default_config()
            changed["profiles"]["Night"] = config.default_profile()
            changed["active_profile"] = "Night"
            store.save(changed)
            self.assertEqual(store.load(), changed)

            with open(path, "w") as f:
                f.write("{ not json")
            with self.assertLogs("favilla.config", level="ERROR"):
                self.assertEqual(store.load(), config.default_config())
            self.assertTrue(os.path.exists(path + ".broken"))

    def test_state_store(self):
        with tempfile.TemporaryDirectory() as root:
            store = config.StateStore(os.path.join(root, "state.json"))
            self.assertEqual(store.load(), {"applied": {}, "persisted": {}})
            store.save({"applied": {"m": {"polling_rate": 500}}, "persisted": {}})
            self.assertEqual(store.load()["applied"]["m"]["polling_rate"], 500)
            with open(os.path.join(root, "state.json"), "w") as f:
                json.dump([1, 2], f)
            self.assertEqual(store.load(), {"applied": {}, "persisted": {}})


if __name__ == "__main__":
    unittest.main()
