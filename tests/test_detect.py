"""DRM connector discovery should list every plugged-in display."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from monitorcontrol.detect import connected_connectors, iter_connectors
from tests.test_edid import make_edid


def _write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")


def _fake_drm(root: Path) -> None:
    drm = root / "class" / "drm"
    # Two live monitors from different vendors, plus a dead port.
    hdmi = drm / "card1-HDMI-A-1"
    _write(hdmi / "status", "connected\n")
    _write(hdmi / "enabled", "enabled\n")
    _write(hdmi / "edid", make_edid(manufacturer="DEL", name="U2720Q", serial="AA"))

    dp = drm / "card0-DP-3"
    _write(dp / "status", "connected\n")
    _write(dp / "enabled", "enabled\n")
    _write(dp / "edid", make_edid(manufacturer="GSM", name="27GL850", serial="BB"))

    unused = drm / "card1-DP-1"
    _write(unused / "status", "disconnected\n")
    _write(unused / "enabled", "disabled\n")
    _write(unused / "edid", b"")

    edp = drm / "card0-eDP-1"
    _write(edp / "status", "connected\n")
    _write(edp / "enabled", "enabled\n")
    _write(edp / "edid", make_edid(manufacturer="AUO", name="Laptop Panel", serial="CC"))

    # Non-connector sysfs nodes must be ignored.
    _write(drm / "card1" / "uevent", "MAJOR=226\n")
    _write(drm / "version", "drm\n")


class DetectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _fake_drm(self.root)
        self.drm = self.root / "class" / "drm"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_iterates_every_connector(self) -> None:
        connectors = iter_connectors(self.drm)
        names = [c.sys_name for c in connectors]
        self.assertEqual(
            names,
            ["card0-DP-3", "card0-eDP-1", "card1-DP-1", "card1-HDMI-A-1"],
        )

    def test_connected_filters_disconnected_ports(self) -> None:
        live = connected_connectors(self.drm)
        self.assertEqual(
            {(c.display_name, c.connector_type) for c in live},
            {
                ("U2720Q", "HDMI-A"),
                ("27GL850", "DP"),
                ("Laptop Panel", "eDP"),
            },
        )

    def test_identity_is_per_monitor_not_per_port(self) -> None:
        live = {c.display_name: c.identity for c in connected_connectors(self.drm)}
        self.assertEqual(live["U2720Q"], "DEL:U2720Q:AA")
        self.assertEqual(live["27GL850"], "GSM:27GL850:BB")

    def test_missing_drm_root(self) -> None:
        self.assertEqual(iter_connectors(self.root / "nope"), [])

    def test_real_sysfs_if_present(self) -> None:
        # Smoke the live machine without assuming which monitors are attached.
        live = connected_connectors()
        for connector in live:
            self.assertTrue(connector.connected)
            self.assertTrue(connector.sys_name)
            self.assertTrue(connector.display_name)


if __name__ == "__main__":
    unittest.main()
