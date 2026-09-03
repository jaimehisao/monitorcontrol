from __future__ import annotations

import unittest

from monitorcontrol.controller import Controller, Scheduler
from monitorcontrol.display import BackendKind, Display, FeatureState
from monitorcontrol.vcp import Feature


class ManualScheduler(Scheduler):
    def __init__(self) -> None:
        self.queued: list[object] = []

    def call_later(self, delay_s: float, fn) -> object:
        self.queued.append(fn)
        return fn

    def cancel(self, handle: object) -> None:
        if handle in self.queued:
            self.queued.remove(handle)

    def fire(self) -> None:
        fns = list(self.queued)
        self.queued.clear()
        for fn in fns:
            fn()


def _display(identity: str, name: str, brightness: int = 50) -> Display:
    writes: list[tuple[Feature, int]] = []

    def setter(feature: Feature, value: int) -> None:
        writes.append((feature, value))

    display = Display(
        identity=identity,
        name=name,
        connector_sys_name=identity,
        connector_type="HDMI-A",
        kind=BackendKind.DDC,
        features={Feature.BRIGHTNESS: FeatureState(current=brightness, maximum=100)},
        _set=setter,
    )
    display.writes = writes  # type: ignore[attr-defined]
    return display


class ControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dell = _display("DEL:U2720Q:AA", "U2720Q", 40)
        self.lg = _display("GSM:27GL850:BB", "27GL850", 70)
        self.sched = ManualScheduler()
        self.ctrl = Controller(
            step=5,
            discover_fn=lambda: [self.dell, self.lg],
            scheduler=self.sched,
        )
        self.ctrl.refresh()

    def test_adjust_moves_every_display_that_has_the_feature(self) -> None:
        changes = self.ctrl.adjust(Feature.BRIGHTNESS, +10)
        self.assertEqual([c.state.percent for c in changes], [50, 80])
        self.assertEqual(self.dell.writes, [])
        self.sched.fire()
        self.assertEqual(self.dell.writes, [(Feature.BRIGHTNESS, 50)])
        self.assertEqual(self.lg.writes, [(Feature.BRIGHTNESS, 80)])

    def test_rapid_changes_coalesce_to_the_last_value(self) -> None:
        self.ctrl.adjust(Feature.BRIGHTNESS, +5)
        self.ctrl.adjust(Feature.BRIGHTNESS, +5)
        self.ctrl.adjust(Feature.BRIGHTNESS, +5)
        self.assertEqual(len(self.sched.queued), 1)
        self.sched.fire()
        self.assertEqual(self.dell.writes, [(Feature.BRIGHTNESS, 55)])

    def test_sync_set_copies_percent_to_the_other_monitor(self) -> None:
        self.ctrl.sync = True
        self.ctrl.set_percent(self.dell.identity, Feature.BRIGHTNESS, 20, immediate=True)
        self.assertEqual(self.dell.features[Feature.BRIGHTNESS].percent, 20)
        self.assertEqual(self.lg.features[Feature.BRIGHTNESS].percent, 20)
        self.assertEqual(self.lg.writes, [(Feature.BRIGHTNESS, 20)])

    def test_identity_limits_the_change(self) -> None:
        self.ctrl.adjust(Feature.BRIGHTNESS, -10, identity=self.lg.identity, immediate=True)
        self.assertEqual(self.dell.features[Feature.BRIGHTNESS].percent, 40)
        self.assertEqual(self.lg.features[Feature.BRIGHTNESS].percent, 60)
        self.assertEqual(self.dell.writes, [])

    def test_subscribe_sees_adjust(self) -> None:
        seen: list[int] = []
        self.ctrl.subscribe(lambda changes: seen.append(changes[0].state.percent))
        self.ctrl.adjust(Feature.BRIGHTNESS, +5, identity=self.dell.identity, immediate=True)
        self.assertEqual(seen, [45])

    def test_clamps_at_zero_and_hundred(self) -> None:
        self.ctrl.adjust(Feature.BRIGHTNESS, -100, immediate=True)
        self.assertEqual(self.dell.features[Feature.BRIGHTNESS].percent, 0)
        self.ctrl.adjust(Feature.BRIGHTNESS, +1000, immediate=True)
        self.assertEqual(self.dell.features[Feature.BRIGHTNESS].percent, 100)


if __name__ == "__main__":
    unittest.main()
