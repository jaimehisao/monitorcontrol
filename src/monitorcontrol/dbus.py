"""D-Bus surface for the session daemon.

Methods take/return JSON strings so the GNOME Shell extension and the CLI
share one parser. `dispatch` is the testable core; Gio export is a thin wrap.

Signals (all one JSON string argument):

- `Changed`: a list of ``{"id", "feature", "percent"}`` records. Emitted once
  for every controller change, including sync and a rolled-back failed write.
- `OperationFailed`: the same record plus ``"error"``, for writes the hardware
  rejected.
- `DisplaysChanged`: the `ListDisplays` payload after a rescan.
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
    <signal name="DisplaysChanged">
      <arg type="s" name="json"/>
    </signal>
    <signal name="OperationFailed">
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


def changes_payload(changes, *, include_error: bool = False) -> str:
    from monitorcontrol.service import NAME_BY_FEATURE

    rows = []
    for change in changes:
        row = {
            "id": change.display.identity,
            "name": change.display.name,
            "feature": NAME_BY_FEATURE.get(change.feature, change.feature.name.lower()),
            "percent": change.state.percent,
        }
        if include_error and change.error:
            row["error"] = change.error
        rows.append(row)
    return json.dumps(rows)


def loads_changed(payload: str) -> list[dict[str, Any]]:
    """Records the Shell extension can apply. Malformed entries are skipped."""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    rows = data if isinstance(data, list) else [data]
    cleaned: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        identity = row.get("id")
        feature = row.get("feature")
        percent = row.get("percent")
        if not isinstance(identity, str) or not isinstance(feature, str):
            continue
        if isinstance(percent, bool) or not isinstance(percent, int):
            continue
        cleaned.append({"id": identity, "feature": feature, "percent": percent})
    return cleaned


def _glib_marshal(fn) -> None:
    from gi.repository import GLib

    GLib.idle_add(lambda: fn() or False)


class SessionExport:
    """Bus name, object registration, and change signals for one daemon."""

    def __init__(self, service: MonitorService, connection, registration_id: int, owner_id: int, marshal) -> None:
        self.service = service
        self.connection = connection
        self.registration_id = registration_id
        self.owner_id = owner_id
        self._marshal = marshal
        self._closed = False

    def on_changes(self, changes) -> None:
        if self._closed or not changes:
            return
        changed = changes_payload(changes)
        failed = [change for change in changes if change.error]
        failed_payload = changes_payload(failed, include_error=True) if failed else None

        def emit() -> None:
            if self._closed:
                return
            self._emit("Changed", changed)
            if failed_payload is not None:
                self._emit("OperationFailed", failed_payload)

        self._marshal(emit)

    def on_topology(self, _displays) -> None:
        if self._closed:
            return
        payload = json.dumps(self.service.list_displays())

        def emit() -> None:
            if not self._closed:
                self._emit("DisplaysChanged", payload)

        self._marshal(emit)

    def _emit(self, signal: str, payload: str) -> None:
        from gi.repository import GLib

        self.connection.emit_signal(
            None,
            OBJECT_PATH,
            INTERFACE,
            signal,
            GLib.Variant("(s)", (payload,)),
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        controller = self.service.controller
        controller.unsubscribe(self.on_changes)
        controller.unsubscribe(self.on_topology)
        self.connection.unregister_object(self.registration_id)
        if self.owner_id:
            from gi.repository import Gio

            Gio.bus_unown_name(self.owner_id)


def export_session(
    service: MonitorService,
    connection=None,
    *,
    own_name: bool | None = None,
    marshal=None,
) -> SessionExport:
    """Export the session object and keep the registration for shutdown.

    The real session bus is claimed only when the caller does not inject a
    connection. Tests pass a mock connection and do not own a bus name.
    """
    from gi.repository import Gio, GLib

    injected = connection is not None
    if connection is None:
        connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    if own_name is None:
        own_name = not injected
    info = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION_XML)
    iface = info.interfaces[0]

    def on_method(_conn, _sender, _path, _iface, method, params, invocation):
        try:
            payload = dispatch(service, method, params.unpack())
            invocation.return_value(GLib.Variant("(s)", (payload,)))
        except Exception as exc:  # noqa: BLE001 - D-Bus must not crash the app
            invocation.return_dbus_error(f"{INTERFACE}.Error", str(exc))

    registration = connection.register_object(OBJECT_PATH, iface, on_method, None, None)
    owner_id = 0
    try:
        if own_name:
            owner_id = own_bus_name()
        session = SessionExport(
            service,
            connection,
            registration,
            owner_id,
            marshal or _glib_marshal,
        )
        service.controller.subscribe(session.on_changes)
        service.controller.subscribe_topology(session.on_topology)
    except Exception:
        connection.unregister_object(registration)
        if owner_id:
            Gio.bus_unown_name(owner_id)
        raise
    return session


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
