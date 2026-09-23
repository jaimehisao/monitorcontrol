"""Grant DDC/CI access in one admin prompt, usable in the current session.

The udev rule uses systemd `uaccess` so the seated user gets an ACL without
waiting for a new login. We also chmod/setfacl the nodes that already exist
so the first run can talk to the monitor immediately.
"""

from __future__ import annotations

import os
import pwd
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))

UDEV_RULE_NAME = "90-monitorcontrol-i2c.rules"
UDEV_RULE = (
    "# MonitorControl — DDC/CI over I2C for the active graphical session\n"
    'KERNEL=="i2c-[0-9]*", GROUP="i2c", MODE="0660", TAG+="uaccess"\n'
)
MODULES_LOAD = "i2c-dev\n"
DEFAULT_UDEV = Path("/etc/udev/rules.d") / UDEV_RULE_NAME
DEFAULT_MODULES = Path("/etc/modules-load.d/i2c-dev.conf")
DEFAULT_DEV = Path("/dev")
DEFAULT_POLICY = Path("/usr/share/polkit-1/actions/dev.monitorcontrol.MonitorControl.policy")
POLICY = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <vendor>MonitorControl</vendor>
  <action id="dev.monitorcontrol.pkexec.setup">
    <description>Grant access to display I2C devices</description>
    <message>Authentication is required so MonitorControl can control external displays</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/monitorcontrol</annotate>
    <annotate key="org.freedesktop.policykit.exec.argv1">--privileged-setup</annotate>
  </action>
</policyconfig>
"""


class SetupError(RuntimeError):
    """A privileged setup step failed. Device permissions were not weakened."""


class SetupRunner(Protocol):
    def ensure_group(self, name: str) -> None: ...
    def add_user_to_group(self, user: str, group: str) -> None: ...
    def load_module(self, name: str) -> None: ...
    def reload_udev(self) -> None: ...
    def grant_now(self, device: Path, user: str, group: str) -> None: ...


class LinuxRunner:
    def _run(self, argv: list[str]) -> None:
        try:
            subprocess.run(argv, check=True, capture_output=True, text=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            detail = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) else str(exc)
            raise SetupError(f"{argv[0]} failed: {detail or exc}") from exc

    def ensure_group(self, name: str) -> None:
        self._run(["groupadd", "-f", name])

    def add_user_to_group(self, user: str, group: str) -> None:
        self._run(["usermod", "-aG", group, user])

    def load_module(self, name: str) -> None:
        self._run(["modprobe", name])

    def reload_udev(self) -> None:
        self._run(["udevadm", "control", "--reload-rules"])
        self._run(["udevadm", "trigger"])

    def grant_now(self, device: Path, user: str, group: str) -> None:
        self._run(["chgrp", group, str(device)])
        try:
            os.chmod(device, 0o660)
        except OSError as exc:
            raise SetupError(f"could not set {device} to mode 0660: {exc}") from exc
        acl = subprocess.run(
            ["setfacl", "-m", f"u:{user}:rw", str(device)],
            check=False,
            capture_output=True,
            text=True,
        )
        if acl.returncode != 0:
            raise SetupError(
                f"could not grant {user} access to {device.name}; "
                "install acl, or log out and back in so the i2c group applies"
            )


def list_i2c_nodes(dev_root: Path = DEFAULT_DEV) -> list[Path]:
    return sorted(p for p in Path(dev_root).glob("i2c-*") if p.exists())


def validate_username(username: str) -> str:
    if (
        not username
        or username == "root"
        or username.startswith("-")
        or any(character in username for character in " /\n\t")
    ):
        raise ValueError("refusing to configure I2C for an empty, root, or unsafe user name")
    try:
        pwd.getpwnam(username)
    except KeyError as exc:
        raise ValueError(f"unknown user {username}") from exc
    return username


def privileged_setup(
    username: str,
    *,
    udev_path: Path = DEFAULT_UDEV,
    modules_path: Path = DEFAULT_MODULES,
    policy_path: Path | None = None,
    devices: list[Path] | None = None,
    runner: SetupRunner | None = None,
) -> None:
    username = validate_username(username)
    if policy_path is None and os.geteuid() == 0:
        policy_path = DEFAULT_POLICY
    host = runner or LinuxRunner()
    udev_path.parent.mkdir(parents=True, exist_ok=True)
    udev_path.write_text(UDEV_RULE, encoding="utf-8")
    modules_path.parent.mkdir(parents=True, exist_ok=True)
    modules_path.write_text(MODULES_LOAD, encoding="utf-8")
    if policy_path is not None:
        try:
            policy_path.parent.mkdir(parents=True, exist_ok=True)
            policy_path.write_text(POLICY, encoding="utf-8")
        except OSError as exc:
            raise SetupError(f"could not install the polkit policy: {exc}") from exc
    host.ensure_group("i2c")
    host.add_user_to_group(username, "i2c")
    host.load_module("i2c-dev")
    host.reload_udev()
    for device in devices if devices is not None else list_i2c_nodes():
        host.grant_now(device, username, "i2c")


def privileged_argv(username: str, *, executable: str | None = None) -> list[str]:
    """Command line for pkexec. Never includes a shell."""
    if _is_frozen() or executable:
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
    installed = Path.home() / ".local" / "bin" / "monitorcontrol"
    if installed.exists():
        exe = str(installed)
    return GrantRequest(username=user, argv=privileged_argv(user, executable=exe))
