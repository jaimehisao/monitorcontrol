from __future__ import annotations

import unittest
from unittest.mock import patch

from monitorcontrol.assetlib import is_frozen, package_data


class AssetlibTests(unittest.TestCase):
    def test_package_data_source_tree(self) -> None:
        css = package_data("data", "style.css")
        self.assertTrue(css.is_file())
        ext = package_data("data", "gnome-extension", "metadata.json")
        self.assertTrue(ext.is_file())
        self.assertFalse(is_frozen())

    def test_frozen_path(self) -> None:
        with patch("monitorcontrol.assetlib.is_frozen", return_value=True), patch(
            "monitorcontrol.assetlib.meipass"
        ) as mei:
            from pathlib import Path

            mei.return_value = Path("/tmp/_meipass")
            self.assertEqual(
                package_data("data", "style.css"),
                Path("/tmp/_meipass/monitorcontrol/data/style.css"),
            )


if __name__ == "__main__":
    unittest.main()
