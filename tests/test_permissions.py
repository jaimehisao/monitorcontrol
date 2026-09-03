from __future__ import annotations

import unittest

from monitorcontrol.permissions import SETUP_COMMANDS, permission_message


class PermissionTests(unittest.TestCase):
    def test_setup_commands_are_generic(self) -> None:
        self.assertIn("i2c", SETUP_COMMANDS)
        self.assertIn("udev", SETUP_COMMANDS)
        self.assertNotIn("nvidia", SETUP_COMMANDS.lower())
        self.assertNotIn("lenovo", SETUP_COMMANDS.lower())

    def test_live_message_matches_access(self) -> None:
        from monitorcontrol.i2c import permission_status

        ready, _ = permission_status()
        message = permission_message()
        if ready:
            self.assertIsNone(message)
        else:
            self.assertIsNotNone(message)
            assert message is not None
            self.assertIn("/dev/i2c", message)


if __name__ == "__main__":
    unittest.main()
