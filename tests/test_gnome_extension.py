from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from monitorcontrol.gnome_extension import UUID, install, is_installed, uninstall


class ExtensionInstallTests(unittest.TestCase):
    def test_copies_metadata_and_js(self) -> None:
        with TemporaryDirectory() as raw:
            root = Path(raw)
            dest = install(root)
            self.assertTrue(is_installed(root))
            self.assertEqual(dest.name, UUID)
            meta = json.loads((dest / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["uuid"], UUID)
            self.assertIn("50", meta["shell-version"])
            js = (dest / "extension.js").read_text(encoding="utf-8")
            self.assertIn("QuickSlider", js)
            self.assertIn("addExternalIndicator", js)
            self.assertNotIn("XF86MonBrightnessUp", js)
            install(root)  # replace existing
            self.assertTrue(uninstall(root))
            self.assertFalse(is_installed(root))
            self.assertFalse(uninstall(root))

    def test_enable_calls_gnome_extensions(self) -> None:
        from monitorcontrol.gnome_extension import UUID, enable

        class Proc:
            returncode = 0

        seen = []

        def runner(argv, **_kwargs):
            seen.append(argv)
            return Proc()

        self.assertTrue(enable(runner=runner))
        self.assertEqual(seen[0][:3], ["gnome-extensions", "enable", UUID])


if __name__ == "__main__":
    unittest.main()
