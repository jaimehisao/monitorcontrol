from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from monitorcontrol.dbus import _variant_for, own_bus_name, session_client


class GioHelperTests(unittest.TestCase):
    def test_variant_for(self) -> None:
        self.assertIsNone(_variant_for("ListDisplays", ()))
        self.assertIsNone(_variant_for("Refresh", ()))
        setp = _variant_for("SetPercent", ("id", "brightness", 10))
        self.assertEqual(setp.unpack(), ("id", "brightness", 10))
        adj = _variant_for("Adjust", ("brightness", 5, ""))
        self.assertEqual(adj.unpack(), ("brightness", 5, ""))
        with self.assertRaises(ValueError):
            _variant_for("Nope", ())

    def test_session_client_no_owner(self) -> None:
        proxy = MagicMock()
        proxy.get_name_owner.return_value = None
        with patch("gi.repository.Gio.bus_get_sync"), patch(
            "gi.repository.Gio.DBusProxy.new_sync", return_value=proxy
        ):
            self.assertIsNone(session_client())

    def test_session_client_ok(self) -> None:
        proxy = MagicMock()
        proxy.get_name_owner.return_value = ":1.2"
        result = MagicMock()
        result.unpack.return_value = ("[]",)
        proxy.call_sync.return_value = result
        with patch("gi.repository.Gio.bus_get_sync"), patch(
            "gi.repository.Gio.DBusProxy.new_sync", return_value=proxy
        ):
            client = session_client()
            self.assertEqual(client.list_displays(), [])

    def test_own_name(self) -> None:
        with patch("gi.repository.Gio.bus_own_name", return_value=9) as own:
            self.assertEqual(own_bus_name("dev.x"), 9)
            own.assert_called()

    def test_export_session(self) -> None:
        from monitorcontrol.controller import Controller
        from monitorcontrol.dbus import export_session
        from monitorcontrol.service import MonitorService

        connection = MagicMock()
        connection.register_object.return_value = 3
        svc = MonitorService(Controller(discover_fn=lambda: []))
        session = export_session(svc, connection)
        self.assertEqual(session.registration_id, 3)
        self.addCleanup(session.close)
        self.addCleanup(svc.controller.close)
        args, _kwargs = connection.register_object.call_args
        on_method = args[2]
        invocation = MagicMock()
        params = MagicMock()
        params.unpack.return_value = ()
        on_method(None, None, None, None, "ListDisplays", params, invocation)
        invocation.return_value.assert_called()
        on_method(None, None, None, None, "Nope", params, invocation)
        invocation.return_dbus_error.assert_called()

    def test_changed_reaches_every_source_and_shutdown_releases_the_bus(self) -> None:
        import json

        from monitorcontrol.controller import Controller
        from monitorcontrol.dbus import export_session
        from monitorcontrol.ddc import DdcError
        from monitorcontrol.display import BackendKind, Display, FeatureState
        from monitorcontrol.gnome_backlight import apply_native_percent
        from monitorcontrol.service import MonitorService
        from monitorcontrol.vcp import Feature

        def make(identity: str, name: str, kind=BackendKind.DDC) -> Display:
            return Display(
                identity=identity,
                name=name,
                connector_sys_name=identity,
                connector_type="HDMI-A" if kind is BackendKind.DDC else "eDP",
                kind=kind,
                features={Feature.BRIGHTNESS: FeatureState(40, 100)},
                _set=lambda _feature, _value: None,
            )

        dell = make("DEL:U2720Q:AA", "U2720Q")
        lg = make("GSM:27GL850:BB", "27GL850")
        laptop = make("AUO:panel", "Laptop", BackendKind.BACKLIGHT)
        ctrl = Controller(discover_fn=lambda: [laptop, dell, lg], retry_sleep=lambda _delay: None)
        ctrl.refresh()
        ctrl.sync = True
        service = MonitorService(ctrl)
        connection = MagicMock()
        connection.register_object.return_value = 7
        session = export_session(service, connection, marshal=lambda fn: fn())
        self.addCleanup(session.close)
        self.addCleanup(ctrl.close)

        def emitted():
            rows = []
            for call in connection.emit_signal.call_args_list:
                rows.append((call.args[3], json.loads(call.args[4].unpack()[0])))
            return rows

        service.set_percent(dell.identity, "brightness", 15)
        signals = emitted()
        self.assertEqual([name for name, _payload in signals], ["Changed"])
        synced = {row["id"]: row["percent"] for row in signals[0][1]}
        self.assertEqual(synced[dell.identity], 15)
        self.assertEqual(synced[lg.identity], 15)

        connection.emit_signal.reset_mock()
        service.adjust("brightness", 5, dell.identity)
        self.assertEqual(emitted()[0][0], "Changed")
        self.assertEqual(emitted()[0][1][0]["percent"], 20)

        connection.emit_signal.reset_mock()
        apply_native_percent(ctrl, 33)
        native = emitted()
        self.assertTrue(native)
        self.assertTrue(all(name == "Changed" for name, _payload in native))
        percents = [row["percent"] for _name, payload in native for row in payload]
        self.assertIn(33, percents)

        ctrl.flush()
        connection.emit_signal.reset_mock()
        service.refresh()
        self.assertEqual(emitted()[0][0], "DisplaysChanged")

        def fail(_feature, _value):
            raise DdcError("unsupported VCP")

        dell._set = fail
        connection.emit_signal.reset_mock()
        service.set_percent(dell.identity, "brightness", 9)
        ctrl.flush()
        names = [name for name, _payload in emitted()]
        self.assertIn("Changed", names)
        self.assertIn("OperationFailed", names)
        failed = next(payload for name, payload in emitted() if name == "OperationFailed")
        self.assertIn("unsupported", failed[0]["error"])

        session.close()
        connection.unregister_object.assert_called_with(7)
        session.close()


if __name__ == "__main__":
    unittest.main()
