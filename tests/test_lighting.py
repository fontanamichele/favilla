import copy
import math
import random
import unittest

from favilla import config, lighting


def keyglow_glow(x, y, waves, device, now, life=0.9, life_cross=1.8, speed=14.0, width=1.1):
    """The wave of the keyglow prototype, kept as the reference look."""
    glow = 0.0
    for wx, wy, t0, origin in waves:
        age = now - t0
        wave_life = life if origin == device else life_cross
        if age >= wave_life:
            continue
        d = math.hypot(x - wx, y - wy)
        ring = math.exp(-((d - age * speed) / width) ** 2)
        center = math.exp(-(d / 0.6) ** 2) * max(0.0, 1 - age / 0.25)
        glow = max(glow, max(ring, center) * (1 - age / wave_life) ** 1.5)
    return min(glow, 1.0)


def settings(**changes):
    lighting_settings = copy.deepcopy(config.DEFAULT_LIGHTING)
    for path, value in changes.items():
        section, key = path.split("__") if "__" in path else (None, path)
        (lighting_settings[section] if section else lighting_settings)[key] = value
    return lighting_settings


class ColorTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(lighting.parse_color("#ff4400"), (255, 68, 0))
        self.assertEqual(lighting.parse_color("FF4400"), (255, 68, 0))
        self.assertEqual(lighting.parse_color("#f40"), (255, 68, 0))
        self.assertEqual(lighting.parse_color([1, 2, 3]), (1, 2, 3))
        for bad in ("#ff44", "orange", [1, 2], [256, 0, 0], [True, 0, 0], None):
            with self.assertRaises(ValueError):
                lighting.parse_color(bad)

    def test_hex(self):
        self.assertEqual(lighting.to_hex((255, 68, 0)), "#ff4400")


class RippleTest(unittest.TestCase):
    def test_same_look_as_keyglow(self):
        rng = random.Random(42)
        ripple = lighting.Ripple("#ffffff")
        waves = []
        for _ in range(6):  # presses always happen before the frame being drawn
            wave = (rng.uniform(0, 20), rng.uniform(0, 5), rng.uniform(0, 1.0), rng.choice(["kb", "mouse"]))
            waves.append(wave)
            ripple.press(*wave[:2], wave[3], wave[2])
        for _ in range(500):
            x, y, now = rng.uniform(0, 20), rng.uniform(0, 5), rng.uniform(1.0, 3.0)
            device = rng.choice(["kb", "mouse"])
            self.assertAlmostEqual(ripple.glow(x, y, device, now),
                                   keyglow_glow(x, y, waves, device, now), places=12)

    def test_presses_expire(self):
        ripple = lighting.Ripple("#ffffff")
        ripple.press(1, 1, "kb", now=10.0)
        self.assertTrue(ripple.active(10.5))
        self.assertTrue(ripple.active(11.7))       # still reaching the other device
        self.assertFalse(ripple.active(11.81))


class EngineTest(unittest.TestCase):
    leds = [("k41", 0.5, 0.5), ("k44", 6.875, 4.5)]

    def test_static_is_not_animated(self):
        engine = lighting.LightingEngine(settings())
        self.assertFalse(engine.animated(0.0))
        self.assertEqual(engine.frame("kb", self.leds, 0.0),
                         {"k41": (255, 68, 0), "k44": (255, 68, 0)})

    def test_press_lights_the_key(self):
        engine = lighting.LightingEngine(settings())
        engine.press(0.5, 0.5, "kb", now=5.0)
        self.assertTrue(engine.animated(5.0))
        frame = engine.frame("kb", self.leds, 5.0)
        self.assertEqual(frame["k41"], (255, 255, 255))
        self.assertEqual(frame["k44"], (255, 68, 0))     # the ring has not got there yet
        self.assertFalse(engine.animated(7.0))
        self.assertEqual(engine.frame("kb", self.leds, 7.0)["k41"], (255, 68, 0))

    def test_brightness(self):
        engine = lighting.LightingEngine(settings(brightness=0.5))
        self.assertEqual(engine.frame("kb", self.leds, 0.0)["k41"], (127, 34, 0))

    def test_keyfade_stays_on_the_pressed_device(self):
        engine = lighting.LightingEngine(settings(reactive__effect="keyfade"))
        engine.press(19.0, 3.0, "mouse", now=1.0)
        self.assertEqual(engine.frame("kb", [("k1", 15.0, 3.0)], 1.0)["k1"], (255, 68, 0))
        self.assertEqual(engine.frame("mouse", [("z1", 19.0, 3.0)], 1.0)["z1"], (255, 255, 255))

    def test_no_reactive(self):
        engine = lighting.LightingEngine(settings(reactive__effect="none"))
        engine.press(0.5, 0.5, "kb", now=1.0)
        self.assertFalse(engine.animated(1.0))

    def test_animated_backgrounds(self):
        breathing = lighting.LightingEngine(settings(background__effect="breathing"))
        self.assertTrue(breathing.animated(0.0))
        self.assertEqual(breathing.resting(self.leds)["k41"], (255, 68, 0))
        self.assertLess(breathing.frame("kb", self.leds, 0.0)["k41"][0], 40)
        spectrum = lighting.LightingEngine(settings(background__effect="spectrum"))
        self.assertNotEqual(spectrum.frame("kb", self.leds, 0.0)["k41"],
                            spectrum.frame("kb", self.leds, 1.0)["k41"])

    def test_off(self):
        engine = lighting.LightingEngine(settings(background__effect="off"))
        self.assertEqual(engine.resting(self.leds)["k41"], (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
