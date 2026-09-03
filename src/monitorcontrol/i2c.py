"""Linux I2C access for DDC/CI.

Buses are discovered from sysfs. We skip SMBus adapters (those are
motherboards, not monitors) but do not special-case GPU vendors: NVIDIA,
AMD, Intel, and DisplayPort AUX all show up as i2c-* nodes.
"""

from __future__ import annotations

import fcntl
import os
from dataclasses import dataclass
from pathlib import Path

from monitorcontrol.ddc import DDCCI_ADDR, DdcError, DdcPermissionError, I2C_SLAVE

DEFAULT_I2C_DEV = Path("/sys/class/i2c-dev")
DEFAULT_DEV_ROOT = Path("/dev")


@dataclass(frozen=True)
class I2cBus:
    number: int
    name: str
    sys_path: Path

    @property
    def dev_path(self) -> Path:
        return DEFAULT_DEV_ROOT / f"i2c-{self.number}"

    @property
    def likely_display(self) -> bool:
        lower = self.name.lower()
        if "smbus" in lower:
            return False
        return True


class LinuxI2cTransport:
    """Raw /dev/i2c-N transport addressed at the DDC/CI slave (0x37)."""

    def __init__(self, bus_number: int, *, dev_root: Path = DEFAULT_DEV_ROOT) -> None:
        self.bus_number = bus_number
        self.path = Path(dev_root) / f"i2c-{bus_number}"
        try:
            self.fd = os.open(self.path, os.O_RDWR)
        except PermissionError as exc:
            raise DdcPermissionError(
                f"no permission to use {self.path}; add this user to the i2c group"
            ) from exc
        except OSError as exc:
            raise DdcError(f"unable to open {self.path}: {exc}") from exc
        try:
            fcntl.ioctl(self.fd, I2C_SLAVE, DDCCI_ADDR)
        except OSError as exc:
            os.close(self.fd)
            self.fd = -1
            raise DdcError(f"no DDC/CI slave on {self.path}") from exc

    def write(self, data: bytes) -> None:
        try:
            os.write(self.fd, data)
        except OSError as exc:
            raise DdcError(f"I2C write failed on {self.path}") from exc

    def read(self, n: int) -> bytes:
        try:
            return os.read(self.fd, n)
        except OSError as exc:
            raise DdcError(f"I2C read failed on {self.path}") from exc

    def close(self) -> None:
        fd = getattr(self, "fd", -1)
        if fd >= 0:
            os.close(fd)
            self.fd = -1


def _read_name(bus_dir: Path) -> str:
    for candidate in (bus_dir / "name", bus_dir / "device" / "name"):
        try:
            return candidate.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
    return bus_dir.name


def iter_i2c_buses(class_root: Path = DEFAULT_I2C_DEV) -> list[I2cBus]:
    if not class_root.exists():
        return []
    buses: list[I2cBus] = []
    for path in sorted(class_root.iterdir()):
        if not path.name.startswith("i2c-"):
            continue
        try:
            number = int(path.name.split("-", 1)[1])
        except ValueError:
            continue
        buses.append(I2cBus(number=number, name=_read_name(path), sys_path=path))
    return buses


def display_buses(class_root: Path = DEFAULT_I2C_DEV) -> list[I2cBus]:
    return [bus for bus in iter_i2c_buses(class_root) if bus.likely_display]


def i2c_device_available(bus_number: int, *, dev_root: Path = DEFAULT_DEV_ROOT) -> bool:
    path = Path(dev_root) / f"i2c-{bus_number}"
    return os.access(path, os.R_OK | os.W_OK)


def permission_status(dev_root: Path = DEFAULT_DEV_ROOT) -> tuple[bool, list[Path]]:
    """True if at least one /dev/i2c-* node is usable by this user."""
    blocked: list[Path] = []
    usable = False
    for path in sorted(Path(dev_root).glob("i2c-*")):
        if os.access(path, os.R_OK | os.W_OK):
            usable = True
        else:
            blocked.append(path)
    return usable, blocked
