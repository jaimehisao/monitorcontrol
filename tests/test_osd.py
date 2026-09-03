from __future__ import annotations

import os
import unittest

from monitorcontrol.controller import Change
from monitorcontrol.display import BackendKind, Display, FeatureState
from monitorcontrol.vcp import Feature

HAS_DISPLAY = bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))


@unittest.skipUnless(HAS_DISPLAY, "no graphical session")
class OsdSmokeTests(unittest.TestCase):
    def test_updates_percent(self) -> None:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw

        from monitorcontrol.osd import Osd

        Adw.init()
        app = Adw.Application(application_id="dev.monitorcontrol.TestOsd")
        app.register()
        osd = Osd(app)
        display = Display(
            identity="x",
            name="x",
            connector_sys_name="",
            connector_type="HDMI-A",
            kind=BackendKind.DDC,
            features={Feature.BRIGHTNESS: FeatureState(40, 100)},
        )
        osd.show_changes(
            [Change(display=display, feature=Feature.BRIGHTNESS, state=FeatureState(55, 100))]
        )
        self.assertEqual(osd.label.get_text(), "55%")
        self.assertEqual(osd.bar.get_value(), 55)
        osd.win.destroy()


if __name__ == "__main__":
    unittest.main()
