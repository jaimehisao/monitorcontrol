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
            self.assertIn("_addIndicator", js)
            self.assertIn("display-brightness-symbolic", js)
            self.assertIn("this._icon.visible = this._sliders.size > 0", js)
            self.assertNotIn("XF86MonBrightnessUp", js)
            self.assertNotIn("StatusNotifierItem", js)
            self.assertNotIn("AppIndicator", js)
            mode = (dest / "extension.js").stat().st_mode & 0o777
            self.assertEqual(mode, 0o644)
            install(root)  # replace existing
            self.assertTrue(uninstall(root))
            self.assertFalse(is_installed(root))
            self.assertFalse(uninstall(root))

    def test_enable_calls_gnome_extensions(self) -> None:
        from monitorcontrol.gnome_extension import UUID, enable

        class Proc:
            returncode = 0

        class Settings:
            def __init__(self) -> None:
                self.values = ["other@example.com"]
                self.keys: list[str] = []

            def get_strv(self, key: str) -> list[str]:
                self.keys.append(key)
                return list(self.values)

            def set_strv(self, key: str, values: list[str]) -> None:
                self.keys.append(key)
                self.values = list(values)

        seen = []

        def runner(argv, **_kwargs):
            seen.append(argv)
            return Proc()

        settings = Settings()
        self.assertTrue(enable(runner=runner, settings=settings))
        self.assertEqual(seen[0][:3], ["gnome-extensions", "enable", UUID])
        self.assertIn(UUID, settings.values)
        self.assertEqual(settings.keys, ["enabled-extensions", "enabled-extensions"])

    def test_panel_icon_is_gnome_system_indicator(self) -> None:
        js = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "monitorcontrol"
            / "data"
            / "gnome-extension"
            / "extension.js"
        ).read_text(encoding="utf-8")
        self.assertIn("class Indicator extends SystemIndicator", js)
        self.assertLess(js.index("_addIndicator"), js.index("addExternalIndicator"))
        self.assertIn("icon_name = 'display-brightness-symbolic'", js)
        self.assertIn("this._icon.visible = false", js)

    def test_add_enabled_uuid_is_idempotent(self) -> None:
        from monitorcontrol.gnome_extension import UUID, add_enabled_uuid

        self.assertEqual(add_enabled_uuid([]), [UUID])
        self.assertEqual(add_enabled_uuid([UUID]), [UUID])


if __name__ == "__main__":
    unittest.main()
