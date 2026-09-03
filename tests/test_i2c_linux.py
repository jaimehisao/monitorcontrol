from __future__ import annotations

import os
import stat
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from monitorcontrol.ddc import DdcError, DdcPermissionError
from monitorcontrol.i2c import (
    LinuxI2cTransport,
    i2c_device_available,
    iter_i2c_buses,
    permission_status,
)


class LinuxTransportTests(unittest.TestCase):
    def test_permission_and_ioctl_errors(self) -> None:
        with patch("monitorcontrol.i2c.os.open", side_effect=PermissionError("nope")):
            with self.assertRaises(DdcPermissionError):
                LinuxI2cTransport(3)
        with patch("monitorcontrol.i2c.os.open", return_value=7), patch(
            "monitorcontrol.i2c.fcntl.ioctl", side_effect=OSError("no slave")
        ), patch("monitorcontrol.i2c.os.close") as close:
            with self.assertRaises(DdcError):
                LinuxI2cTransport(3)
            close.assert_called_once_with(7)

    def test_open_oserror(self) -> None:
        with patch("monitorcontrol.i2c.os.open", side_effect=OSError("missing")):
            with self.assertRaises(DdcError):
                LinuxI2cTransport(1)

    def test_read_write_close(self) -> None:
        with patch("monitorcontrol.i2c.os.open", return_value=5), patch(
            "monitorcontrol.i2c.fcntl.ioctl"
        ), patch("monitorcontrol.i2c.os.write", return_value=3) as write, patch(
            "monitorcontrol.i2c.os.read", return_value=b"abc"
        ), patch("monitorcontrol.i2c.os.close") as close:
            transport = LinuxI2cTransport(4)
            transport.write(b"hi")
            self.assertEqual(transport.read(3), b"abc")
            transport.close()
            transport.close()
            write.assert_called()
            close.assert_called_once()

        with patch("monitorcontrol.i2c.os.open", return_value=5), patch(
            "monitorcontrol.i2c.fcntl.ioctl"
        ), patch("monitorcontrol.i2c.os.write", side_effect=OSError("w")), patch(
            "monitorcontrol.i2c.os.close"
        ):
            transport = LinuxI2cTransport(4)
            with self.assertRaises(DdcError):
                transport.write(b"x")
        with patch("monitorcontrol.i2c.os.open", return_value=5), patch(
            "monitorcontrol.i2c.fcntl.ioctl"
        ), patch("monitorcontrol.i2c.os.read", side_effect=OSError("r")), patch(
            "monitorcontrol.i2c.os.close"
        ):
            transport = LinuxI2cTransport(4)
            with self.assertRaises(DdcError):
                transport.read(1)

    def test_permission_status_and_names(self) -> None:
        with TemporaryDirectory() as raw:
            root = Path(raw)
            good = root / "i2c-1"
            bad = root / "i2c-2"
            good.write_bytes(b"")
            bad.write_bytes(b"")
            os.chmod(good, stat.S_IRUSR | stat.S_IWUSR)
            os.chmod(bad, 0)
            usable, blocked = permission_status(root)
            self.assertTrue(usable)
            self.assertTrue(any(p.name == "i2c-2" for p in blocked))
            self.assertTrue(i2c_device_available(1, dev_root=root))

            class_root = root / "class"
            (class_root / "not-a-bus").mkdir(parents=True)
            (class_root / "i2c-nope").mkdir()
            (class_root / "i2c-3").mkdir()
            buses = iter_i2c_buses(class_root)
            numbers = {b.number for b in buses}
            self.assertIn(3, numbers)
            self.assertTrue(any(b.name == "i2c-3" for b in buses))


if __name__ == "__main__":
    unittest.main()
