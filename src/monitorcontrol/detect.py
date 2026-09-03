"""Discover connected displays from DRM sysfs.

This path does not need I2C permissions. `/sys/class/drm` already exposes
connector status and the EDID blob the kernel read at hotplug, so we can
name monitors even before DDC is set up.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from monitorcontrol.edid import Edid, EdidError, parse_edid

DEFAULT_DRM_ROOT = Path("/sys/class/drm")


@dataclass(frozen=True)
class Connector:
    sys_name: str
    connector_type: str
    status: str
    enabled: bool
    sys_path: Path
    edid: Edid | None

    @property
    def connected(self) -> bool:
        return self.status == "connected"

    @property
    def display_name(self) -> str:
        if self.edid:
            return self.edid.model
        return self.sys_name

    @property
    def identity(self) -> str:
        if self.edid:
            return self.edid.identity
        return self.sys_name


def _connector_type(sys_name: str) -> str:
    # card1-HDMI-A-1 -> HDMI-A, card0-eDP-1 -> eDP
    parts = sys_name.split("-", 1)
    if len(parts) < 2:
        return sys_name
    rest = parts[1]
    # Drop the trailing connector index.
    head, sep, tail = rest.rpartition("-")
    if sep and tail.isdigit():
        return head
    return rest


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def _read_edid(path: Path) -> Edid | None:
    try:
        blob = path.read_bytes()
    except OSError:
        return None
    if len(blob) < 128:
        return None
    try:
        return parse_edid(blob)
    except EdidError:
        return None


def iter_connectors(drm_root: Path = DEFAULT_DRM_ROOT) -> list[Connector]:
    """Return every DRM connector, connected or not."""
    if not drm_root.exists():
        return []

    connectors: list[Connector] = []
    for path in sorted(drm_root.iterdir()):
        status_path = path / "status"
        if not status_path.exists():
            continue
        sys_name = path.name
        connectors.append(
            Connector(
                sys_name=sys_name,
                connector_type=_connector_type(sys_name),
                status=_read_text(status_path) or "unknown",
                enabled=_read_text(path / "enabled") == "enabled",
                sys_path=path,
                edid=_read_edid(path / "edid"),
            )
        )
    return connectors


def connected_connectors(drm_root: Path = DEFAULT_DRM_ROOT) -> list[Connector]:
    return [c for c in iter_connectors(drm_root) if c.connected]
