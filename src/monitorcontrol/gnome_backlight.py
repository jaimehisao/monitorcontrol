"""Follow GNOME's own brightness slider when Mutter exposes a backlight.

On a laptop, Quick Settings and XF86MonBrightness* go through Mutter's
DisplayConfig Backlight property. We watch that and copy the percent onto
every DDC display (the macOS 'sync from the built-in panel' behaviour).

On a desktop the property is empty — there is no kernel backlight — so
the GNOME Shell extension injects the same Quick Settings slider instead.
"""

from __future__ import annotations

from typing import Any, Callable

from monitorcontrol.controller import Controller
from monitorcontrol.display import BackendKind
from monitorcontrol.vcp import Feature


def strip_variants(obj: Any) -> Any:
    """Unwrap GLib.Variant-like objects nested in the Backlight property."""
    unpack = getattr(obj, "unpack", None)
    if callable(unpack):
        return strip_variants(unpack())
    if isinstance(obj, dict):
        return {key: strip_variants(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [strip_variants(item) for item in obj]
    return obj


def parse_backlight(payload: Any) -> list[dict[str, Any]]:
    """Normalize the DisplayConfig Backlight property to a list of dicts.

    Wire type is `(uaa{sv})`: serial plus an array of entries. Each entry
    at least has `connector`. `value` is present only when GNOME can
    actually drive that panel.
    """
    if payload is None:
        return []
    payload = strip_variants(payload)
    entries: Any
    if isinstance(payload, (list, tuple)) and len(payload) == 2:
        entries = payload[1]
    else:
        entries = payload
    parsed: list[dict[str, Any]] = []
    if not entries:
        return parsed
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        item: dict[str, Any] = {}
        if "connector" in entry:
            item["connector"] = str(entry["connector"])
        if "active" in entry:
            item["active"] = bool(entry["active"])
        if "value" in entry:
            try:
                item["value"] = int(entry["value"])
            except (TypeError, ValueError):
                continue
        parsed.append(item)
    return parsed


def slider_percent(entries: list[dict[str, Any]]) -> int | None:
    """Percent shown by the GNOME Quick Settings brightness slider.

    GNOME 49+ can have one slider per backlight; we use the first active
    entry that actually has a value (the built-in panel, typically).
    """
    for entry in entries:
        if not entry.get("active", True):
            continue
        if "value" not in entry:
            continue
        return max(0, min(100, int(entry["value"])))
    return None


class NativeBrightnessFollower:
    """Call `on_percent` when GNOME's slider/keys change the backlight."""

    def __init__(self, on_percent: Callable[[int], None]) -> None:
        self._on_percent = on_percent
        self._last: int | None = None

    def handle(self, payload: Any) -> int | None:
        percent = slider_percent(parse_backlight(payload))
        if percent is None:
            return None
        if percent == self._last:
            return percent
        self._last = percent
        self._on_percent(percent)
        return percent


def apply_native_percent(controller: Controller, percent: int) -> int:
    """Copy GNOME's slider onto DDC displays; refresh the laptop cache."""
    applied = 0
    for display in controller.targets(Feature.BRIGHTNESS):
        if display.kind is BackendKind.BACKLIGHT:
            display.features[Feature.BRIGHTNESS] = display.features[
                Feature.BRIGHTNESS
            ].with_percent(percent)
            continue
        controller.set_percent(
            display.identity,
            Feature.BRIGHTNESS,
            percent,
            immediate=True,
            propagate=False,
        )
        applied += 1
    return applied


def attach_mutter(follower: NativeBrightnessFollower, proxy=None):
    """Subscribe to Mutter DisplayConfig.Backlight. `proxy` is injectable."""
    if proxy is None:
        from gi.repository import Gio

        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        proxy = Gio.DBusProxy.new_sync(
            bus,
            Gio.DBusProxyFlags.NONE,
            None,
            "org.gnome.Mutter.DisplayConfig",
            "/org/gnome/Mutter/DisplayConfig",
            "org.gnome.Mutter.DisplayConfig",
            None,
        )

    def on_changed(_proxy, changed, invalidated):
        names = []
        if changed is not None:
            try:
                names.extend(changed.keys())
            except Exception:
                names.extend(list(changed))
        if invalidated:
            names.extend(list(invalidated))
        if names and "Backlight" not in names:
            return
        follower.handle(proxy.get_cached_property("Backlight"))

    proxy.connect("g-properties-changed", on_changed)
    follower.handle(proxy.get_cached_property("Backlight"))
    return proxy
