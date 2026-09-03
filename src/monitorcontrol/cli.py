"""Command-line entry point.

`monitorcontrol` with no arguments starts the GTK app. Subcommands talk
to a running daemon over D-Bus when one exists, so keybinds show the OSD
the same way the macOS app does.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import TextIO

from monitorcontrol import APP_NAME, __version__
from monitorcontrol.controller import Controller
from monitorcontrol.service import FEATURE_BY_NAME, MonitorService

_FEATURE_BY_COMMAND = FEATURE_BY_NAME


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="monitorcontrol",
        description="Control brightness, contrast, and volume on any DDC/CI or laptop display.",
    )
    parser.add_argument(
        "--version", action="version", version=f"{APP_NAME} {__version__}"
    )
    parser.add_argument(
        "--display",
        "-d",
        help="Limit to one display (name, identity, or connector, substring ok)",
    )
    parser.add_argument(
        "--step", type=int, default=5, help="Percent step for up/down (default: 5)"
    )
    parser.add_argument(
        "--background",
        action="store_true",
        help="Start the daemon without showing the window (autostart)",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="List detected displays")
    sub.add_parser("gui", help="Open the control window")
    for name in _FEATURE_BY_COMMAND:
        feat = sub.add_parser(name, help=f"Get or change {name}")
        feat.add_argument(
            "value",
            nargs="?",
            default="get",
            help="up, down, get, or a percent 0-100",
        )
    keys = sub.add_parser("shortcuts", help="Install GNOME brightness keybindings")
    keys.add_argument("action", choices=["install", "uninstall", "status"])
    keys.add_argument(
        "--volume",
        action="store_true",
        help="Also bind XF86Audio* to the monitor speakers",
    )
    ext = sub.add_parser("extension", help="Install the GNOME Quick Settings slider")
    ext.add_argument("action", choices=["install", "uninstall", "status"])
    return parser


def _resolve_identity(rows: list[dict], needle: str | None) -> str | None:
    if needle is None:
        return None
    lowered = needle.lower()
    matches: list[str] = []
    for row in rows:
        haystack = " ".join(
            [
                str(row.get("name", "")),
                str(row.get("id", "")),
                str(row.get("connector", "")),
                str(row.get("connector_type", "")),
            ]
        ).lower()
        if lowered in haystack:
            matches.append(row["id"])
    if not matches:
        raise SystemExit(f"no display matched {needle!r}")
    if len(matches) > 1:
        raise SystemExit(
            f"{needle!r} matched more than one display; be more specific"
        )
    return matches[0]


def _print_list(service, out: TextIO) -> int:
    rows = service.list_displays()
    if not rows:
        out.write("No displays detected.\n")
        return 1
    for row in rows:
        out.write(f"{row['name']}\n")
        out.write(f"  id:        {row['id']}\n")
        out.write(f"  connector: {row.get('connector') or '—'}\n")
        out.write(f"  backend:   {row.get('kind', '')}\n")
        for name, percent in (row.get("features") or {}).items():
            out.write(f"  {name:<10} {percent}%\n")
        if row.get("warning"):
            out.write(f"  warning:   {row['warning']}\n")
        out.write("\n")
    return 0


def _run_feature(service, command: str, value: str, identity: str | None, step: int, out: TextIO) -> int:
    rows = [
        row
        for row in service.list_displays()
        if command in (row.get("features") or {})
        and (identity is None or row["id"] == identity)
    ]
    if not rows:
        where = f" on {identity}" if identity else ""
        raise SystemExit(f"no display supports {command}{where}")

    if value in {"get", "show", ""}:
        for row in rows:
            out.write(f"{row['name']}: {row['features'][command]}%\n")
        return 0

    if value in {"up", "+"}:
        changes = service.adjust(command, step, identity or "")
    elif value in {"down", "-"}:
        changes = service.adjust(command, -step, identity or "")
    else:
        try:
            percent = int(value)
        except ValueError as exc:
            raise SystemExit(f"expected up, down, or a percent, got {value!r}") from exc
        changes = []
        for row in rows:
            changes.extend(service.set_percent(row["id"], command, percent))

    for change in changes:
        out.write(f"{change['name']}: {change['percent']}%\n")
    return 0


def _run_shortcuts(action: str, *, volume: bool, store, program: str, out: TextIO) -> int:
    from monitorcontrol import shortcuts

    if action == "install":
        shortcuts.install(store, include_volume=volume, program=program)
        out.write("Installed GNOME brightness keybindings.\n")
        return 0
    if action == "uninstall":
        shortcuts.uninstall(store)
        out.write("Removed MonitorControl keybindings.\n")
        return 0
    paths = shortcuts.installed_paths(store)
    if not paths:
        out.write("No MonitorControl keybindings installed.\n")
        return 1
    for path in paths:
        out.write(f"{path}\n")
    return 0


def _run_extension(action: str, *, dest, out: TextIO) -> int:
    from monitorcontrol import gnome_extension

    if action == "install":
        path = gnome_extension.install(dest)
        out.write(f"Installed {path}\nEnable with: gnome-extensions enable {gnome_extension.UUID}\n")
        return 0
    if action == "uninstall":
        gnome_extension.uninstall(dest)
        out.write("Removed the Quick Settings extension.\n")
        return 0
    if gnome_extension.is_installed(dest):
        out.write(f"{gnome_extension.UUID} is installed.\n")
        return 0
    out.write("Quick Settings extension is not installed.\n")
    return 1


def run(
    argv: Sequence[str] | None = None,
    *,
    controller: Controller | None = None,
    service=None,
    out: TextIO = sys.stdout,
    launch_gui=None,
    shortcut_store=None,
    extension_root=None,
    program: str | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command in {None, "gui"}:
        if launch_gui is not None:
            return launch_gui()
        from monitorcontrol.app import run_app

        return run_app(background=bool(getattr(args, "background", False) and args.command is None))

    if args.command == "shortcuts":
        from monitorcontrol.paths import cli_command
        from monitorcontrol.shortcuts import gnome_store

        store = shortcut_store if shortcut_store is not None else gnome_store()
        return _run_shortcuts(
            args.action,
            volume=bool(getattr(args, "volume", False)),
            store=store,
            program=program or cli_command(),
            out=out,
        )
    if args.command == "extension":
        from pathlib import Path

        from monitorcontrol.gnome_extension import DEFAULT_ROOT

        dest = extension_root if extension_root is not None else DEFAULT_ROOT
        return _run_extension(args.action, dest=Path(dest), out=out)

    own = False
    if service is None:
        if controller is None:
            from monitorcontrol.dbus import session_client

            service = session_client()
        if service is None:
            own = controller is None
            if controller is None:
                controller = Controller(step=args.step)
                controller.refresh()
            else:
                controller.step = args.step
                if not controller.displays:
                    controller.refresh()
            service = MonitorService(controller)
    try:
        identity = _resolve_identity(service.list_displays(), args.display)
        if args.command == "list":
            return _print_list(service, out)
        return _run_feature(
            service, args.command, args.value, identity, args.step, out
        )
    finally:
        if own and controller is not None:
            controller.close()


def main() -> None:
    sys.exit(run())
