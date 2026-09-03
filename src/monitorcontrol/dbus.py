"""D-Bus surface for the session daemon.

Methods take/return JSON strings so the GNOME Shell extension and the CLI
share one parser. `dispatch` is the testable core; Gio export is a thin wrap.
"""

from __future__ import annotations

import json
from typing import Any

from monitorcontrol import APP_ID
from monitorcontrol.service import MonitorService

BUS_NAME = APP_ID
OBJECT_PATH = "/dev/monitorcontrol/MonitorControl"
INTERFACE = "dev.monitorcontrol.MonitorControl"

INTROSPECTION_XML = f"""
<node>
  <interface name="{INTERFACE}">
    <method name="ListDisplays">
      <arg type="s" name="json" direction="out"/>
    </method>
    <method name="SetPercent">
      <arg type="s" name="identity" direction="in"/>
      <arg type="s" name="feature" direction="in"/>
      <arg type="i" name="percent" direction="in"/>
      <arg type="s" name="json" direction="out"/>
    </method>
    <method name="Adjust">
      <arg type="s" name="feature" direction="in"/>
      <arg type="i" name="delta" direction="in"/>
      <arg type="s" name="identity" direction="in"/>
      <arg type="s" name="json" direction="out"/>
    </method>
    <method name="Refresh">
      <arg type="s" name="json" direction="out"/>
    </method>
    <signal name="Changed">
      <arg type="s" name="json"/>
    </signal>
  </interface>
</node>
"""


def dispatch(service: MonitorService, method: str, args: tuple[Any, ...]) -> str:
    if method == "ListDisplays":
        return json.dumps(service.list_displays())
    if method == "SetPercent":
        identity, feature, percent = args
        return json.dumps(service.set_percent(identity, feature, int(percent)))
    if method == "Adjust":
        feature, delta, identity = args
        return json.dumps(service.adjust(feature, int(delta), identity or ""))
    if method == "Refresh":
        return json.dumps(service.refresh())
    raise ValueError(f"unknown method {method}")


def export_session(service: MonitorService, connection=None) -> int:
    """Register the object on a D-Bus connection. Returns the registration id."""
    from gi.repository import Gio, GLib

    if connection is None:
        connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    info = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION_XML)
    iface = info.interfaces[0]

    def on_method(_conn, _sender, _path, _iface, method, params, invocation):
        try:
            payload = dispatch(service, method, params.unpack())
            invocation.return_value(GLib.Variant("(s)", (payload,)))
        except Exception as exc:  # noqa: BLE001 - D-Bus must not crash the app
            invocation.return_dbus_error(f"{INTERFACE}.Error", str(exc))

    return connection.register_object(OBJECT_PATH, iface, on_method, None, None)


def own_bus_name(bus_name: str = BUS_NAME) -> int:
    from gi.repository import Gio

    return Gio.bus_own_name(
        Gio.BusType.SESSION,
        bus_name,
        Gio.BusNameOwnerFlags.NONE,
        None,
        None,
        None,
    )


def _variant_for(method: str, args: tuple) -> object | None:
    from gi.repository import GLib

    if method == "ListDisplays":
        return None
    if method == "Refresh":
        return None
    if method == "SetPercent":
        return GLib.Variant("(ssi)", args)
    if method == "Adjust":
        return GLib.Variant("(sis)", args)
    raise ValueError(method)


def session_client(timeout_ms: int = 400):
    """Return a JsonClient talking to a running daemon, or None."""
    from gi.repository import Gio, GLib

    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        proxy = Gio.DBusProxy.new_sync(
            bus,
            Gio.DBusProxyFlags.DO_NOT_AUTO_START,
            None,
            BUS_NAME,
            OBJECT_PATH,
            INTERFACE,
            None,
        )
    except GLib.Error:
        return None
    if proxy.get_name_owner() is None:
        return None

    def call(method: str, args: tuple) -> str:
        variant = _variant_for(method, args)
        result = proxy.call_sync(
            method, variant, Gio.DBusCallFlags.NONE, timeout_ms, None
        )
        return result.unpack()[0]

    return JsonClient(call)


class JsonClient:
    """Same methods as MonitorService, backed by dispatch() or a callable."""

    def __init__(self, call) -> None:
        self._call = call

    def list_displays(self) -> list:
        return json.loads(self._call("ListDisplays", ()))

    def set_percent(self, identity: str, feature: str, percent: int) -> list:
        return json.loads(self._call("SetPercent", (identity, feature, percent)))

    def adjust(self, feature: str, delta: int, identity: str = "") -> list:
        return json.loads(self._call("Adjust", (feature, delta, identity)))

    def refresh(self) -> list:
        return json.loads(self._call("Refresh", ()))
