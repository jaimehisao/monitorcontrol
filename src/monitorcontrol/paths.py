"""How to invoke this program from a keybind, autostart, or pkexec."""

from __future__ import annotations

import os
import shlex
import shutil
import sys
from pathlib import Path

import monitorcontrol
from monitorcontrol.assetlib import is_frozen


def package_src_root() -> Path:
    """Directory that must be on PYTHONPATH for `python -m monitorcontrol`."""
    return Path(monitorcontrol.__file__).resolve().parent.parent


def user_bin_dir() -> Path:
    return Path.home() / ".local" / "bin"


def user_binary() -> Path:
    return user_bin_dir() / "monitorcontrol"


def install_user_binary() -> Path:
    """Put a stable `monitorcontrol` on PATH so keys and autostart keep working."""
    dest = user_binary()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if is_frozen():
        src = Path(sys.executable).resolve()
        if src != dest.resolve():
            shutil.copy2(src, dest)
        dest.chmod(0o755)
        return dest
    wrapper = (
        "#!/bin/sh\n"
        f"export PYTHONPATH={shlex.quote(str(package_src_root()))}\n"
        f"exec {shlex.quote(sys.executable)} -m monitorcontrol \"$@\"\n"
    )
    dest.write_text(wrapper, encoding="utf-8")
    dest.chmod(0o755)
    return dest


def cli_command() -> str:
    dest = user_binary()
    if dest.exists():
        return str(dest)
    if is_frozen():
        return sys.executable
    installed = shutil.which("monitorcontrol")
    if installed:
        return installed
    return (
        f"env PYTHONPATH={shlex.quote(str(package_src_root()))} "
        f"{shlex.quote(sys.executable)} -m monitorcontrol"
    )


def current_username() -> str:
    return os.environ.get("USER") or os.environ.get("LOGNAME") or os.environ.get("SUDO_USER") or ""
