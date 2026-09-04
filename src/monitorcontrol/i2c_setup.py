"""Grant DDC/CI access in one admin prompt, usable in the current session.

The udev rule uses systemd `uaccess` so the seated user gets an ACL without
waiting for a new login. We also chmod/setfacl the nodes that already exist
so the first run can talk to the monitor immediately.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from monitorcontrol.paths import is_frozen, user_binary

UDEV_RULE_NAME = "90-monitorcontrol-i2c.rules"
UDEV_RULE = (
    "# MonitorControl — DDC/CI over I2C for the active graphical session\n"
    'KERNEL=="i2c-[0-9]*", GROUP="i2c", MODE="0660", TAG+="uaccess"\n'
)
MODULES_LOAD = "i2c-dev\n"
DEFAULT_UDEV = Path("/etc/udev/rules.d") / UDEV_RULE_NAME
DEFAULT_MODULES = Path("/etc/modules-load.d/i2c-dev.conf")
DEFAULT_DEV = Path("/dev")


class SetupRunner(Protocol):
    def ensure_group(self, name: str) -> None: ...
    def add_user_to_group(self, user: str, group: str) -> None: ...
    def load_module(self, name: str) -> None: ...
    def reload_udev(self) -> None: ...
    def grant_now(self, device: Path, user: str, group: str) -> None: ...


class LinuxRunner:
    def ensure_group(self, name: str) -> None:
        subprocess.run(["groupadd", "-f", name], check=False)

    def add_user_to_group(self, user: str, group: str) -> None:
        subprocess.run(["usermod", "-aG", group, user], check=False)

    def load_module(self, name: str) -> None:
        subprocess.run(["modprobe", name], check=False)

    def reload_udev(self) -> None:
        subprocess.run(["udevadm", "control", "--reload-rules"], check=False)
        subprocess.run(["udevadm", "trigger"], check=False)

    def grant_now(self, device: Path, user: str, group: str) -> None:
        subprocess.run(["chgrp", group, str(device)], check=False)
        try:
            os.chmod(device, 0o660)
        except OSError:
            pass
        acl = subprocess.run(
            ["setfacl", "-m", f"u:{user}:rw", str(device)],
            check=False,
            capture_output=True,
        )
        if acl.returncode != 0:
            try:
                os.chmod(device, 0o666)
            except OSError:
                pass


def list_i2c_nodes(dev_root: Path = DEFAULT_DEV) -> list[Path]:
    return sorted(p for p in Path(dev_root).glob("i2c-*") if p.exists())


def privileged_setup(
    username: str,
    *,
    udev_path: Path = DEFAULT_UDEV,
    modules_path: Path = DEFAULT_MODULES,
    devices: list[Path] | None = None,
    runner: SetupRunner | None = None,
) -> None:
    if not username or username == "root":
        raise ValueError("refusing to configure I2C for an empty or root user")
    host = runner or LinuxRunner()
    udev_path.parent.mkdir(parents=True, exist_ok=True)
    udev_path.write_text(UDEV_RULE, encoding="utf-8")
    modules_path.parent.mkdir(parents=True, exist_ok=True)
    modules_path.write_text(MODULES_LOAD, encoding="utf-8")
    host.ensure_group("i2c")
    host.add_user_to_group(username, "i2c")
    host.load_module("i2c-dev")
    host.reload_udev()
    for device in devices if devices is not None else list_i2c_nodes():
        host.grant_now(device, username, "i2c")


def privileged_argv(username: str, *, executable: str | None = None) -> list[str]:
    """Command line for pkexec. Never includes a shell."""
    if is_frozen() or executable:
        prog = executable or sys.executable
        return [prog, "--privileged-setup", "--setup-user", username]
    return [
        sys.executable,
        "-m",
        "monitorcontrol",
        "--privileged-setup",
        "--setup-user",
        username,
    ]


def pkexec_grant(
    username: str,
    *,
    run=subprocess.run,
    executable: str | None = None,
) -> tuple[bool, str | None]:
    argv = ["pkexec", *privileged_argv(username, executable=executable)]
    try:
        proc = run(argv, check=False, capture_output=True, text=True)
    except OSError as exc:
        return False, f"could not start pkexec: {exc}"
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or f"pkexec exited {proc.returncode}").strip()
        return False, err
    return True, None


@dataclass(frozen=True)
class GrantRequest:
    username: str
    argv: list[str]


def grant_request(username: str | None = None) -> GrantRequest:
    user = username or os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    exe = None
    installed = user_binary()
    if installed.exists():
        exe = str(installed)
    return GrantRequest(username=user, argv=privileged_argv(user, executable=exe))
