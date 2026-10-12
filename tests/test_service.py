from __future__ import annotations

import unittest

from monitorcontrol.controller import Controller
from monitorcontrol.display import BackendKind, Display, FeatureState
from monitorcontrol.service import feature_label, MonitorService, parse_feature
from monitorcontrol.vcp import Feature


def _display(identity: str, name: str, brightness: int = 40, volume: bool = False) -> Display:
    features = {Feature.BRIGHTNESS: FeatureState(brightness, 100)}
    if volume:
        features[Feature.AUDIO_SPEAKER_VOLUME] = FeatureState(10, 100)
    return Display(
        identity=identity,
        name=name,
        connector_sys_name="card1-HDMI-A-1",
        connector_type="HDMI-A",
        kind=BackendKind.DDC,
        features=features,
        _set=lambda _f, _v: None,
    )


class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dell = _display("DEL:U2720Q:AA", "U2720Q", 40, volume=True)
        self.lg = _display("GSM:27GL850:BB", "27GL850", 70)
        self.ctrl = Controller(discover_fn=lambda: [self.dell, self.lg])
        self.ctrl.refresh()
        self.svc = MonitorService(self.ctrl)

    def tearDown(self) -> None:
        self.ctrl.close()

    def test_list_payload(self) -> None:
        rows = self.svc.list_displays()
        by_name = {row["name"]: row for row in rows}
        self.assertEqual(by_name["U2720Q"]["features"]["brightness"], 40)
        self.assertEqual(by_name["U2720Q"]["confirmed"]["brightness"], 40)
        self.assertEqual(by_name["U2720Q"]["features"]["volume"], 10)
        self.assertNotIn("volume", by_name["27GL850"]["features"])
        self.assertTrue(by_name["U2720Q"]["controllable"])

    def test_set_and_adjust(self) -> None:
        changed = self.svc.set_percent("DEL:U2720Q:AA", "brightness", 25)
        self.assertEqual(changed[0]["percent"], 25)
        self.assertEqual(changed[0]["confirmed"], 40)
        bumped = self.svc.adjust("brightness", 5, "DEL:U2720Q:AA")
        self.assertEqual(bumped[0]["percent"], 30)
        all_up = self.svc.adjust("brightness", 10, "")
        percents = {row["name"]: row["percent"] for row in all_up}
        self.assertEqual(percents["U2720Q"], 40)
        self.assertEqual(percents["27GL850"], 80)

    def test_refresh_and_unknown_feature(self) -> None:
        rows = self.svc.refresh()
        self.assertEqual(len(rows), 2)
        with self.assertRaises(ValueError):
            parse_feature("gamma")
        with self.assertRaises(ValueError):
            self.svc.set_percent("DEL:U2720Q:AA", "gamma", 1)
        self.assertEqual(feature_label("brightness"), "Brightness")

    def test_session_api_coalesces_with_the_controller(self) -> None:
        writes: list[int] = []
        display = _display("DEL:U2720Q:AA", "U2720Q", 40)
        display._set = lambda _feature, value: writes.append(value)
        ctrl = Controller(discover_fn=lambda: [display], retry_sleep=lambda _delay: None)
        ctrl.refresh()
        svc = MonitorService(ctrl)
        try:
            for percent in range(100):
                svc.set_percent(display.identity, "brightness", percent)
            self.assertEqual(writes, [])
            ctrl.flush()
            self.assertEqual(writes, [99])
        finally:
            ctrl.close()


if __name__ == "__main__":
    unittest.main()
