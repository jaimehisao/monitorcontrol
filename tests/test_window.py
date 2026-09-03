from __future__ import annotations

import os
import unittest

from monitorcontrol.controller import Controller
from monitorcontrol.display import BackendKind, Display, FeatureState
from monitorcontrol.vcp import Feature

HAS_DISPLAY = bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))


def _display() -> Display:
    return Display(
        identity="DEL:U2720Q:AA",
        name="U2720Q",
        connector_sys_name="card1-HDMI-A-1",
        connector_type="HDMI-A",
        kind=BackendKind.DDC,
        features={
            Feature.BRIGHTNESS: FeatureState(current=40, maximum=100),
            Feature.AUDIO_SPEAKER_VOLUME: FeatureState(current=10, maximum=100),
        },
        _set=lambda _f, _v: None,
    )


@unittest.skipUnless(HAS_DISPLAY, "no graphical session")
class WindowSmokeTests(unittest.TestCase):
    def test_builds_rows_for_each_feature(self) -> None:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw

        from monitorcontrol.window import ControlWindow

        Adw.init()
        app = Adw.Application(application_id="dev.monitorcontrol.TestWindow")
        app.register()
        controller = Controller(discover_fn=lambda: [_display()])
        controller.refresh()
        window = ControlWindow(app, controller)
        self.assertEqual(window.get_title(), "MonitorControl")
        self.assertEqual(len(window._scales), 2)
        self.assertIn(("DEL:U2720Q:AA", Feature.BRIGHTNESS), window._scales)
        called = []
        window.on_settings = lambda: called.append(True)
        window._on_settings(None)
        self.assertEqual(called, [True])
        scale = window._scales[("DEL:U2720Q:AA", Feature.BRIGHTNESS)]
        scale.set_value(22)
        empty = Controller(discover_fn=lambda: [])
        empty.refresh()
        window2 = ControlWindow(app, empty)
        self.assertEqual(window2._stack.get_visible_child_name(), "empty")
        window._on_copy_setup(window._banner)
        window.destroy()
        window2.destroy()


if __name__ == "__main__":
    unittest.main()
