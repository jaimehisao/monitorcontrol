from __future__ import annotations

import json
import unittest

from monitorcontrol.controller import Controller
from monitorcontrol.dbus import JsonClient, dispatch
from monitorcontrol.display import BackendKind, Display, FeatureState
from monitorcontrol.service import MonitorService
from monitorcontrol.vcp import Feature


def _display() -> Display:
    return Display(
        identity="DEL:U2720Q:AA",
        name="U2720Q",
        connector_sys_name="HDMI-1",
        connector_type="HDMI-A",
        kind=BackendKind.DDC,
        features={Feature.BRIGHTNESS: FeatureState(40, 100)},
        _set=lambda _f, _v: None,
    )


class DispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ctrl = Controller(discover_fn=lambda: [_display()])
        self.ctrl.refresh()
        self.service = MonitorService(self.ctrl)
        self.client = JsonClient(lambda method, args: dispatch(self.service, method, args))

    def test_list_set_adjust_refresh(self) -> None:
        rows = self.client.list_displays()
        self.assertEqual(rows[0]["name"], "U2720Q")
        changed = self.client.set_percent("DEL:U2720Q:AA", "brightness", 12)
        self.assertEqual(changed[0]["percent"], 12)
        bumped = self.client.adjust("brightness", 8, "DEL:U2720Q:AA")
        self.assertEqual(bumped[0]["percent"], 20)
        rows = self.client.refresh()
        self.assertEqual(len(rows), 1)

    def test_unknown_method(self) -> None:
        with self.assertRaises(ValueError):
            dispatch(self.service, "Nope", ())

    def test_raw_adjust_empty_identity(self) -> None:
        payload = json.loads(dispatch(self.service, "Adjust", ("brightness", -5, "")))
        self.assertEqual(payload[0]["percent"], 35)


if __name__ == "__main__":
    unittest.main()
