from __future__ import annotations

import io
import unittest

from monitorcontrol.cli import build_parser, run
from monitorcontrol.controller import Controller
from monitorcontrol.display import BackendKind, Display, FeatureState
from monitorcontrol.vcp import Feature


def _display(identity: str, name: str, *, volume: bool = False) -> Display:
    writes: list[tuple[Feature, int]] = []

    def setter(feature: Feature, value: int) -> None:
        writes.append((feature, value))

    features = {Feature.BRIGHTNESS: FeatureState(current=40, maximum=100)}
    if volume:
        features[Feature.AUDIO_SPEAKER_VOLUME] = FeatureState(current=15, maximum=100)
    display = Display(
        identity=identity,
        name=name,
        connector_sys_name="card1-HDMI-A-1",
        connector_type="HDMI-A",
        kind=BackendKind.DDC,
        features=features,
        _set=setter,
    )
    display.writes = writes  # type: ignore[attr-defined]
    return display


class ParserTests(unittest.TestCase):
    def test_list_and_brightness(self) -> None:
        ns = build_parser().parse_args(["list"])
        self.assertEqual(ns.command, "list")
        ns = build_parser().parse_args(["--display", "U2720Q", "brightness", "up"])
        self.assertEqual(ns.display, "U2720Q")
        self.assertEqual(ns.command, "brightness")
        self.assertEqual(ns.value, "up")
        ns = build_parser().parse_args(["brightness", "35"])
        self.assertEqual(ns.value, "35")


class RunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dell = _display("DEL:U2720Q:AA", "U2720Q", volume=True)
        self.lg = _display("GSM:27GL850:BB", "27GL850")
        self.ctrl = Controller(
            step=5,
            discover_fn=lambda: [self.dell, self.lg],
        )
        self.ctrl.refresh()
        self.out = io.StringIO()

    def test_list(self) -> None:
        code = run(["list"], controller=self.ctrl, out=self.out)
        self.assertEqual(code, 0)
        text = self.out.getvalue()
        self.assertIn("U2720Q", text)
        self.assertIn("27GL850", text)
        self.assertIn("volume", text)
        self.assertNotIn("27GL850:\n  volume", text)

    def test_brightness_up_all(self) -> None:
        run(["brightness", "up"], controller=self.ctrl, out=self.out)
        self.assertIn("U2720Q: 45%", self.out.getvalue())
        self.assertIn("27GL850: 45%", self.out.getvalue())
        self.assertEqual(self.dell.writes, [(Feature.BRIGHTNESS, 45)])

    def test_brightness_set_one_display_by_name(self) -> None:
        run(
            ["--display", "27GL", "brightness", "10"],
            controller=self.ctrl,
            out=self.out,
        )
        self.assertEqual(self.lg.features[Feature.BRIGHTNESS].percent, 10)
        self.assertEqual(self.dell.features[Feature.BRIGHTNESS].percent, 40)

    def test_volume_only_hits_monitors_with_speakers(self) -> None:
        run(["volume", "up"], controller=self.ctrl, out=self.out)
        self.assertIn("U2720Q: 20%", self.out.getvalue())
        self.assertNotIn("27GL850", self.out.getvalue())

    def test_unknown_display(self) -> None:
        with self.assertRaises(SystemExit):
            run(["--display", "nope", "brightness", "up"], controller=self.ctrl, out=self.out)

    def test_gui_uses_launcher_hook(self) -> None:
        called = []
        code = run(["gui"], controller=self.ctrl, out=self.out, launch_gui=lambda: called.append(1) or 0)
        self.assertEqual(code, 0)
        self.assertEqual(called, [1])


if __name__ == "__main__":
    unittest.main()
