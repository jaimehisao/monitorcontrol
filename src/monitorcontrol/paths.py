"""How to invoke this program from a keybind or autostart file."""

from __future__ import annotations

import shlex
import shutil
import sys
from pathlib import Path

import monitorcontrol


def package_src_root() -> Path:
    """Directory that must be on PYTHONPATH for `python -m monitorcontrol`."""
    return Path(monitorcontrol.__file__).resolve().parent.parent


def cli_command() -> str:
    installed = shutil.which("monitorcontrol")
    if installed:
        return installed
    return (
        f"env PYTHONPATH={shlex.quote(str(package_src_root()))} "
        f"{shlex.quote(sys.executable)} -m monitorcontrol"
    )
