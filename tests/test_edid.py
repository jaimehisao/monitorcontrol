"""EDID parsing has to work for whatever is plugged in, not one model."""

from __future__ import annotations

import unittest
from pathlib import Path

from monitorcontrol.edid import EdidError, parse_edid

FIXTURES = Path(__file__).parent / "fixtures"


def _letters_to_mfg_bytes(letters: str) -> tuple[int, int]:
    a, b, c = (ord(ch) - 64 for ch in letters)
    word = (a << 10) | (b << 5) | c
    return word >> 8, word & 0xFF


def make_edid(
    *,
    manufacturer: str = "DEL",
    name: str = "U2720Q",
    serial: str = "ABC123",
    product_code: int = 0x1122,
    year: int = 2020,
) -> bytes:
    """Minimal EDID base block. Checksum is not computed; we don't require it."""
    data = bytearray(128)
    data[0:8] = bytes.fromhex("00ffffffffffff00")
    data[8], data[9] = _letters_to_mfg_bytes(manufacturer)
    data[10] = product_code & 0xFF
    data[11] = (product_code >> 8) & 0xFF
    data[17] = year - 1990
    data[21] = 60
    data[22] = 34

    def put_descriptor(offset: int, kind: int, text: str) -> None:
        data[offset : offset + 18] = bytes(18)
        data[offset + 3] = kind
        payload = (text.encode("ascii") + b"\n").ljust(13, b" ")[:13]
        data[offset + 5 : offset + 18] = payload

    put_descriptor(54, 0xFC, name)
    put_descriptor(72, 0xFF, serial)
    return bytes(data)


class ParseEdidTests(unittest.TestCase):
    def test_synthetic_dell(self) -> None:
        edid = parse_edid(make_edid())
        self.assertEqual(edid.manufacturer, "DEL")
        self.assertEqual(edid.name, "U2720Q")
        self.assertEqual(edid.serial_text, "ABC123")
        self.assertEqual(edid.model, "U2720Q")
        self.assertEqual(edid.identity, "DEL:U2720Q:ABC123")
        self.assertEqual(edid.year, 2020)
        self.assertEqual(edid.product_code, 0x1122)

    def test_synthetic_lg(self) -> None:
        edid = parse_edid(
            make_edid(manufacturer="GSM", name="LG ULTRAGEAR", serial="SN99")
        )
        self.assertEqual(edid.manufacturer, "GSM")
        self.assertEqual(edid.model, "LG ULTRAGEAR")
        self.assertEqual(edid.identity, "GSM:LG ULTRAGEAR:SN99")

    def test_fallback_model_when_name_descriptor_missing(self) -> None:
        blob = bytearray(make_edid(manufacturer="AUS", name="X", serial="Y"))
        blob[54 : 54 + 18] = bytes(18)  # wipe name descriptor
        edid = parse_edid(bytes(blob))
        self.assertIsNone(edid.name)
        self.assertEqual(edid.model, "AUS-1122")
        self.assertEqual(edid.manufacturer, "AUS")

    def test_identity_without_serial(self) -> None:
        blob = bytearray(make_edid(manufacturer="SAM", name="Odyssey", serial="Z"))
        blob[72 : 72 + 18] = bytes(18)
        blob[12:16] = b"\x00\x00\x00\x00"
        edid = parse_edid(bytes(blob))
        self.assertEqual(edid.identity, "SAM:Odyssey")

    def test_real_lenovo_p27h20_fixture(self) -> None:
        # One real blob so we know the parser survives vendor padding.
        blob = (FIXTURES / "p27h20.edid").read_bytes()
        edid = parse_edid(blob)
        self.assertEqual(edid.manufacturer, "LEN")
        self.assertEqual(edid.name, "P27h-20")
        self.assertEqual(edid.serial_text, "V9091HR5")
        self.assertEqual(edid.identity, "LEN:P27h-20:V9091HR5")
        self.assertGreaterEqual(len(blob), 128)

    def test_rejects_short_blob(self) -> None:
        with self.assertRaises(EdidError):
            parse_edid(b"\x00" * 16)

    def test_rejects_bad_header(self) -> None:
        blob = bytearray(make_edid())
        blob[0] = 0xFF
        with self.assertRaises(EdidError):
            parse_edid(bytes(blob))


if __name__ == "__main__":
    unittest.main()
