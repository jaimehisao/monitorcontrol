"""Turn DRM connectors, DDC buses, and backlights into a display list.

Every connected connector becomes a display. How we drive it depends on
what the hardware actually offers:

- eDP/LVDS/DSI -> sysfs backlight
- everything else -> DDC/CI, probing VCP codes per monitor
- if DDC is missing or permission-denied, the display is still listed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from monitorcontrol.backlight import (
    DEFAULT_BACKLIGHT_ROOT,
    Backlight,
    is_internal_connector,
    iter_backlights,
)
from monitorcontrol.ddc import DdcClient, DdcError, DdcPermissionError
from monitorcontrol.detect import (
    DEFAULT_DRM_ROOT,
    Connector,
    connected_connectors,
)
from monitorcontrol.i2c import DEFAULT_I2C_DEV, display_buses
from monitorcontrol.vcp import USER_FEATURES, Feature


class BackendKind(str, Enum):
    DDC = "ddc"
    BACKLIGHT = "backlight"
    NONE = "none"


@dataclass(frozen=True)
class FeatureState:
    current: int
    maximum: int

    @property
    def percent(self) -> int:
        if self.maximum <= 0:
            return 0
        return max(0, min(100, round(100 * self.current / self.maximum)))

    def with_percent(self, percent: int) -> FeatureState:
        percent = max(0, min(100, int(percent)))
        current = round(percent * self.maximum / 100) if self.maximum else 0
        return FeatureState(current=current, maximum=self.maximum)

    def with_delta_percent(self, delta: int) -> FeatureState:
        return self.with_percent(self.percent + delta)


DdcOpener = Callable[[int], DdcClient | None]


@dataclass
class Display:
    identity: str
    name: str
    connector_sys_name: str
    connector_type: str
    kind: BackendKind
    features: dict[Feature, FeatureState] = field(default_factory=dict)
    warning: str | None = None
    bus_number: int | None = None
    _set: Callable[[Feature, int], None] | None = field(default=None, repr=False, compare=False)
    _refresh: Callable[[Feature], FeatureState] | None = field(
        default=None, repr=False, compare=False
    )
    _close: Callable[[], None] | None = field(default=None, repr=False, compare=False)

    def get(self, feature: Feature) -> FeatureState:
        if feature not in self.features:
            raise KeyError(f"{self.name} has no {feature.name}")
        if self._refresh is not None:
            self.features[feature] = self._refresh(feature)
        return self.features[feature]

    def set_raw(self, feature: Feature, value: int) -> FeatureState:
        state = self.features[feature]
        clamped = max(0, min(state.maximum, int(value)))
        if self._set is not None:
            self._set(feature, clamped)
        updated = FeatureState(current=clamped, maximum=state.maximum)
        self.features[feature] = updated
        return updated

    def set_percent(self, feature: Feature, percent: int) -> FeatureState:
        target = self.features[feature].with_percent(percent)
        return self.set_raw(feature, target.current)

    def adjust_percent(self, feature: Feature, delta: int) -> FeatureState:
        target = self.features[feature].with_delta_percent(delta)
        return self.set_raw(feature, target.current)

    @property
    def controllable(self) -> bool:
        return self.kind is not BackendKind.NONE and bool(self.features)

    def close(self) -> None:
        if self._close is not None:
            self._close()
            self._close = None


def _bus_from_ddc_symlink(connector_path: Path) -> int | None:
    ddc = connector_path / "ddc"
    if not ddc.exists():
        return None
    try:
        target = ddc.resolve() if ddc.is_symlink() else ddc
    except OSError:
        return None
    name = target.name
    if name.startswith("i2c-"):
        try:
            return int(name.split("-", 1)[1])
        except ValueError:
            return None
    return None


def _backlight_display(connector: Connector, backlight: Backlight) -> Display:
    current = backlight.get()

    def setter(feature: Feature, value: int) -> None:
        if feature is not Feature.BRIGHTNESS:
            raise KeyError(feature)
        backlight.set(value)

    def refresh(feature: Feature) -> FeatureState:
        if feature is not Feature.BRIGHTNESS:
            raise KeyError(feature)
        return FeatureState(current=backlight.get(), maximum=backlight.maximum)

    return Display(
        identity=connector.identity,
        name=connector.display_name,
        connector_sys_name=connector.sys_name,
        connector_type=connector.connector_type,
        kind=BackendKind.BACKLIGHT,
        features={
            Feature.BRIGHTNESS: FeatureState(current=current, maximum=backlight.maximum)
        },
        _set=setter,
        _refresh=refresh,
    )


def _uncontrolled(connector: Connector, warning: str) -> Display:
    return Display(
        identity=connector.identity,
        name=connector.display_name,
        connector_sys_name=connector.sys_name,
        connector_type=connector.connector_type,
        kind=BackendKind.NONE,
        warning=warning,
    )


def _ddc_display(
    connector: Connector | None,
    bus_number: int,
    client: DdcClient,
    probed: dict[int, object],
) -> Display:
    from monitorcontrol.ddc import VcpReply

    features: dict[Feature, FeatureState] = {}
    for code, reply in probed.items():
        assert isinstance(reply, VcpReply)
        try:
            feature = Feature(code)
        except ValueError:
            continue
        features[feature] = FeatureState(current=reply.current, maximum=reply.maximum)

    def setter(feature: Feature, value: int) -> None:
        client.set(int(feature), value)

    def refresh(feature: Feature) -> FeatureState:
        reply = client.get(int(feature))
        return FeatureState(current=reply.current, maximum=reply.maximum)

    if connector is not None:
        identity = connector.identity
        name = connector.display_name
        sys_name = connector.sys_name
        connector_type = connector.connector_type
    else:
        identity = f"i2c-{bus_number}"
        name = f"Display on i2c-{bus_number}"
        sys_name = ""
        connector_type = "DDC"

    warning = None
    if not features:
        warning = "DDC/CI responded but none of brightness, contrast, or volume are supported"

    return Display(
        identity=identity,
        name=name,
        connector_sys_name=sys_name,
        connector_type=connector_type,
        kind=BackendKind.DDC,
        features=features,
        warning=warning,
        bus_number=bus_number,
        _set=setter,
        _refresh=refresh,
        _close=client.close,
    )


def _open_linux(bus: int) -> DdcClient | None:
    from monitorcontrol.i2c import LinuxI2cTransport

    try:
        return DdcClient(LinuxI2cTransport(bus))
    except DdcPermissionError:
        raise
    except DdcError:
        return None


def discover(
    *,
    drm_root: Path = DEFAULT_DRM_ROOT,
    backlight_root: Path = DEFAULT_BACKLIGHT_ROOT,
    i2c_class_root: Path = DEFAULT_I2C_DEV,
    opener: DdcOpener | None = None,
) -> list[Display]:
    """Inventory every connected display we can see."""
    open_ddc = opener if opener is not None else _open_linux
    connectors = connected_connectors(drm_root)
    backlights = iter_backlights(backlight_root)
    displays: list[Display] = []

    internals = [c for c in connectors if is_internal_connector(c.connector_type)]
    externals = [c for c in connectors if c not in internals]

    leftover_backlights = list(backlights)
    for connector in internals:
        if leftover_backlights:
            displays.append(_backlight_display(connector, leftover_backlights.pop(0)))
        else:
            displays.append(
                _uncontrolled(
                    connector,
                    "laptop panel detected but no /sys/class/backlight device",
                )
            )

    permission_blocked = False
    claimed_buses: set[int] = set()

    def try_bus(bus_number: int) -> DdcClient | dict | None:
        nonlocal permission_blocked
        try:
            client = open_ddc(bus_number)
        except DdcPermissionError:
            permission_blocked = True
            return None
        except DdcError:
            return None
        if client is None:
            return None
        try:
            probed = client.probe(USER_FEATURES)
        except DdcError:
            client.close()
            return None
        return {"client": client, "probed": probed}

    for connector in externals:
        preferred = _bus_from_ddc_symlink(connector.sys_path)
        candidates: list[int] = []
        if preferred is not None:
            candidates.append(preferred)
        for bus in display_buses(i2c_class_root):
            if bus.number not in candidates:
                candidates.append(bus.number)

        attached = False
        for bus_number in candidates:
            if bus_number in claimed_buses:
                continue
            result = try_bus(bus_number)
            if not result:
                continue
            claimed_buses.add(bus_number)
            displays.append(
                _ddc_display(connector, bus_number, result["client"], result["probed"])
            )
            attached = True
            break
        if attached:
            continue
        if permission_blocked:
            warning = "DDC/CI needs I2C access — add this user to the i2c group"
        else:
            warning = "no DDC/CI on this connection (enable it in the monitor OSD if it has one)"
        displays.append(_uncontrolled(connector, warning))

    # DDC monitors that never matched a DRM connector still count.
    for bus in display_buses(i2c_class_root):
        if bus.number in claimed_buses:
            continue
        result = try_bus(bus.number)
        if not result:
            continue
        claimed_buses.add(bus.number)
        displays.append(
            _ddc_display(None, bus.number, result["client"], result["probed"])
        )

    return displays
