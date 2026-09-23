"""Cached, debounced control of every discovered display.

DDC writes are slow and wear monitor NVRAM, so the UI/CLI updates the
cached percent immediately and the hardware write is coalesced. `sync`
applies a change to every display that implements that feature.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

from monitorcontrol.display import Display, FeatureState, discover
from monitorcontrol.vcp import Feature

FLUSH_DELAY_S = 0.08


class Scheduler:
    def call_later(self, delay_s: float, fn: Callable[[], None]) -> object:
        timer = threading.Timer(delay_s, fn)
        timer.daemon = True
        timer.start()
        return timer

    def cancel(self, handle: object) -> None:
        if isinstance(handle, threading.Timer):
            handle.cancel()


@dataclass(frozen=True)
class Change:
    display: Display
    feature: Feature
    state: FeatureState


class Controller:
    def __init__(
        self,
        *,
        step: int = 5,
        sync: bool = False,
        discover_fn: Callable[[], list[Display]] = discover,
        scheduler: Scheduler | None = None,
        flush_delay_s: float = FLUSH_DELAY_S,
    ) -> None:
        self.step = step
        self.sync = sync
        self._discover = discover_fn
        self._scheduler = scheduler or Scheduler()
        self._flush_delay_s = flush_delay_s
        self.displays: list[Display] = []
        self._pending: dict[tuple[str, Feature], int] = {}
        self._flush_handle: object | None = None
        self.last_write_error: str | None = None
        self._hardware: dict[tuple[str, Feature], FeatureState] = {}
        self._lock = threading.Lock()
        self._listeners: list[Callable[[list[Change]], None]] = []
        self._refresh_listeners: list[Callable[[list[Display]], None]] = []

    def subscribe(self, fn: Callable[[list[Change]], None]) -> None:
        self._listeners.append(fn)

    def subscribe_refresh(self, fn: Callable[[list[Display]], None]) -> None:
        self._refresh_listeners.append(fn)

    def _notify(self, changes: list[Change]) -> None:
        if not changes:
            return
        for fn in list(self._listeners):
            fn(changes)

    def refresh(self, *, block: bool = True) -> list[Display]:
        if not block:
            self._scheduler.call_later(0, self._refresh_now)
            with self._lock:
                return list(self.displays)
        return self._refresh_now()

    def _refresh_now(self) -> list[Display]:
        self._flush_io()
        found = self._discover()
        with self._lock:
            previous = list(self.displays)
            self.displays = found
            self._remember_hardware()
            current = list(self.displays)
        for display in previous:
            display.close()
        for fn in list(self._refresh_listeners):
            fn(current)
        return current

    def flush(self) -> None:
        self._flush_io()

    def close(self) -> None:
        with self._lock:
            if self._flush_handle is not None:
                self._scheduler.cancel(self._flush_handle)
                self._flush_handle = None
        self._flush_io()
        with self._lock:
            previous = list(self.displays)
            self.displays = []
        for display in previous:
            display.close()

    def find(self, identity: str) -> Display:
        for display in self.displays:
            if display.identity == identity:
                return display
        raise KeyError(identity)

    def targets(self, feature: Feature, identity: str | None = None) -> list[Display]:
        if identity is not None:
            display = self.find(identity)
            if feature not in display.features:
                return []
            return [display]
        return [d for d in self.displays if feature in d.features]

    def set_percent(
        self,
        identity: str,
        feature: Feature,
        percent: int,
        *,
        immediate: bool = False,
        propagate: bool | None = None,
        notify: bool = True,
    ) -> list[Change]:
        identities = [identity]
        sync = self.sync if propagate is None else propagate
        if sync:
            identities = [d.identity for d in self.targets(feature)]
            if identity not in identities:
                identities.insert(0, identity)
        changes: list[Change] = []
        with self._lock:
            for display_id in identities:
                display = self.find(display_id)
                if feature not in display.features:
                    continue
                target = display.features[feature].with_percent(percent)
                display.features[feature] = target
                self._pending[(display_id, feature)] = target.current
                changes.append(Change(display=display, feature=feature, state=target))
            if not immediate:
                self._arm_flush()
        if immediate:
            self._flush_io()
        if notify:
            self._notify(changes)
        return changes

    def adjust(
        self,
        feature: Feature,
        delta: int | None = None,
        *,
        identity: str | None = None,
        immediate: bool = False,
    ) -> list[Change]:
        step = self.step if delta is None else delta
        changes: list[Change] = []
        for display in self.targets(feature, identity):
            percent = display.features[feature].percent + step
            changes.extend(
                self.set_percent(
                    display.identity,
                    feature,
                    percent,
                    immediate=immediate,
                    propagate=False,
                )
            )
        return changes

    def _arm_flush(self) -> None:
        if self._flush_handle is not None:
            self._scheduler.cancel(self._flush_handle)
        self._flush_handle = self._scheduler.call_later(
            self._flush_delay_s, self._flush
        )

    def _flush(self) -> None:
        self._flush_io()

    def _remember_hardware(self) -> None:
        self._hardware = {
            (display.identity, feature): state
            for display in self.displays
            for feature, state in display.features.items()
        }

    def _flush_io(self) -> None:
        with self._lock:
            pending = self._pending
            self._pending = {}
            self._flush_handle = None
            grouped: dict[str, list[tuple[Display, Feature, int]]] = {}
            for (identity, feature), value in pending.items():
                display = next((item for item in self.displays if item.identity == identity), None)
                if display is None:
                    continue
                grouped.setdefault(identity, []).append((display, feature, value))

        def run_group(items: list[tuple[Display, Feature, int]]) -> list[tuple]:
            results = []
            for display, feature, value in items:
                try:
                    display.set_raw(feature, value)
                except Exception as exc:
                    results.append((display, feature, exc))
                else:
                    results.append((display, feature, None))
            return results

        results: list[tuple] = []
        groups = list(grouped.values())
        if len(groups) <= 1:
            if groups:
                results.extend(run_group(groups[0]))
        else:
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=min(4, len(groups))) as pool:
                for part in pool.map(run_group, groups):
                    results.extend(part)

        corrections: list[Change] = []
        with self._lock:
            for display, feature, error in results:
                if error is not None:
                    previous = self._hardware.get((display.identity, feature))
                    if previous is not None and feature in display.features:
                        display.features[feature] = previous
                        corrections.append(Change(display=display, feature=feature, state=previous))
                    message = f"Could not update {display.name}: {error}"
                    display.warning = message
                    self.last_write_error = message
                    continue
                self.last_write_error = None
                self._hardware[(display.identity, feature)] = display.features[feature]
        if corrections:
            self._notify(corrections)
