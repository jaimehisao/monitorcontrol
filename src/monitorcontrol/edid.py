"""Parse the 128-byte EDID base block.

We only need identity: manufacturer, model name, serial. That is enough to
label a display in the UI and to keep settings attached when the cable
moves to another port. Extended blocks are ignored.
"""

from __future__ import annotations

from dataclasses import dataclass

EDID_HEADER = bytes.fromhex("00ffffffffffff00")
DESCRIPTOR_OFFSETS = (54, 72, 90, 108)
DESCRIPTOR_MONITOR_NAME = 0xFC
DESCRIPTOR_SERIAL = 0xFF


class EdidError(ValueError):
    """Raised when a blob is not a usable EDID base block."""


def _manufacturer_id(data: bytes) -> str:
    word = (data[8] << 8) | data[9]
    # Three 5-bit letters packed into 15 bits, 1 = 'A'.
    letters = (
        ((word >> 10) & 0x1F),
        ((word >> 5) & 0x1F),
        (word & 0x1F),
    )
    if any(n < 1 or n > 26 for n in letters):
        return "UNK"
    return "".join(chr(n + 64) for n in letters)


def _descriptor_text(block: bytes) -> str:
    # 13 bytes of text starting at offset 5, terminated by 0x0A, space padded.
    raw = block[5:18].split(b"\n", 1)[0].split(b"\x0a", 1)[0]
    return raw.replace(b"\x00", b"").decode("latin1", errors="replace").strip()


def _descriptors(data: bytes) -> dict[int, str]:
    found: dict[int, str] = {}
    for offset in DESCRIPTOR_OFFSETS:
        block = data[offset : offset + 18]
        if len(block) < 18:
            continue
        if block[0] != 0 or block[1] != 0:
            continue  # detailed timing, not a text descriptor
        kind = block[3]
        if kind in (DESCRIPTOR_MONITOR_NAME, DESCRIPTOR_SERIAL):
            text = _descriptor_text(block)
            if text:
                found[kind] = text
    return found


@dataclass(frozen=True)
class Edid:
    manufacturer: str
    product_code: int
    serial_number: int
    week: int
    year: int
    name: str | None
    serial_text: str | None
    width_cm: int
    height_cm: int
    raw: bytes

    @property
    def model(self) -> str:
        if self.name:
            return self.name
        return f"{self.manufacturer}-{self.product_code:04X}"

    @property
    def identity(self) -> str:
        """Stable id that survives the monitor moving to another connector."""
        serial = self.serial_text or (str(self.serial_number) if self.serial_number else "")
        if serial:
            return f"{self.manufacturer}:{self.model}:{serial}"
        return f"{self.manufacturer}:{self.model}"


def parse_edid(data: bytes) -> Edid:
    if len(data) < 128:
        raise EdidError(f"EDID too short: {len(data)} bytes")
    if data[:8] != EDID_HEADER:
        raise EdidError("not an EDID block")

    descriptors = _descriptors(data)
    return Edid(
        manufacturer=_manufacturer_id(data),
        product_code=data[10] | (data[11] << 8),
        serial_number=int.from_bytes(data[12:16], "little"),
        week=data[16],
        year=1990 + data[17],
        name=descriptors.get(DESCRIPTOR_MONITOR_NAME),
        serial_text=descriptors.get(DESCRIPTOR_SERIAL),
        width_cm=data[21],
        height_cm=data[22],
        raw=bytes(data[:128]),
    )
