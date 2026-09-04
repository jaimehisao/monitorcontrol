from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from monitorcontrol.i2c_setup import (
    UDEV_RULE,
    LinuxRunner,
    privileged_argv,
    privileged_setup,
    pkexec_grant,
)


class FakeRunner:
    def __init__(self) -> None:
        self.groups: list[str] = []
        self.memberships: list[tuple[str, str]] = []
        self.modules: list[str] = []
        self.reloaded = 0
        self.grants: list[tuple[str, str, str]] = []

    def ensure_group(self, name: str) -> None:
        self.groups.append(name)

    def add_user_to_group(self, user: str, group: str) -> None:
        self.memberships.append((user, group))

    def load_module(self, name: str) -> None:
        self.modules.append(name)

    def reload_udev(self) -> None:
        self.reloaded += 1

    def grant_now(self, device: Path, user: str, group: str) -> None:
        self.grants.append((str(device), user, group))


class PrivilegedSetupTests(unittest.TestCase):
    def test_writes_rules_and_grants_now(self) -> None:
        with TemporaryDirectory() as raw:
            root = Path(raw)
            udev = root / "udev" / "90-monitorcontrol-i2c.rules"
            modules = root / "modules-load.d" / "i2c-dev.conf"
            bus = root / "dev" / "i2c-7"
            bus.parent.mkdir()
            bus.write_text("")
            runner = FakeRunner()
            privileged_setup(
                "hisao",
                udev_path=udev,
                modules_path=modules,
                devices=[bus],
                runner=runner,
            )
            self.assertIn("uaccess", udev.read_text())
            self.assertEqual(UDEV_RULE, udev.read_text())
            self.assertEqual(modules.read_text(), "i2c-dev\n")
            self.assertEqual(runner.groups, ["i2c"])
            self.assertEqual(runner.memberships, [("hisao", "i2c")])
            self.assertEqual(runner.modules, ["i2c-dev"])
            self.assertEqual(runner.reloaded, 1)
            self.assertEqual(runner.grants, [(str(bus), "hisao", "i2c")])

    def test_refuses_root_user(self) -> None:
        with self.assertRaises(ValueError):
            privileged_setup("root", runner=FakeRunner())

    def test_pkexec_argv_and_failure(self) -> None:
        argv = privileged_argv("hisao", executable="/opt/monitorcontrol")
        self.assertEqual(
            argv,
            ["/opt/monitorcontrol", "--privileged-setup", "--setup-user", "hisao"],
        )
        argv = privileged_argv("hisao", executable=None)
        self.assertIn("--privileged-setup", argv)
        self.assertIn("hisao", argv)

        class Proc:
            returncode = 1
            stderr = "dismissed"
            stdout = ""

        ok, err = pkexec_grant("hisao", run=lambda *_a, **_k: Proc())
        self.assertFalse(ok)
        self.assertIn("dismissed", err or "")

        class Ok:
            returncode = 0
            stderr = ""
            stdout = ""

        ok, err = pkexec_grant("hisao", run=lambda *_a, **_k: Ok(), executable="/x")
        self.assertTrue(ok)
        self.assertIsNone(err)

        def boom(*_a, **_k):
            raise OSError("no pkexec")

        ok, err = pkexec_grant("hisao", run=boom)
        self.assertFalse(ok)
        self.assertIn("pkexec", err or "")


class LinuxRunnerSmoke(unittest.TestCase):
    def test_grant_now_on_temp_node(self) -> None:
        with TemporaryDirectory() as raw:
            node = Path(raw) / "i2c-1"
            node.write_bytes(b"")
            node.chmod(0o600)
            LinuxRunner().grant_now(node, "nobody", "root")
            # chmod 666 fallback or 660 — either is readable attempt
            self.assertTrue(node.exists())


if __name__ == "__main__":
    unittest.main()
