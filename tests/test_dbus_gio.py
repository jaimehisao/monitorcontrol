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
        self.assertEqual(export_session(svc, connection), 3)
        args, _kwargs = connection.register_object.call_args
        on_method = args[2]
        invocation = MagicMock()
        params = MagicMock()
        params.unpack.return_value = ()
        on_method(None, None, None, None, "ListDisplays", params, invocation)
        invocation.return_value.assert_called()
        on_method(None, None, None, None, "Nope", params, invocation)
        invocation.return_dbus_error.assert_called()


if __name__ == "__main__":
    unittest.main()
