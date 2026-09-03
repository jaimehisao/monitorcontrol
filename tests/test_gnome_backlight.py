from __future__ import annotations

import unittest

from monitorcontrol.controller import Controller
from monitorcontrol.display import BackendKind, Display, FeatureState
from monitorcontrol.gnome_backlight import (
    NativeBrightnessFollower,
    apply_native_percent,
    attach_mutter,
    parse_backlight,
    slider_percent,
    strip_variants,
)
from monitorcontrol.vcp import Feature


class ParseTests(unittest.TestCase):
    def test_empty_desktop_payload(self) -> None:
        self.assertEqual(parse_backlight((7, [])), [])
        self.assertIsNone(slider_percent([]))
        self.assertEqual(parse_backlight(None), [])

    def test_laptop_entry(self) -> None:
        payload = (
            3,
            [
                {"connector": "eDP-1", "active": True, "value": 42},
                {"connector": "HDMI-1", "active": True},
            ],
        )
        entries = parse_backlight(payload)
        self.assertEqual(slider_percent(entries), 42)

    def test_skips_inactive_and_bad_values(self) -> None:
        entries = parse_backlight(
            [
                {"connector": "eDP-1", "active": False, "value": 10},
                {"connector": "DP-1", "active": True, "value": "nope"},
                {"connector": "DP-2", "active": True, "value": 80},
            ]
        )
        self.assertEqual(slider_percent(entries), 80)

    def test_clamps(self) -> None:
        self.assertEqual(slider_percent([{"active": True, "value": 140}]), 100)
        self.assertEqual(slider_percent([{"active": True, "value": -5}]), 0)


class FollowerTests(unittest.TestCase):
    def test_fires_once_per_change(self) -> None:
        seen: list[int] = []
        follower = NativeBrightnessFollower(seen.append)
        payload = (1, [{"connector": "eDP-1", "value": 30, "active": True}])
        self.assertEqual(follower.handle(payload), 30)
        self.assertEqual(follower.handle(payload), 30)
        self.assertEqual(seen, [30])
        payload = (2, [{"connector": "eDP-1", "value": 31, "active": True}])
        follower.handle(payload)
        self.assertEqual(seen, [30, 31])

    def test_empty_does_not_fire(self) -> None:
        seen: list[int] = []
        follower = NativeBrightnessFollower(seen.append)
        self.assertIsNone(follower.handle((1, [])))
        self.assertEqual(seen, [])


class ApplyNativeTests(unittest.TestCase):
    def test_copies_onto_ddc_and_updates_laptop_cache(self) -> None:
        writes: list[int] = []
        laptop = Display(
            identity="AUO:panel",
            name="Laptop",
            connector_sys_name="eDP-1",
            connector_type="eDP",
            kind=BackendKind.BACKLIGHT,
            features={Feature.BRIGHTNESS: FeatureState(50, 100)},
        )
        external = Display(
            identity="DEL:U2720Q",
            name="U2720Q",
            connector_sys_name="HDMI-1",
            connector_type="HDMI-A",
            kind=BackendKind.DDC,
            features={Feature.BRIGHTNESS: FeatureState(50, 100)},
            _set=lambda _f, value: writes.append(value),
        )
        ctrl = Controller(discover_fn=lambda: [laptop, external])
        ctrl.refresh()
        applied = apply_native_percent(ctrl, 20)
        self.assertEqual(applied, 1)
        self.assertEqual(laptop.features[Feature.BRIGHTNESS].percent, 20)
        self.assertEqual(external.features[Feature.BRIGHTNESS].percent, 20)
        self.assertEqual(writes, [20])

    def test_strip_and_attach(self) -> None:
        class Box:
            def __init__(self, inner):
                self._inner = inner

            def unpack(self):
                return self._inner

        nested = Box((1, [{"connector": Box("eDP-1"), "value": Box(33), "active": True}]))
        self.assertEqual(slider_percent(parse_backlight(nested)), 33)
        self.assertEqual(strip_variants(Box({"a": Box(1)})), {"a": 1})

        seen: list[int] = []
        follower = NativeBrightnessFollower(seen.append)

        class Proxy:
            def __init__(self):
                self.payload = (1, [{"connector": "eDP-1", "value": 10, "active": True}])
                self.cb = None

            def connect(self, _name, fn):
                self.cb = fn
                return 1

            def get_cached_property(self, _name):
                return self.payload

        proxy = Proxy()
        attach_mutter(follower, proxy)
        self.assertEqual(seen, [10])
        proxy.payload = (2, [{"connector": "eDP-1", "value": 11, "active": True}])
        proxy.cb(proxy, {"Backlight": True}, [])
        self.assertEqual(seen, [10, 11])
        proxy.cb(proxy, {"NightLightSupported": True}, [])
        self.assertEqual(seen, [10, 11])


if __name__ == "__main__":
    unittest.main()
