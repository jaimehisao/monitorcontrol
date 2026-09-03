from __future__ import annotations

import os
import unittest
from unittest.mock import patch

HAS_DISPLAY = bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))


@unittest.skipUnless(HAS_DISPLAY, "no graphical session")
class AppTests(unittest.TestCase):
    def test_run_app_and_startup(self) -> None:
        from monitorcontrol.app import Application, run_app
        from monitorcontrol.config import Config
        from monitorcontrol.controller import Controller
        from monitorcontrol.display import BackendKind, Display, FeatureState
        from monitorcontrol.vcp import Feature

        display = Display(
            identity="x",
            name="x",
            connector_sys_name="",
            connector_type="HDMI-A",
            kind=BackendKind.NONE,
            warning="need i2c",
        )
        bright = Display(
            identity="y",
            name="y",
            connector_sys_name="HDMI-1",
            connector_type="HDMI-A",
            kind=BackendKind.DDC,
            features={Feature.BRIGHTNESS: FeatureState(10, 100)},
            _set=lambda *_a: None,
        )

        with patch("monitorcontrol.app.export_session"), patch(
            "monitorcontrol.app.own_bus_name"
        ), patch("monitorcontrol.app.attach_mutter"), patch.object(
            Application, "run", return_value=0
        ):
            self.assertEqual(run_app(background=True), 0)

        from gi.repository import Adw

        Adw.init()
        with patch("monitorcontrol.app.export_session"), patch(
            "monitorcontrol.app.own_bus_name"
        ), patch("monitorcontrol.app.attach_mutter"):
            app = Application(show_window=False, config=Config(step=7, sync=True))
            app.register()

            def fake_discover():
                return [display, bright]

            with patch("monitorcontrol.app.Controller", return_value=Controller(discover_fn=fake_discover, step=7, sync=True)):
                app.do_startup()
            # do_startup already constructed a real Controller; rebuild window path
            app.controller = Controller(discover_fn=fake_discover)
            app.controller.refresh()
            app.do_activate()
            self.assertIsNotNone(app.win)
            app.win.on_settings = lambda: None
            app.win._on_settings(None)
            app.win._on_refresh(None)
            scale = next(iter(app.win._scales.values()))
            scale.set_value(40)
            app.do_shutdown()


if __name__ == "__main__":
    unittest.main()
