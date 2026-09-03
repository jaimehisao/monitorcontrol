"""Laptop panel brightness via `/sys/class/backlight`.

Built-in panels do not speak DDC/CI. The kernel already exposes a
backlight class device; we treat it as the brightness feature of that
display and leave contrast/volume alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_BACKLIGHT_ROOT = Path("/sys/class/backlight")


class BacklightError(Exception):
    """sysfs backlight node is missing or rejected a write."""


@dataclass
class Backlight:
    name: str
    path: Path
    maximum: int

    def get(self) -> int:
        for filename in ("actual_brightness", "brightness"):
            candidate = self.path / filename
            try:
                return _read_int(candidate)
            except BacklightError:
                continue
        raise BacklightError(f"no brightness node under {self.path}")

    def set(self, value: int) -> None:
        clamped = max(0, min(self.maximum, int(value)))
        try:
            (self.path / "brightness").write_text(str(clamped), encoding="ascii")
        except OSError as exc:
            raise BacklightError(f"cannot set {self.path}/brightness") from exc


def _read_int(path: Path) -> int:
    try:
        return int(path.read_text(encoding="ascii").strip())
    except (OSError, ValueError) as exc:
        raise BacklightError(f"cannot read {path}") from exc


def iter_backlights(root: Path = DEFAULT_BACKLIGHT_ROOT) -> list[Backlight]:
    if not root.exists():
        return []
    found: list[Backlight] = []
    for path in sorted(root.iterdir()):
        max_path = path / "max_brightness"
        if not max_path.exists():
            continue
        try:
            maximum = _read_int(max_path)
        except BacklightError:
            continue
        if maximum <= 0:
            continue
        found.append(Backlight(name=path.name, path=path, maximum=maximum))
    return found


def is_internal_connector(connector_type: str) -> bool:
    return connector_type.upper() in {"EDP", "LVDS", "DSI", "EDP-1"} or (
        connector_type.upper().startswith("EDP")
        or connector_type.upper().startswith("LVDS")
        or connector_type.upper().startswith("DSI")
    )
