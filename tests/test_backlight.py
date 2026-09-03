from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from monitorcontrol.backlight import (
    BacklightError,
    is_internal_connector,
    iter_backlights,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class BacklightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_reads_and_sets_intel_backlight(self) -> None:
        node = self.root / "intel_backlight"
        _write(node / "max_brightness", "96000\n")
        _write(node / "actual_brightness", "48000\n")
        _write(node / "brightness", "48000\n")
        lights = iter_backlights(self.root)
        self.assertEqual(len(lights), 1)
        self.assertEqual(lights[0].name, "intel_backlight")
        self.assertEqual(lights[0].get(), 48000)
        lights[0].set(24000)
        self.assertEqual((node / "brightness").read_text(), "24000")

    def test_clamps_to_max(self) -> None:
        node = self.root / "amdgpu_bl0"
        _write(node / "max_brightness", "255\n")
        _write(node / "brightness", "10\n")
        light = iter_backlights(self.root)[0]
        light.set(999)
        self.assertEqual((node / "brightness").read_text(), "255")
        light.set(-3)
        self.assertEqual((node / "brightness").read_text(), "0")

    def test_ignores_empty_root(self) -> None:
        self.assertEqual(iter_backlights(self.root / "missing"), [])

    def test_internal_connector_types(self) -> None:
        self.assertTrue(is_internal_connector("eDP"))
        self.assertTrue(is_internal_connector("LVDS"))
        self.assertTrue(is_internal_connector("DSI"))
        self.assertFalse(is_internal_connector("HDMI-A"))
        self.assertFalse(is_internal_connector("DP"))
        self.assertFalse(is_internal_connector("DVI-D"))

    def test_missing_brightness_node(self) -> None:
        node = self.root / "broken"
        _write(node / "max_brightness", "100\n")
        light = iter_backlights(self.root)[0]
        with self.assertRaises(BacklightError):
            light.get()


if __name__ == "__main__":
    unittest.main()
