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


def display_payload(display, controller: Controller | None = None) -> dict[str, Any]:
    features: dict[str, int] = {}
    confirmed: dict[str, int] = {}
    errors: dict[str, str] = {}
    for feature, state in display.features.items():
        name = NAME_BY_FEATURE.get(feature)
        if name is None:
            continue
        features[name] = state.percent
        if controller is None:
            confirmed[name] = state.percent
            continue
        confirmed[name] = controller.confirmed_percent(display.identity, feature)
        error = controller.feature_error(display.identity, feature)
        if error:
            errors[name] = error
    payload: dict[str, Any] = {
        "id": display.identity,
        "name": display.name,
        "connector": display.connector_sys_name,
        "connector_type": display.connector_type,
        "kind": display.kind.value,
        "warning": display.warning or "",
        "controllable": display.controllable,
        "features": features,
        "confirmed": confirmed,
    }
    if errors:
        payload["errors"] = errors
    return payload


def change_payload(change) -> dict[str, Any]:
    payload = {
        "id": change.display.identity,
        "name": change.display.name,
        "feature": NAME_BY_FEATURE[change.feature],
        "percent": change.state.percent,
        "confirmed": (change.confirmed or change.state).percent,
    }
    if change.error:
        payload["error"] = change.error
    return payload


class MonitorService:
    """JSON-friendly facade over Controller."""

    def __init__(self, controller: Controller) -> None:
        self.controller = controller

    def list_displays(self) -> list[dict[str, Any]]:
        return [
            display_payload(display, self.controller) for display in self.controller.displays
        ]

    def set_percent(self, identity: str, feature: str, percent: int) -> list[dict[str, Any]]:
        changes = self.controller.set_percent(identity, parse_feature(feature), percent)
        return [change_payload(change) for change in changes]

    def adjust(self, feature: str, delta: int, identity: str = "") -> list[dict[str, Any]]:
        ident = identity or None
        changes = self.controller.adjust(parse_feature(feature), delta, identity=ident)
        return [change_payload(change) for change in changes]

    def refresh(self) -> list[dict[str, Any]]:
        self.controller.refresh()
        return self.list_displays()


def feature_label(name: str) -> str:
    return FEATURE_LABELS[parse_feature(name)]
