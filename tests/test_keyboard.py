import unittest

from favilla import layout
from favilla.devices import apex


class KeyReportTest(unittest.TestCase):
    def test_boot_report(self):
        report = bytes([0x02, 0, 0x04, 0x05, 0, 0, 0, 0])  # left shift + A + B
        self.assertEqual(apex.parse_key_report(report, set()), {0xE1, 0x04, 0x05})

    def test_boot_report_rollover_error_is_ignored(self):
        self.assertEqual(apex.parse_key_report(bytes([0, 0, 1, 1, 1, 1, 1, 1]), set()), set())

    def test_nkro_bitmap(self):
        report = bytearray(32)
        report[0x04 // 8] |= 1 << (0x04 % 8)
        report[0xE0 // 8] |= 1 << (0xE0 % 8)
        self.assertEqual(apex.parse_key_report(bytes(report), set()), {0x04, 0xE0})

    def test_unknown_report_keeps_state(self):
        self.assertEqual(apex.parse_key_report(b"\x01\x02", {7}), {7})


class ColorPacketTest(unittest.TestCase):
    def test_layout(self):
        packet = apex.build_color_packet(0x61, [(41, (255, 68, 0)), (44, (1, 2, 3))], 642)
        self.assertEqual(len(packet), 642)
        self.assertEqual(packet[:11], bytes([0, 0x61, 2, 41, 255, 68, 0, 44, 1, 2, 3]))
        self.assertEqual(set(packet[11:]), {0})

    def test_too_many_leds(self):
        with self.assertRaises(ValueError):
            apex.build_color_packet(0x61, [(1, (0, 0, 0))] * 200, 642)


class LayoutTest(unittest.TestCase):
    def test_rows_are_fifteen_units_wide(self):
        for lay in layout.LAYOUTS.values():
            for row in range(5):
                width = sum(r[2] for key in lay.keys for r in key.rects if r[1] == row)
                self.assertAlmostEqual(width, 15.0, msg=f"{lay.id} row {row}")

    def test_unique_leds(self):
        for lay in layout.LAYOUTS.values():
            leds = [key.led for key in lay.keys]
            self.assertEqual(len(leds), len(set(leds)), lay.id)

    def test_other_layout_keys_are_kept_but_hidden(self):
        keys = {key.led: visible for key, visible in layout.keys_for("ansi_us")}
        self.assertTrue(keys[49])            # ANSI backslash
        self.assertFalse(keys[50])           # ISO key next to Enter, still lit
        self.assertFalse(keys[100])
        self.assertEqual(len(keys), 63)

    def test_centers(self):
        keys = {key.led: key for key in layout.ISO_IT.keys}
        self.assertEqual(keys[41].center, (0.5, 0.5))
        self.assertEqual(keys[40].center, (14.25, 2.0))     # ISO Enter spans two rows
        self.assertEqual(keys[44].center, (6.875, 4.5))     # space bar


if __name__ == "__main__":
    unittest.main()
