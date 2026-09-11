from __future__ import annotations

import os
import unittest

HAS_DISPLAY = bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))


@unittest.skipUnless(HAS_DISPLAY, "no graphical session")
class FirstRunDialogTests(unittest.TestCase):
    def test_builds(self) -> None:
        import gi

        gi.require_version("Adw", "1")
        from gi.repository import Adw

        from monitorcontrol.firstrun import prompt_setup

        Adw.init()
        chosen = []
        prompt_setup(None, chosen.append)
        self.assertEqual(chosen, [])


if __name__ == "__main__":
    unittest.main()
