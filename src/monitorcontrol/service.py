"""Session API used by the CLI, keybinds, and the GNOME Quick Settings slider.

Keep this free of Gio so the protocol can be unit-tested. The GTK app wraps
it with a D-Bus object.
"""

from __future__ import annotations

from typing import Any

from monitorcontrol.controller import Controller
from monitorcontrol.vcp import FEATURE_LABELS, Feature

FEATURE_BY_NAME = {
    "brightness": Feature.BRIGHTNESS,
    "contrast": Feature.CONTRAST,
    "volume": Feature.AUDIO_SPEAKER_VOLUME,
}
NAME_BY_FEATURE = {feature: name for name, feature in FEATURE_BY_NAME.items()}


def parse_feature(name: str) -> Feature:
    try:
        return FEATURE_BY_NAME[name.lower()]
    except KeyError as exc:
        raise ValueError(f"unknown feature {name!r}") from exc


def display_payload(display) -> dict[str, Any]:
    features = {
        NAME_BY_FEATURE[feature]: state.percent
        for feature, state in display.features.items()
        if feature in NAME_BY_FEATURE
    }
    return {
        "id": display.identity,
        "name": display.name,
        "connector": display.connector_sys_name,
        "connector_type": display.connector_type,
        "kind": display.kind.value,
        "warning": display.warning or "",
        "controllable": display.controllable,
        "features": features,
    }


class MonitorService:
    """JSON-friendly facade over Controller."""

    def __init__(self, controller: Controller) -> None:
        self.controller = controller

    def list_displays(self) -> list[dict[str, Any]]:
        return [display_payload(display) for display in self.controller.displays]

    def set_percent(self, identity: str, feature: str, percent: int) -> list[dict[str, Any]]:
        changes = self.controller.set_percent(
            identity, parse_feature(feature), percent, immediate=True
        )
        return [
            {
                "id": change.display.identity,
                "name": change.display.name,
                "feature": NAME_BY_FEATURE[change.feature],
                "percent": change.state.percent,
            }
            for change in changes
        ]

    def adjust(self, feature: str, delta: int, identity: str = "") -> list[dict[str, Any]]:
        ident = identity or None
        changes = self.controller.adjust(
            parse_feature(feature), delta, identity=ident, immediate=True
        )
        return [
            {
                "id": change.display.identity,
                "name": change.display.name,
                "feature": NAME_BY_FEATURE[change.feature],
                "percent": change.state.percent,
            }
            for change in changes
        ]

    def refresh(self) -> list[dict[str, Any]]:
        self.controller.refresh()
        return self.list_displays()


def feature_label(name: str) -> str:
    return FEATURE_LABELS[parse_feature(name)]
