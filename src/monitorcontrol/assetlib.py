"""Locate bundled data files in a normal install and in a frozen binary."""

from __future__ import annotations

import sys
from importlib import resources
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))


def meipass() -> Path:
    return Path(sys._MEIPASS)  # type: ignore[attr-defined]


def package_data(*parts: str) -> Path:
    if is_frozen():
        return meipass().joinpath("monitorcontrol", *parts)
    return Path(resources.files("monitorcontrol")).joinpath(*parts)
