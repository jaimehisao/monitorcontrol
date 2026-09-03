"""DDC/CI request and reply framing.

This is the VESA DDC/CI packet laid onto I2C address 0x37. It is not
vendor-specific. Encoding is split from the Linux I2C file descriptor so
the bytes can be tested without a monitor.
"""

from __future__ import annotations

import struct
import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol

HOST_ADDRESS = 0x51
DDCCI_ADDR = 0x37
PROTOCOL_FLAG = 0x80
GET_VCP = 0x01
GET_VCP_REPLY = 0x02
SET_VCP = 0x03
I2C_SLAVE = 0x0703

# Spec: wait at least 40ms after a get request before reading the reply.
GET_VCP_TIMEOUT_S = 0.04
# Spec: at least 50ms between messages to the same display.
CMD_RATE_S = 0.05


class DdcError(Exception):
    """A DDC/CI request failed or the reply was garbage."""


class DdcPermissionError(DdcError):
    """Opened an I2C node the user is not allowed to use."""


def checksum(data: bytes) -> int:
    value = 0
    for byte in data:
        value ^= byte
    return value


def _frame(body: bytes) -> bytes:
    framed = bytes([HOST_ADDRESS, len(body) | PROTOCOL_FLAG]) + body
    ck = checksum(bytes([DDCCI_ADDR << 1]) + framed)
    return framed + bytes([ck])


def encode_get_vcp(code: int) -> bytes:
    if not 0 <= code <= 0xFF:
        raise ValueError(f"VCP code out of range: {code}")
    return _frame(bytes([GET_VCP, code]))


def encode_set_vcp(code: int, value: int) -> bytes:
    if not 0 <= code <= 0xFF:
        raise ValueError(f"VCP code out of range: {code}")
    if not 0 <= value <= 0xFFFF:
        raise ValueError(f"VCP value out of range: {value}")
    hi = (value >> 8) & 0xFF
    lo = value & 0xFF
    return _frame(bytes([SET_VCP, code, hi, lo]))


@dataclass(frozen=True)
class VcpReply:
    code: int
    current: int
    maximum: int
    vcp_type: int


def decode_get_vcp_reply(packet: bytes, expected_code: int) -> VcpReply:
    """Parse a Get VCP Feature reply.

    Wire format after the I2C address byte has already been consumed by
    the kernel:

        source, length|0x80, 0x02, result, opcode, type, max16, current16, checksum
    """
    if len(packet) < 3:
        raise DdcError(f"short DDC reply ({len(packet)} bytes)")

    length = packet[1] & ~PROTOCOL_FLAG
    # header is 2 bytes; payload is `length` bytes plus a checksum
    expected = 2 + length + 1
    if len(packet) < expected:
        raise DdcError(f"truncated DDC reply: got {len(packet)}, want {expected}")

    header = packet[:2]
    payload = packet[2 : 2 + length]
    wire_checksum = packet[2 + length]
    calculated = checksum(header + payload)
    if wire_checksum != calculated and (wire_checksum ^ calculated) != 0:
        # Some panels XOR the host address into the checksum. Accept that
        # variant; reject anything else.
        alt = checksum(bytes([HOST_ADDRESS]) + header + payload)
        if wire_checksum != calculated and wire_checksum != alt:
            raise DdcError("DDC checksum mismatch")

    if length < 8:
        raise DdcError(f"DDC payload too small: {length}")

    reply_code, result_code, opcode, vcp_type, maximum, current = struct.unpack(
        ">BBBBHH", payload[:8]
    )
    if reply_code != GET_VCP_REPLY:
        raise DdcError(f"unexpected DDC reply code 0x{reply_code:02x}")
    if result_code == 1:
        raise DdcError(f"unsupported VCP code 0x{expected_code:02x}")
    if result_code != 0:
        raise DdcError(f"DDC result 0x{result_code:02x} for VCP 0x{expected_code:02x}")
    if opcode != expected_code:
        raise DdcError(
            f"DDC opcode mismatch: asked 0x{expected_code:02x}, got 0x{opcode:02x}"
        )
    return VcpReply(code=opcode, current=current, maximum=maximum, vcp_type=vcp_type)


class Transport(Protocol):
    def write(self, data: bytes) -> None: ...
    def read(self, n: int) -> bytes: ...
    def close(self) -> None: ...


class DdcClient:
    """One DDC/CI endpoint (usually one physical monitor)."""

    def __init__(
        self,
        transport: Transport,
        *,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._transport = transport
        self._sleep = sleep
        self._monotonic = monotonic
        self._last = 0.0
        self._lock = threading.Lock()

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> DdcClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _pace(self) -> None:
        wait = CMD_RATE_S - (self._monotonic() - self._last)
        if wait > 0:
            self._sleep(wait)

    def get(self, code: int) -> VcpReply:
        with self._lock:
            self._pace()
            self._transport.write(encode_get_vcp(code))
            self._sleep(GET_VCP_TIMEOUT_S)
            raw = self._transport.read(11)
            self._last = self._monotonic()
            return decode_get_vcp_reply(raw, code)

    def set(self, code: int, value: int) -> None:
        with self._lock:
            self._pace()
            self._transport.write(encode_set_vcp(code, value))
            self._last = self._monotonic()

    def probe(self, codes: tuple[int, ...] | None = None) -> dict[int, VcpReply]:
        """Return the subset of `codes` this display actually implements."""
        from monitorcontrol.vcp import USER_FEATURES

        found: dict[int, VcpReply] = {}
        for code in codes if codes is not None else USER_FEATURES:
            try:
                found[int(code)] = self.get(int(code))
            except DdcError:
                continue
        return found
