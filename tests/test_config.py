from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from monitorcontrol.config import Config, load, save


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.path = Path(self.tmp.name) / "config.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_roundtrip(self) -> None:
        save(Config(step=7, sync=True, autostart=True, shortcuts=True), self.path)
        loaded = load(self.path)
        self.assertEqual(loaded.step, 7)
        self.assertTrue(loaded.sync)
        self.assertTrue(loaded.autostart)
        self.assertTrue(loaded.shortcuts)
        self.assertFalse(loaded.volume_keys)

    def test_missing_file_is_defaults(self) -> None:
        self.assertEqual(load(self.path), Config())

    def test_corrupt_and_non_object(self) -> None:
        self.path.write_text("{", encoding="utf-8")
        self.assertEqual(load(self.path), Config())
        self.path.write_text("[]", encoding="utf-8")
        self.assertEqual(load(self.path), Config())

    def test_clamps_step(self) -> None:
        save(Config(step=999), self.path)
        self.assertEqual(load(self.path).step, 50)
        save(Config(step=0), self.path)
        self.assertEqual(load(self.path).step, 1)

    def test_ignores_unknown_keys(self) -> None:
        self.path.write_text(json.dumps({"step": 9, "nope": 1}), encoding="utf-8")
        self.assertEqual(load(self.path).step, 9)


if __name__ == "__main__":
    unittest.main()
