"""Command-line entry point.

`monitorcontrol` with no arguments starts the GTK app. Subcommands talk
to the same controller so keybinds and scripts work without the window.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import TextIO

from monitorcontrol import APP_NAME, __version__
from monitorcontrol.controller import Controller
from monitorcontrol.vcp import FEATURE_LABELS, Feature

_FEATURE_BY_COMMAND = {
    "brightness": Feature.BRIGHTNESS,
    "contrast": Feature.CONTRAST,
    "volume": Feature.AUDIO_SPEAKER_VOLUME,
}


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
    return parser


def _resolve_identity(controller: Controller, needle: str | None) -> str | None:
    if needle is None:
        return None
    lowered = needle.lower()
    matches: list[str] = []
    for display in controller.displays:
        haystack = " ".join(
            [
                display.name,
                display.identity,
                display.connector_sys_name,
                display.connector_type,
            ]
        ).lower()
        if lowered in haystack:
            matches.append(display.identity)
    if not matches:
        raise SystemExit(f"no display matched {needle!r}")
    if len(matches) > 1:
        raise SystemExit(
            f"{needle!r} matched more than one display; be more specific"
        )
    return matches[0]


def _print_list(controller: Controller, out: TextIO) -> int:
    if not controller.displays:
        out.write("No displays detected.\n")
        return 1
    for display in controller.displays:
        out.write(f"{display.name}\n")
        out.write(f"  id:        {display.identity}\n")
        out.write(f"  connector: {display.connector_sys_name or '—'}\n")
        out.write(f"  backend:   {display.kind.value}\n")
        if display.bus_number is not None:
            out.write(f"  i2c:       {display.bus_number}\n")
        if display.features:
            for feature, state in display.features.items():
                label = FEATURE_LABELS.get(feature, feature.name)
                out.write(f"  {label.lower():<10} {state.percent}% ({state.current}/{state.maximum})\n")
        if display.warning:
            out.write(f"  warning:   {display.warning}\n")
        out.write("\n")
    return 0


def _run_feature(
    controller: Controller,
    command: str,
    value: str,
    *,
    identity: str | None,
    out: TextIO,
) -> int:
    feature = _FEATURE_BY_COMMAND[command]
    targets = controller.targets(feature, identity)
    if not targets:
        where = f" on {identity}" if identity else ""
        raise SystemExit(f"no display supports {command}{where}")

    if value in {"get", "show", ""}:
        for display in targets:
            state = display.features[feature]
            out.write(f"{display.name}: {state.percent}%\n")
        return 0

    if value in {"up", "+"}:
        changes = controller.adjust(feature, identity=identity, immediate=True)
    elif value in {"down", "-"}:
        changes = controller.adjust(feature, -controller.step, identity=identity, immediate=True)
    else:
        try:
            percent = int(value)
        except ValueError as exc:
            raise SystemExit(f"expected up, down, or a percent, got {value!r}") from exc
        if identity is None:
            changes = []
            for display in targets:
                changes.extend(
                    controller.set_percent(
                        display.identity,
                        feature,
                        percent,
                        immediate=True,
                        propagate=False,
                    )
                )
        else:
            changes = controller.set_percent(
                identity, feature, percent, immediate=True
            )

    for change in changes:
        out.write(f"{change.display.name}: {change.state.percent}%\n")
    return 0


def run(
    argv: Sequence[str] | None = None,
    *,
    controller: Controller | None = None,
    out: TextIO = sys.stdout,
    launch_gui=None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command in {None, "gui"}:
        if launch_gui is not None:
            return launch_gui()
        from monitorcontrol.app import run_app

        return run_app()

    own = controller is None
    if controller is None:
        controller = Controller(step=args.step)
        controller.refresh()
    else:
        controller.step = args.step
        if not controller.displays:
            controller.refresh()
    try:
        identity = _resolve_identity(controller, args.display)
        if args.command == "list":
            return _print_list(controller, out)
        return _run_feature(
            controller, args.command, args.value, identity=identity, out=out
        )
    finally:
        if own:
            controller.close()


def main() -> None:
    sys.exit(run())
