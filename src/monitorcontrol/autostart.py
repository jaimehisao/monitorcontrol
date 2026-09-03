"""XDG autostart so the daemon is running like the macOS menu-bar extra."""

from __future__ import annotations

from pathlib import Path

from monitorcontrol.paths import cli_command

DESKTOP_NAME = "dev.monitorcontrol.MonitorControl.desktop"
DEFAULT_DIR = Path.home() / ".config" / "autostart"


def desktop_contents(program: str | None = None) -> str:
    exec_cmd = f"{program or cli_command()} --background"
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=MonitorControl\n"
        "Comment=Control external display brightness from keys and Quick Settings\n"
        f"Exec={exec_cmd}\n"
        "Icon=dev.monitorcontrol.MonitorControl\n"
        "Terminal=false\n"
        "Categories=GTK;Settings;HardwareSettings;\n"
        "X-GNOME-Autostart-enabled=true\n"
        "StartupNotify=false\n"
    )


def install(directory: Path = DEFAULT_DIR, program: str | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / DESKTOP_NAME
    path.write_text(desktop_contents(program), encoding="utf-8")
    return path


def uninstall(directory: Path = DEFAULT_DIR) -> bool:
    path = directory / DESKTOP_NAME
    if not path.exists():
        return False
    path.unlink()
    return True


def is_installed(directory: Path = DEFAULT_DIR) -> bool:
    return (directory / DESKTOP_NAME).exists()
