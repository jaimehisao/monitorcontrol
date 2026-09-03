from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from monitorcontrol.ddc import DdcClient, DdcError, encode_set_vcp
from monitorcontrol.i2c import display_buses, iter_i2c_buses
from monitorcontrol.vcp import Feature
from tests.test_ddc import _reply


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class FakeTransport:
    def __init__(self, replies: dict[int, bytes] | None = None) -> None:
        self.writes: list[bytes] = []
        self.replies = replies or {}
        self.closed = False
        self._pending: bytes = b""

    def write(self, data: bytes) -> None:
        self.writes.append(data)
        if len(data) >= 4 and data[2] == 0x01:
            code = data[3]
            self._pending = self.replies.get(code, b"")

    def read(self, n: int) -> bytes:
        if not self._pending:
            raise DdcError("no reply programmed")
        data = self._pending[:n]
        self._pending = b""
        return data

    def close(self) -> None:
        self.closed = True


class DdcClientTests(unittest.TestCase):
    def test_probe_keeps_only_supported_features(self) -> None:
        transport = FakeTransport(
            {
                0x10: _reply(code=0x10, current=40, maximum=100),
                0x12: _reply(code=0x12, result=1),
                0x62: _reply(code=0x62, current=10, maximum=100),
            }
        )
        sleeps: list[float] = []
        client = DdcClient(transport, sleep=sleeps.append, monotonic=lambda: 1000.0)
        found = client.probe()
        self.assertEqual(set(found), {0x10, 0x62})
        self.assertEqual(found[0x10].current, 40)
        self.assertEqual(found[0x62].current, 10)
        self.assertNotIn(0x12, found)

    def test_set_sends_framed_packet(self) -> None:
        transport = FakeTransport()
        client = DdcClient(transport, sleep=lambda _s: None, monotonic=lambda: 1000.0)
        client.set(Feature.BRIGHTNESS, 50)
        self.assertEqual(transport.writes, [encode_set_vcp(0x10, 50)])

    def test_get_unknown_feature_is_an_error(self) -> None:
        transport = FakeTransport({0x10: _reply(code=0x10, result=1)})
        client = DdcClient(transport, sleep=lambda _s: None, monotonic=lambda: 1000.0)
        with self.assertRaises(DdcError):
            client.get(0x10)


class BusEnumerateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_skips_smbus_keeps_gpu_adapters(self) -> None:
        _write(self.root / "i2c-2" / "name", "SMBus I801 adapter at 0000:00:1f.4\n")
        _write(self.root / "i2c-3" / "name", "NVIDIA i2c adapter 1 at 1:00.0\n")
        _write(self.root / "i2c-4" / "name", "i915 gmbus dpb\n")
        _write(self.root / "i2c-5" / "name", "AMDGPU DM i2c encoder 0\n")
        buses = display_buses(self.root)
        names = {b.number: b.name for b in buses}
        self.assertNotIn(2, names)
        self.assertEqual(names[3], "NVIDIA i2c adapter 1 at 1:00.0")
        self.assertEqual(names[4], "i915 gmbus dpb")
        self.assertEqual(names[5], "AMDGPU DM i2c encoder 0")

    def test_empty_sysfs(self) -> None:
        self.assertEqual(iter_i2c_buses(self.root / "missing"), [])


if __name__ == "__main__":
    unittest.main()
