import os
import tempfile
import unittest

from favilla import hid

# Real report descriptors read from an Apex Pro Mini Wireless dongle (1038:1624)
# and an Aerox 5 Wireless dongle (1038:1852).
APEX_VENDOR = bytes.fromhex(
    "06c0ff0901a10106c1ff150026ff00750809f09540810209f19540910209f2968102b102c0")
APEX_BOOT = bytes.fromhex(
    "05010906a10175019508050719e029e7150025018102750895018101050719002aff0015002"
    "6ff00750895068100050819012903250175019503910295059101c0")
APEX_NKRO = bytes.fromhex(
    "05010906a101050719002aff001500250175019600018102050819012903250175019503910"
    "295059101c0")
AEROX_MOUSE = bytes.fromhex(
    "05010902a1010901a100a1020509190129081500250195087501810205010930093116018026"
    "ff7f75109502810609381581257f750895018106c0a102050c0a38021581257f750895018106"
    "c0a10206c1ff150026ff00750809f095058102c0c0c0")
AEROX_VENDOR = bytes.fromhex(
    "06c0ff0901a10106c1ff150026ff00750809f09540810209f19540910209f2960002b102c0")


class DescriptorTest(unittest.TestCase):
    def test_vendor_interface_reports(self):
        self.assertEqual(hid.report_lengths(APEX_VENDOR),
                         {("input", 0): 64, ("output", 0): 64, ("feature", 0): 641})
        self.assertEqual(hid.report_lengths(AEROX_VENDOR)[("feature", 0)], 512)

    def test_usages(self):
        self.assertEqual(hid.top_level_usage(APEX_VENDOR), (0xFFC0, 0x01))
        self.assertEqual(hid.top_level_usage(APEX_BOOT), (0x01, 0x06))
        self.assertEqual(hid.top_level_usage(AEROX_MOUSE), (0x01, 0x02))

    def test_keyboard_report_sizes(self):
        self.assertEqual(hid.report_lengths(APEX_BOOT)[("input", 0)], 8)
        self.assertEqual(hid.report_lengths(APEX_NKRO)[("input", 0)], 32)

    def test_mouse_report(self):
        self.assertEqual(hid.report_lengths(AEROX_MOUSE)[("input", 0)], 12)
        self.assertFalse(hid.uses_report_ids(AEROX_MOUSE))

    def test_report_id_detection(self):
        with_id = bytes.fromhex("05010902a1018502" "0509190129031500250195037501810295057501" "8103c0")
        self.assertTrue(hid.uses_report_ids(with_id))


class EnumerateTest(unittest.TestCase):
    def test_sysfs_layout(self):
        with tempfile.TemporaryDirectory() as root:
            entries = [("hidraw6", "1-9:1.3", "0003:1038:1624.0007", APEX_VENDOR),
                       ("hidraw9", "1-10:1.0", "0003:1038:1852.000A", AEROX_MOUSE),
                       ("hidraw2", "1-4:1.0", "0003:046D:C52B.0003", AEROX_MOUSE),
                       ("hidraw1", "", "0005:1038:1624.0001", APEX_VENDOR)]  # Bluetooth
            for name, interface, hid_dir, descriptor in entries:
                device = os.path.join(root, "devices", interface.split(":")[0] or "bt",
                                      interface or "bt0", hid_dir)
                os.makedirs(device)
                with open(os.path.join(device, "report_descriptor"), "wb") as f:
                    f.write(descriptor)
                os.makedirs(os.path.join(root, "class", name))
                os.symlink(device, os.path.join(root, "class", name, "device"))

            nodes = hid.enumerate_nodes(0x1038, sysfs=os.path.join(root, "class"))
            self.assertEqual([n.path for n in nodes], ["/dev/hidraw6", "/dev/hidraw9"])
            keyboard, mouse = nodes
            self.assertEqual((keyboard.product_id, keyboard.interface, keyboard.port),
                             (0x1624, 3, "1-9"))
            self.assertEqual((mouse.product_id, mouse.interface, mouse.port), (0x1852, 0, "1-10"))
            self.assertTrue(mouse.is_mouse)
            self.assertEqual(len(hid.enumerate_nodes(sysfs=os.path.join(root, "class"))), 3)


if __name__ == "__main__":
    unittest.main()
