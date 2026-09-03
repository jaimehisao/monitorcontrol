"""DDC/CI framing is the same bytes for every MCCS monitor."""

from __future__ import annotations

import unittest

from monitorcontrol.ddc import (
    DdcError,
    decode_get_vcp_reply,
    encode_get_vcp,
    encode_set_vcp,
)
from monitorcontrol.vcp import Feature, USER_FEATURES


def _reply(
    *,
    code: int = 0x10,
    current: int = 50,
    maximum: int = 100,
    result: int = 0,
    reply_code: int = 0x02,
    checksum: int | None = None,
) -> bytes:
    payload = bytes(
        [
            reply_code,
            result,
            code,
            0x00,
            (maximum >> 8) & 0xFF,
            maximum & 0xFF,
            (current >> 8) & 0xFF,
            current & 0xFF,
        ]
    )
    header = bytes([0x6E, 0x80 | len(payload)])
    if checksum is None:
        value = 0
        for byte in header + payload:
            value ^= byte
        checksum = value
    return header + payload + bytes([checksum])


class FeatureTableTests(unittest.TestCase):
    def test_user_features_are_standard_mccs_codes(self) -> None:
        self.assertEqual(Feature.BRIGHTNESS, 0x10)
        self.assertEqual(Feature.CONTRAST, 0x12)
        self.assertEqual(Feature.AUDIO_SPEAKER_VOLUME, 0x62)
        self.assertEqual(
            USER_FEATURES,
            (
                Feature.BRIGHTNESS,
                Feature.CONTRAST,
                Feature.AUDIO_SPEAKER_VOLUME,
            ),
        )


class EncodeTests(unittest.TestCase):
    def test_get_brightness(self) -> None:
        # Host 0x51, length 2 | 0x80, get 0x01, VCP 0x10, xor checksum with 0x6E.
        self.assertEqual(encode_get_vcp(0x10), bytes.fromhex("51 82 01 10 ac"))

    def test_set_brightness_50(self) -> None:
        self.assertEqual(
            encode_set_vcp(0x10, 50), bytes.fromhex("51 84 03 10 00 32 9a")
        )

    def test_set_volume_uses_same_framing(self) -> None:
        packet = encode_set_vcp(Feature.AUDIO_SPEAKER_VOLUME, 20)
        self.assertEqual(packet[0], 0x51)
        self.assertEqual(packet[2], 0x03)
        self.assertEqual(packet[3], 0x62)
        self.assertEqual(int.from_bytes(packet[4:6], "big"), 20)

    def test_set_rejects_out_of_range(self) -> None:
        with self.assertRaises(ValueError):
            encode_set_vcp(0x10, 70000)
        with self.assertRaises(ValueError):
            encode_get_vcp(0x1FF)


class DecodeTests(unittest.TestCase):
    def test_brightness_reply(self) -> None:
        reply = decode_get_vcp_reply(_reply(), 0x10)
        self.assertEqual(reply.current, 50)
        self.assertEqual(reply.maximum, 100)
        self.assertEqual(reply.code, 0x10)

    def test_16bit_values(self) -> None:
        reply = decode_get_vcp_reply(
            _reply(current=0x0100, maximum=0x03E8), 0x10
        )
        self.assertEqual(reply.current, 256)
        self.assertEqual(reply.maximum, 1000)

    def test_unsupported_feature(self) -> None:
        with self.assertRaisesRegex(DdcError, "unsupported"):
            decode_get_vcp_reply(_reply(result=1), 0x10)

    def test_opcode_mismatch(self) -> None:
        with self.assertRaisesRegex(DdcError, "opcode mismatch"):
            decode_get_vcp_reply(_reply(code=0x12), 0x10)

    def test_bad_checksum(self) -> None:
        with self.assertRaisesRegex(DdcError, "checksum"):
            decode_get_vcp_reply(_reply(checksum=0x00), 0x10)

    def test_short_packet(self) -> None:
        with self.assertRaises(DdcError):
            decode_get_vcp_reply(b"\x6e\x82", 0x10)


if __name__ == "__main__":
    unittest.main()
