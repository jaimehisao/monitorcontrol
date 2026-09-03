from __future__ import annotations

import unittest

from monitorcontrol.shortcuts import (
    BINDINGS,
    MemoryShortcutStore,
    command_for,
    install,
    installed_paths,
    uninstall,
)


class ShortcutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = MemoryShortcutStore(
            ["/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/other/"]
        )

    def test_install_brightness_leaves_other_bindings(self) -> None:
        added = install(self.store, program="monitorcontrol")
        self.assertEqual(len(added), 2)
        paths = self.store.get_paths()
        self.assertIn(
            "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/other/",
            paths,
        )
        up = [b for b in BINDINGS if b.key.endswith("up") and not b.volume][0]
        self.assertEqual(
            self.store.entries[up.path]["binding"], "XF86MonBrightnessUp"
        )
        self.assertEqual(
            self.store.entries[up.path]["command"],
            "monitorcontrol brightness up",
        )
        self.assertEqual(len(installed_paths(self.store)), 2)

    def test_volume_opt_in_and_opt_out(self) -> None:
        install(self.store, include_volume=True, program="mc")
        self.assertEqual(len(installed_paths(self.store)), 4)
        install(self.store, include_volume=False, program="mc")
        self.assertEqual(len(installed_paths(self.store)), 2)
        vol = [b for b in BINDINGS if b.volume][0]
        self.assertNotIn(vol.path, self.store.entries)

    def test_uninstall(self) -> None:
        install(self.store, program="mc")
        removed = uninstall(self.store)
        self.assertEqual(len(removed), 2)
        self.assertEqual(
            self.store.get_paths(),
            ["/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/other/"],
        )
        self.assertEqual(installed_paths(self.store), [])

    def test_gnome_store_adapter(self) -> None:
        from unittest.mock import MagicMock, patch

        from monitorcontrol.shortcuts import gnome_store

        inst = MagicMock()
        inst.get_strv.return_value = ["/p/"]
        with patch("gi.repository.Gio.Settings") as Settings:
            Settings.new.return_value = inst
            Settings.new_with_path.return_value = inst
            store = gnome_store()
            self.assertEqual(store.get_paths(), ["/p/"])
            store.set_paths(["/q/"])
            inst.set_strv.assert_called()
            store.write("/q/", "Name", "cmd", "XF86MonBrightnessUp")
            inst.set_string.assert_called()
            store.drop("/q/")
            inst.reset.assert_called()

    def test_command_for_uses_program(self) -> None:
        binding = BINDINGS[0]
        self.assertEqual(command_for(binding, "foo"), "foo brightness up")


if __name__ == "__main__":
    unittest.main()
