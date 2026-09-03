from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from monitorcontrol.ddc import DdcClient, DdcPermissionError
from monitorcontrol.display import BackendKind, FeatureState, discover
from monitorcontrol.vcp import Feature
from tests.test_ddc import _reply
from tests.test_detect import _fake_drm
from tests.test_i2c import FakeTransport


def _write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")


def _opener(mapping: dict):
    def open_bus(number: int):
        spec = mapping.get(number, None)
        if spec is None:
            return None
        if spec == "perm":
            raise DdcPermissionError("denied")
        replies = {
            code: _reply(code=code, current=cur, maximum=mx)
            for code, (cur, mx) in spec.items()
        }
        return DdcClient(
            FakeTransport(replies),
            sleep=lambda _s: None,
            monotonic=lambda: 1000.0,
        )

    return open_bus


class FeatureStateTests(unittest.TestCase):
    def test_percent_and_delta(self) -> None:
        state = FeatureState(current=50, maximum=100)
        self.assertEqual(state.percent, 50)
        self.assertEqual(state.with_percent(80).current, 80)
        self.assertEqual(state.with_delta_percent(-10).current, 40)

    def test_non_100_max(self) -> None:
        state = FeatureState(current=24000, maximum=96000)
        self.assertEqual(state.percent, 25)
        self.assertEqual(state.with_percent(100).current, 96000)


class DiscoverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.drm = self.root / "drm"
        self.backlight = self.root / "backlight"
        self.i2c = self.root / "i2c"
        _fake_drm(self.root)
        # _fake_drm writes class/drm under root
        self.drm = self.root / "class" / "drm"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_laptop_plus_two_externals(self) -> None:
        _write(self.backlight / "intel_backlight" / "max_brightness", "96000\n")
        _write(self.backlight / "intel_backlight" / "actual_brightness", "48000\n")
        _write(self.backlight / "intel_backlight" / "brightness", "48000\n")
        _write(self.i2c / "i2c-7" / "name", "NVIDIA i2c adapter 1\n")
        _write(self.i2c / "i2c-8" / "name", "i915 gmbus dpb\n")
        _write(self.i2c / "i2c-2" / "name", "SMBus I801 adapter\n")

        hdmi = self.drm / "card1-HDMI-A-1"
        dp = self.drm / "card0-DP-3"
        (hdmi / "ddc").symlink_to(self.i2c / "i2c-7")
        (dp / "ddc").symlink_to(self.i2c / "i2c-8")

        displays = discover(
            drm_root=self.drm,
            backlight_root=self.backlight,
            i2c_class_root=self.i2c,
            opener=_opener(
                {
                    7: {0x10: (30, 100), 0x62: (10, 100)},
                    8: {0x10: (70, 100), 0x12: (50, 100)},
                }
            ),
        )
        by_name = {d.name: d for d in displays}
        self.assertEqual(set(by_name), {"Laptop Panel", "U2720Q", "27GL850"})

        laptop = by_name["Laptop Panel"]
        self.assertEqual(laptop.kind, BackendKind.BACKLIGHT)
        self.assertEqual(laptop.features[Feature.BRIGHTNESS].percent, 50)
        self.assertNotIn(Feature.CONTRAST, laptop.features)

        dell = by_name["U2720Q"]
        self.assertEqual(dell.kind, BackendKind.DDC)
        self.assertEqual(dell.bus_number, 7)
        self.assertEqual(set(dell.features), {Feature.BRIGHTNESS, Feature.AUDIO_SPEAKER_VOLUME})
        self.assertNotIn(Feature.CONTRAST, dell.features)

        lg = by_name["27GL850"]
        self.assertEqual(lg.kind, BackendKind.DDC)
        self.assertEqual(lg.bus_number, 8)
        self.assertIn(Feature.CONTRAST, lg.features)
        self.assertNotIn(Feature.AUDIO_SPEAKER_VOLUME, lg.features)

        dell.set_percent(Feature.BRIGHTNESS, 10)
        self.assertEqual(dell.features[Feature.BRIGHTNESS].percent, 10)

    def test_permission_still_lists_the_monitor(self) -> None:
        _write(self.i2c / "i2c-7" / "name", "AMDGPU DM i2c encoder 0\n")
        displays = discover(
            drm_root=self.drm,
            backlight_root=self.backlight,
            i2c_class_root=self.i2c,
            opener=_opener({7: "perm"}),
        )
        externals = [d for d in displays if d.connector_type != "eDP"]
        self.assertTrue(externals)
        for display in externals:
            self.assertEqual(display.kind, BackendKind.NONE)
            self.assertIn("i2c group", display.warning or "")

    def test_no_ddc_still_lists_hdmi(self) -> None:
        displays = discover(
            drm_root=self.drm,
            backlight_root=self.backlight,
            i2c_class_root=self.i2c,
            opener=_opener({}),
        )
        hdmi = next(d for d in displays if d.connector_type == "HDMI-A")
        self.assertEqual(hdmi.kind, BackendKind.NONE)
        self.assertIn("DDC/CI", hdmi.warning or "")
        self.assertEqual(hdmi.name, "U2720Q")


class DisplayObjectTests(unittest.TestCase):
    def test_get_refresh_close_and_percent(self) -> None:
        from monitorcontrol.display import BackendKind, Display, FeatureState
        from monitorcontrol.vcp import Feature

        reads = {"n": 0}

        def refresh(feature: Feature) -> FeatureState:
            reads["n"] += 1
            return FeatureState(3, 10)

        closed = []
        display = Display(
            identity="x",
            name="x",
            connector_sys_name="",
            connector_type="HDMI-A",
            kind=BackendKind.DDC,
            features={Feature.BRIGHTNESS: FeatureState(1, 10)},
            warning="heads up",
            _set=lambda _f, _v: None,
            _refresh=refresh,
            _close=lambda: closed.append(True),
        )
        self.assertEqual(display.get(Feature.BRIGHTNESS).current, 3)
        self.assertEqual(reads["n"], 1)
        display.close()
        display.close()
        self.assertEqual(closed, [True])
        with self.assertRaises(KeyError):
            display.get(Feature.CONTRAST)

    def test_open_linux_permission(self) -> None:
        from monitorcontrol.ddc import DdcError, DdcPermissionError
        from monitorcontrol.display import _open_linux
        from unittest.mock import patch

        with patch("monitorcontrol.i2c.LinuxI2cTransport", side_effect=DdcPermissionError("x")):
            with self.assertRaises(DdcPermissionError):
                _open_linux(1)
        with patch("monitorcontrol.i2c.LinuxI2cTransport", side_effect=DdcError("no")):
            self.assertIsNone(_open_linux(1))


class IsolatedDiscoverTests(unittest.TestCase):
    def test_ddc_without_drm_still_shows_up(self) -> None:
        with TemporaryDirectory() as raw:
            root = Path(raw)
            drm = root / "drm"
            drm.mkdir()
            i2c = root / "i2c"
            _write(i2c / "i2c-9" / "name", "NVIDIA i2c adapter 4\n")
            displays = discover(
                drm_root=drm,
                backlight_root=root / "bl",
                i2c_class_root=i2c,
                opener=_opener({9: {0x10: (5, 100)}}),
            )
            self.assertEqual(len(displays), 1)
            self.assertEqual(displays[0].name, "Display on i2c-9")
            self.assertEqual(displays[0].kind, BackendKind.DDC)


if __name__ == "__main__":
    unittest.main()
