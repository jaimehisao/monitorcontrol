from __future__ import annotations

import threading
import time
import unittest

from monitorcontrol.controller import MAX_TRANSIENT_RETRIES, Controller, is_transient
from monitorcontrol.ddc import DdcError, DdcPermissionError
from monitorcontrol.display import BackendKind, Display, FeatureState
from monitorcontrol.vcp import Feature


def _display(
    identity: str,
    name: str,
    brightness: int = 50,
    *,
    setter=None,
    refresh=None,
    contrast: int | None = None,
) -> Display:
    writes: list[tuple[Feature, int]] = []

    def default_setter(feature: Feature, value: int) -> None:
        writes.append((feature, value))

    features = {Feature.BRIGHTNESS: FeatureState(current=brightness, maximum=100)}
    if contrast is not None:
        features[Feature.CONTRAST] = FeatureState(current=contrast, maximum=100)
    display = Display(
        identity=identity,
        name=name,
        connector_sys_name=identity,
        connector_type="HDMI-A",
        kind=BackendKind.DDC,
        features=features,
        _set=setter or default_setter,
        _refresh=refresh,
    )
    display.writes = writes  # type: ignore[attr-defined]
    return display


class ControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dell = _display("DEL:U2720Q:AA", "U2720Q", 40)
        self.lg = _display("GSM:27GL850:BB", "27GL850", 70)
        self.ctrl = Controller(
            step=5,
            discover_fn=lambda: [self.dell, self.lg],
            retry_sleep=lambda _delay: None,
        )
        self.ctrl.refresh()

    def tearDown(self) -> None:
        self.ctrl.close()

    def test_adjust_moves_every_display_that_has_the_feature(self) -> None:
        changes = self.ctrl.adjust(Feature.BRIGHTNESS, +10)
        self.assertEqual([change.state.percent for change in changes], [50, 80])
        self.assertEqual(self.dell.writes, [])
        self.ctrl.flush()
        self.assertEqual(self.dell.writes, [(Feature.BRIGHTNESS, 50)])
        self.assertEqual(self.lg.writes, [(Feature.BRIGHTNESS, 80)])

    def test_rapid_changes_coalesce_to_the_last_value(self) -> None:
        self.ctrl.adjust(Feature.BRIGHTNESS, +5)
        self.ctrl.adjust(Feature.BRIGHTNESS, +5)
        self.ctrl.adjust(Feature.BRIGHTNESS, +5)
        self.assertEqual(self.dell.writes, [])
        self.ctrl.flush()
        self.assertEqual(self.dell.writes, [(Feature.BRIGHTNESS, 55)])

    def test_hundred_event_drag_writes_the_final_value_once(self) -> None:
        for percent in range(100):
            self.ctrl.set_percent(self.dell.identity, Feature.BRIGHTNESS, percent, propagate=False)
        self.assertEqual(self.dell.writes, [])
        self.assertEqual(self.ctrl.confirmed_percent(self.dell.identity, Feature.BRIGHTNESS), 40)
        self.ctrl.flush()
        self.assertEqual(self.dell.writes, [(Feature.BRIGHTNESS, 99)])
        self.assertEqual(self.ctrl.confirmed_percent(self.dell.identity, Feature.BRIGHTNESS), 99)

    def test_sync_set_copies_percent_to_the_other_monitor(self) -> None:
        self.ctrl.sync = True
        self.ctrl.set_percent(self.dell.identity, Feature.BRIGHTNESS, 20)
        self.ctrl.flush()
        self.assertEqual(self.dell.features[Feature.BRIGHTNESS].percent, 20)
        self.assertEqual(self.lg.features[Feature.BRIGHTNESS].percent, 20)
        self.assertEqual(self.lg.writes, [(Feature.BRIGHTNESS, 20)])

    def test_identity_limits_the_change(self) -> None:
        self.ctrl.adjust(Feature.BRIGHTNESS, -10, identity=self.lg.identity)
        self.ctrl.flush()
        self.assertEqual(self.dell.features[Feature.BRIGHTNESS].percent, 40)
        self.assertEqual(self.lg.features[Feature.BRIGHTNESS].percent, 60)
        self.assertEqual(self.dell.writes, [])

    def test_subscribe_sees_adjust(self) -> None:
        seen: list[int] = []
        self.ctrl.subscribe(lambda changes: seen.append(changes[0].state.percent))
        self.ctrl.adjust(Feature.BRIGHTNESS, +5, identity=self.dell.identity)
        self.assertEqual(seen, [45])

    def test_listener_errors_do_not_escape(self) -> None:
        seen: list[int] = []

        def broken(_changes: list) -> None:
            raise RuntimeError("listener blew up")

        self.ctrl.subscribe(broken)
        self.ctrl.subscribe(lambda changes: seen.append(changes[0].state.percent))
        self.ctrl.adjust(Feature.BRIGHTNESS, +5, identity=self.dell.identity)
        self.assertEqual(seen, [45])
        self.assertTrue(any("listener blew up" in item for item in self.ctrl.worker_errors))
        self.ctrl._notify([])

    def test_close_flushes_pending_writes(self) -> None:
        ctrl = Controller(
            discover_fn=lambda: [self.dell],
            retry_sleep=lambda _delay: None,
        )
        ctrl.refresh()
        ctrl.adjust(Feature.BRIGHTNESS, +1)
        with self.assertRaises(KeyError):
            ctrl.find("nope")
        ctrl.close()
        self.assertEqual(self.dell.writes, [(Feature.BRIGHTNESS, 41)])
        self.assertEqual(ctrl.displays, [])

    def test_clamps_at_zero_and_hundred(self) -> None:
        self.ctrl.adjust(Feature.BRIGHTNESS, -100)
        self.assertEqual(self.dell.features[Feature.BRIGHTNESS].percent, 0)
        self.ctrl.adjust(Feature.BRIGHTNESS, +1000)
        self.assertEqual(self.dell.features[Feature.BRIGHTNESS].percent, 100)

    def test_failed_write_rolls_back_to_confirmed(self) -> None:
        calls = {"n": 0}

        def explode(_feature: Feature, _value: int) -> None:
            calls["n"] += 1
            raise DdcError("I2C write failed on /dev/i2c-4")

        dell = _display("DEL:U2720Q:AA", "U2720Q", 40, setter=explode)
        ctrl = Controller(discover_fn=lambda: [dell], retry_sleep=lambda _delay: None)
        ctrl.refresh()
        seen: list[str | None] = []
        ctrl.subscribe(lambda changes: seen.append(changes[0].error))
        ctrl.set_percent(dell.identity, Feature.BRIGHTNESS, 70, propagate=False)
        ctrl.flush()
        self.assertEqual(calls["n"], 1 + MAX_TRANSIENT_RETRIES)
        self.assertEqual(dell.features[Feature.BRIGHTNESS].percent, 40)
        self.assertIn("write failed", ctrl.feature_error(dell.identity, Feature.BRIGHTNESS) or "")
        self.assertEqual(ctrl.confirmed_percent(dell.identity, Feature.BRIGHTNESS), 40)
        self.assertTrue(any(item and "write failed" in item for item in seen))
        ctrl.close()

    def test_transient_failure_retries_then_confirms(self) -> None:
        calls = {"n": 0}
        writes: list[int] = []

        def flaky(_feature: Feature, value: int) -> None:
            calls["n"] += 1
            if calls["n"] == 1:
                raise DdcError("I2C write failed")
            writes.append(value)

        dell = _display("DEL:U2720Q:AA", "U2720Q", 40, setter=flaky)
        ctrl = Controller(discover_fn=lambda: [dell], retry_sleep=lambda _delay: None)
        ctrl.refresh()
        ctrl.set_percent(dell.identity, Feature.BRIGHTNESS, 70, propagate=False)
        ctrl.flush()
        self.assertEqual(calls["n"], 2)
        self.assertEqual(writes, [70])
        self.assertIsNone(ctrl.feature_error(dell.identity, Feature.BRIGHTNESS))
        self.assertEqual(ctrl.confirmed_percent(dell.identity, Feature.BRIGHTNESS), 70)
        ctrl.close()

    def test_permanent_failure_does_not_retry(self) -> None:
        calls = {"n": 0}

        def denied(_feature: Feature, _value: int) -> None:
            calls["n"] += 1
            raise DdcPermissionError("not allowed")

        dell = _display("DEL:U2720Q:AA", "U2720Q", 40, setter=denied)
        ctrl = Controller(discover_fn=lambda: [dell], retry_sleep=lambda _delay: None)
        ctrl.refresh()
        ctrl.set_percent(dell.identity, Feature.BRIGHTNESS, 12, propagate=False)
        ctrl.flush()
        self.assertEqual(calls["n"], 1)
        self.assertEqual(dell.features[Feature.BRIGHTNESS].percent, 40)
        ctrl.close()

    def test_failed_write_adopts_a_follow_up_read(self) -> None:
        def explode(_feature: Feature, _value: int) -> None:
            raise RuntimeError("rejected")

        def read_back(_feature: Feature) -> FeatureState:
            return FeatureState(current=33, maximum=100)

        dell = _display("DEL:U2720Q:AA", "U2720Q", 40, setter=explode, refresh=read_back)
        ctrl = Controller(discover_fn=lambda: [dell], retry_sleep=lambda _delay: None)
        ctrl.refresh()
        ctrl.set_percent(dell.identity, Feature.BRIGHTNESS, 80, propagate=False)
        ctrl.flush()
        self.assertEqual(dell.features[Feature.BRIGHTNESS].percent, 33)
        self.assertIsNone(ctrl.feature_error(dell.identity, Feature.BRIGHTNESS))
        self.assertEqual(ctrl.confirmed_percent(dell.identity, Feature.BRIGHTNESS), 33)
        ctrl.close()

    def test_refresh_keeps_a_pending_user_change(self) -> None:
        holder = {"display": _display("DEL:U2720Q:AA", "U2720Q", 40)}
        ctrl = Controller(
            discover_fn=lambda: [holder["display"]],
            retry_sleep=lambda _delay: None,
        )
        ctrl.refresh()
        ctrl.set_percent("DEL:U2720Q:AA", Feature.BRIGHTNESS, 90, propagate=False)
        self.assertEqual(holder["display"].writes, [])
        holder["display"] = _display("DEL:U2720Q:AA", "U2720Q", 40)
        ctrl.refresh()
        self.assertEqual(ctrl.displays[0].features[Feature.BRIGHTNESS].percent, 90)
        self.assertEqual(ctrl.displays[0].writes, [])
        ctrl.flush()
        self.assertEqual(ctrl.displays[0].writes, [(Feature.BRIGHTNESS, 90)])
        ctrl.close()

    def test_refresh_drops_pending_writes_for_a_removed_display(self) -> None:
        ctrl = Controller(
            discover_fn=lambda: [self.dell, self.lg],
            retry_sleep=lambda _delay: None,
        )
        ctrl.refresh()
        ctrl.set_percent(self.lg.identity, Feature.BRIGHTNESS, 10, propagate=False)
        ctrl._discover = lambda: [self.dell]
        ctrl.refresh()
        self.assertEqual([display.identity for display in ctrl.displays], [self.dell.identity])
        ctrl.flush()
        self.assertEqual(self.lg.writes, [])
        ctrl.close()

    def test_one_display_does_not_block_another(self) -> None:
        release = threading.Event()
        started = threading.Event()
        slow_writes: list[int] = []
        fast_writes: list[int] = []

        def slow(_feature: Feature, value: int) -> None:
            started.set()
            self.assertTrue(release.wait(2))
            slow_writes.append(value)

        def fast(_feature: Feature, value: int) -> None:
            fast_writes.append(value)

        slow_display = _display("slow", "Slow", setter=slow)
        fast_display = _display("fast", "Fast", setter=fast)
        ctrl = Controller(
            discover_fn=lambda: [slow_display, fast_display],
            flush_delay_s=0,
            retry_sleep=lambda _delay: None,
        )
        ctrl.refresh()
        ctrl.set_percent("slow", Feature.BRIGHTNESS, 11, propagate=False)
        self.assertTrue(started.wait(1))
        ctrl.set_percent("fast", Feature.BRIGHTNESS, 22, propagate=False)
        deadline = time.monotonic() + 1
        while not fast_writes and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(fast_writes, [22])
        self.assertEqual(slow_writes, [])
        release.set()
        ctrl.flush()
        self.assertEqual(slow_writes, [11])
        ctrl.close()

    def test_commands_on_one_display_stay_serialized(self) -> None:
        current = {"n": 0}
        peak = {"n": 0}
        order: list[Feature] = []

        def setter(feature: Feature, value: int) -> None:
            current["n"] += 1
            peak["n"] = max(peak["n"], current["n"])
            time.sleep(0.05)
            order.append(feature)
            current["n"] -= 1

        dell = _display("DEL:U2720Q:AA", "U2720Q", setter=setter, contrast=20)
        ctrl = Controller(
            discover_fn=lambda: [dell],
            flush_delay_s=0.05,
            retry_sleep=lambda _delay: None,
        )
        ctrl.refresh()
        ctrl.set_percent(dell.identity, Feature.BRIGHTNESS, 30, propagate=False)
        ctrl.set_percent(dell.identity, Feature.CONTRAST, 60, propagate=False)
        ctrl.flush()
        self.assertEqual(peak["n"], 1)
        self.assertEqual(order, [Feature.BRIGHTNESS, Feature.CONTRAST])
        ctrl.close()

    def test_read_failure_keeps_the_rollback(self) -> None:
        def explode(_feature: Feature, _value: int) -> None:
            raise RuntimeError("nope")

        def read_back(_feature: Feature) -> FeatureState:
            raise DdcError("I2C read failed")

        dell = _display("DEL:U2720Q:AA", "U2720Q", 40, setter=explode, refresh=read_back)
        ctrl = Controller(discover_fn=lambda: [dell], retry_sleep=lambda _delay: None)
        ctrl.refresh()
        ctrl.set_percent(dell.identity, Feature.BRIGHTNESS, 80, propagate=False)
        ctrl.flush()
        self.assertEqual(dell.features[Feature.BRIGHTNESS].percent, 40)
        self.assertIn("nope", ctrl.feature_error(dell.identity, Feature.BRIGHTNESS) or "")
        ctrl.close()

    def test_stale_write_and_worker_exception_stay_contained(self) -> None:
        self.ctrl.set_percent(self.dell.identity, Feature.BRIGHTNESS, 80, propagate=False)
        self.ctrl.flush()
        lane = self.ctrl._lanes[self.dell.identity]
        self.assertEqual(lane._write_one(Feature.BRIGHTNESS, 10, 0), [])
        self.assertEqual(self.dell.features[Feature.BRIGHTNESS].percent, 80)
        self.ctrl.displays.clear()
        generation = self.ctrl._generations[(self.dell.identity, Feature.BRIGHTNESS)]
        self.assertEqual(lane._write_one(Feature.BRIGHTNESS, 10, generation), [])

        def explode(_batch: dict) -> list:
            raise RuntimeError("worker exploded")

        lane._write_batch = explode  # type: ignore[method-assign]
        lane.submit(Feature.BRIGHTNESS, 80, generation)
        self.ctrl.flush()
        self.assertTrue(any("worker exploded" in item for item in self.ctrl.worker_errors))

    def test_is_transient_classification(self) -> None:
        self.assertTrue(is_transient(TimeoutError("timed out")))
        self.assertTrue(is_transient(OSError("busy")))
        self.assertTrue(is_transient(DdcError("short DDC reply")))
        self.assertFalse(is_transient(DdcPermissionError("no")))
        self.assertFalse(is_transient(DdcError("unsupported VCP")))
        self.assertFalse(is_transient(RuntimeError("boom")))


if __name__ == "__main__":
    unittest.main()
