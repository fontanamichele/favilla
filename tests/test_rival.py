"""Favilla must write exactly the bytes rivalcfg itself would write."""

import os
import unittest

from favilla.devices import rival

try:
    from rivalcfg import mouse as rival_mouse
    from rivalcfg import mouse_settings, usbhid
except ImportError:
    rival_mouse = None

AEROX_5_WIRELESS = 0x1852


@unittest.skipIf(rival_mouse is None, "rivalcfg is not installed")
class PacketParityTest(unittest.TestCase):
    def setUp(self):
        os.environ["RIVALCFG_DEBUG_NO_COMMAND_DELAY"] = "1"
        self.profile = rival.profile_for(0x1038, AEROX_5_WIRELESS)

    def rivalcfg_bytes(self, method, *args):
        fake = usbhid.FakeDevice()
        settings = mouse_settings.FakeMouseSettings(0x1038, AEROX_5_WIRELESS, self.profile)
        mouse = rival_mouse.Mouse(fake, self.profile, settings)
        getattr(mouse, method)(*args)
        return fake.bytes.getvalue()

    def favilla_bytes(self, name, value):
        info = self.profile["settings"][name]
        handler = getattr(rival.rival_handlers, info["value_type"])
        data = handler.process_value(info, rival._integers(value))
        return bytes([info["report_type"]]) + rival.build_packet(info, data)

    def test_settings(self):
        cases = [("sensitivity", "800, 1600", [800.0, 1600.0]),
                 ("polling_rate", 500, "500"),
                 ("sleep_timer", 10, 10.0),
                 ("dim_timer", 60, 60),
                 ("reactive_color", "#ffffff", "#ffffff"),
                 ("reactive_color", "off", "off"),
                 ("z1_color", "#ff4400", "#ff4400")]
        for name, rivalcfg_value, favilla_value in cases:
            with self.subTest(name=name, value=favilla_value):
                self.assertEqual(self.favilla_bytes(name, favilla_value),
                                 self.rivalcfg_bytes("set_" + name, rivalcfg_value))

    def test_save_command(self):
        info = self.profile["save_command"]
        self.assertEqual(bytes([info["report_type"]]) + rival.build_packet(info),
                         self.rivalcfg_bytes("save"))

    def test_led_frame_packet(self):
        info = self.profile["settings"]["z2_color"]
        self.assertEqual(rival.build_packet(info, (255, 68, 0)),
                         bytes([0x00, 0x61, 0x01, 0x01, 0xFF, 0x44, 0x00]))


@unittest.skipIf(rival_mouse is None, "rivalcfg is not installed")
class ProfileTest(unittest.TestCase):
    def test_names(self):
        wireless = rival.profile_for(0x1038, AEROX_5_WIRELESS)
        wired = rival.profile_for(0x1038, 0x1854)
        self.assertEqual(rival.display_name(wireless["name"]), "Aerox 5 Wireless")
        self.assertEqual(rival.model_key(wireless["name"]), "aerox_5_wireless")
        self.assertEqual(rival.model_key(wired["name"]), "aerox_5_wireless")
        self.assertIsNone(rival.profile_for(0x1038, 0x1624))   # the keyboard


if __name__ == "__main__":
    unittest.main()
