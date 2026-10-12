"""Cached, coalesced control of every discovered display.

DDC writes are slow and wear monitor NVRAM. Every caller — the window,
the session API, and GNOME brightness following — updates the desired
percent immediately and hands the hardware write to a per-display worker.
Workers coalesce a burst down to the latest value, keep one display's
commands in order, and do not block a different display.

`display.features` is the desired value the UI is showing. `confirmed`
is the last value hardware accepted. A failed write rolls the desired
value back to confirmed (or to a follow-up read) and records an error
instead of leaving the cache looking successful.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from monitorcontrol.ddc import DdcError, DdcPermissionError
from monitorcontrol.display import Display, FeatureState, discover
from monitorcontrol.vcp import Feature

log = logging.getLogger(__name__)

FLUSH_DELAY_S = 0.08
MAX_TRANSIENT_RETRIES = 2
RETRY_DELAY_S = 0.05
_TRANSIENT_TEXT = ("write failed", "read failed", "timeout", "timed out", "short ddc", "truncated")


def is_transient(exc: BaseException) -> bool:
    """True when the same write is worth trying again."""
    if isinstance(exc, DdcPermissionError):
        return False
    if isinstance(exc, (TimeoutError, OSError)):
        return True
    if isinstance(exc, DdcError):
        text = str(exc).lower()
        return any(token in text for token in _TRANSIENT_TEXT)
    return False


@dataclass(frozen=True)
class Change:
    display: Display
    feature: Feature
    state: FeatureState
    confirmed: FeatureState | None = None
    error: str | None = None


class _Lane:
    """One long-lived worker. Commands for this display stay in order."""

    def __init__(self, controller: Controller, identity: str) -> None:
        self.controller = controller
        self.identity = identity
        self._pending: dict[Feature, tuple[int, int]] = {}
        self._cond = threading.Condition()
        self._waiters: list[threading.Event] = []
        self._writing = False
        self._stop = False
        self._force = False
        self._thread = threading.Thread(
            target=self._run,
            name=f"monitorcontrol-{identity}",
            daemon=True,
        )
        self._thread.start()

    def submit(self, feature: Feature, raw: int, generation: int) -> None:
        with self._cond:
            self._pending[feature] = (raw, generation)
            self._cond.notify_all()

    def flush(self) -> None:
        """Write whatever is already queued and wait until this lane is idle."""
        done = threading.Event()
        with self._cond:
            if not self._pending and not self._writing:
                return
            self._waiters.append(done)
            self._force = True
            self._cond.notify_all()
        if not done.wait(5):
            raise TimeoutError(f"timed out writing {self.identity}")

    def steal(self) -> dict[Feature, tuple[int, int]]:
        """Take writes that have not started. Wait out one that has."""
        with self._cond:
            batch = self._pending
            self._pending = {}
            writing = self._writing
            self._cond.notify_all()
        if writing:
            done = threading.Event()
            with self._cond:
                if self._writing:
                    self._waiters.append(done)
                else:
                    done.set()
            if not done.wait(5):
                raise TimeoutError(f"timed out stopping {self.identity}")
        return batch

    def stop(self) -> None:
        with self._cond:
            self._stop = True
            self._force = True
            self._cond.notify_all()
        self._thread.join(timeout=2)

    def _release_waiters_locked(self) -> None:
        if self._pending or self._writing:
            return
        waiters = self._waiters
        self._waiters = []
        for waiter in waiters:
            waiter.set()

    def _run(self) -> None:
        while True:
            with self._cond:
                if not self._pending:
                    self._writing = False
                    self._release_waiters_locked()
                    while not self._pending and not self._stop:
                        self._cond.wait()
                    if self._stop and not self._pending:
                        self._release_waiters_locked()
                        return
                delay = self.controller._flush_delay_s
                if delay > 0 and not self._force:
                    while not self._force and not self._stop:
                        snapshot = dict(self._pending)
                        self._cond.wait(timeout=delay)
                        if self._force or self._stop or self._pending == snapshot:
                            break
                self._force = False
                batch = self._pending
                self._pending = {}
                self._writing = bool(batch)
            if not batch:
                continue
            try:
                notes = self._write_batch(batch)
                # Notify before marking the lane idle so refresh cannot close
                # the display underneath a listener. Listeners must not flush.
                for change in notes:
                    self.controller._notify([change])
            except Exception as exc:
                log.exception("display worker failed for %s", self.identity)
                self.controller._capture(self.identity, exc)
            finally:
                with self._cond:
                    self._writing = False
                    if not self._pending:
                        self._release_waiters_locked()

    def _write_batch(self, batch: dict[Feature, tuple[int, int]]) -> list[Change]:
        notes: list[Change] = []
        for feature, (raw, generation) in batch.items():
            notes.extend(self._write_one(feature, raw, generation))
        return notes

    def _write_one(self, feature: Feature, raw: int, generation: int) -> list[Change]:
        attempts = 0
        while True:
            if not self.controller._generation_is(self.identity, feature, generation):
                return []
            display = self.controller._lookup(self.identity)
            if display is None or feature not in display.features:
                return []
            try:
                state = display.set_raw(feature, raw)
            except Exception as exc:
                if is_transient(exc) and attempts < MAX_TRANSIENT_RETRIES:
                    attempts += 1
                    self.controller._retry_sleep(RETRY_DELAY_S * attempts)
                    continue
                return self._fail(display, feature, generation, exc)
            self._confirm(display, feature, generation, state)
            return []

    def _confirm(
        self,
        display: Display,
        feature: Feature,
        generation: int,
        state: FeatureState,
    ) -> None:
        with self.controller._lock:
            key = (display.identity, feature)
            if self.controller._generations.get(key) != generation:
                desired = self.controller._desired.get(key)
                if desired is not None:
                    display.features[feature] = desired
                return
            self.controller._confirmed[key] = state
            self.controller._desired[key] = state
            display.features[feature] = state
            self.controller._errors.pop(key, None)

    def _fail(
        self,
        display: Display,
        feature: Feature,
        generation: int,
        exc: BaseException,
    ) -> list[Change]:
        with self.controller._lock:
            key = (display.identity, feature)
            if self.controller._generations.get(key) != generation:
                return []
            confirmed = self.controller._confirmed.get(key)
            if confirmed is not None:
                display.features[feature] = confirmed
                self.controller._desired[key] = confirmed
            message = str(exc) or type(exc).__name__
            self.controller._errors[key] = message
            shown = display.features[feature]
            rolled = Change(
                display=display,
                feature=feature,
                state=shown,
                confirmed=confirmed,
                error=message,
            )
        notes = [rolled]
        recovered = self._read_back(display, feature, generation)
        if recovered is not None:
            notes.append(recovered)
        return notes

    def _read_back(
        self,
        display: Display,
        feature: Feature,
        generation: int,
    ) -> Change | None:
        refresh = display._refresh
        if refresh is None:
            return None
        try:
            state = refresh(feature)
        except Exception:
            log.debug("reconcile read failed for %s", display.identity, exc_info=True)
            return None
        with self.controller._lock:
            key = (display.identity, feature)
            if self.controller._generations.get(key) != generation:
                return None
            display.features[feature] = state
            self.controller._confirmed[key] = state
            self.controller._desired[key] = state
            self.controller._errors.pop(key, None)
        return Change(display=display, feature=feature, state=state, confirmed=state)


class Controller:
    def __init__(
        self,
        *,
        step: int = 5,
        sync: bool = False,
        discover_fn: Callable[[], list[Display]] = discover,
        flush_delay_s: float = FLUSH_DELAY_S,
        retry_sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.step = step
        self.sync = sync
        self._discover = discover_fn
        self._flush_delay_s = flush_delay_s
        self._retry_sleep = retry_sleep or time.sleep
        self.displays: list[Display] = []
        self.worker_errors: list[str] = []
        self._lanes: dict[str, _Lane] = {}
        self._desired: dict[tuple[str, Feature], FeatureState] = {}
        self._confirmed: dict[tuple[str, Feature], FeatureState] = {}
        self._errors: dict[tuple[str, Feature], str] = {}
        self._generations: dict[tuple[str, Feature], int] = {}
        self._lock = threading.Lock()
        self._listeners: list[Callable[[list[Change]], None]] = []
        self._topology: list[Callable[[list[Display]], None]] = []

    def subscribe(self, fn: Callable[[list[Change]], None]) -> None:
        self._listeners.append(fn)

    def subscribe_topology(self, fn: Callable[[list[Display]], None]) -> None:
        self._topology.append(fn)

    def unsubscribe(self, fn: Callable[..., None]) -> None:
        for bucket in (self._listeners, self._topology):
            try:
                bucket.remove(fn)  # type: ignore[arg-type]
            except ValueError:
                pass

    def _notify(self, changes: list[Change]) -> None:
        if not changes:
            return
        for fn in list(self._listeners):
            try:
                fn(changes)
            except Exception as exc:
                log.exception("controller listener failed")
                self._capture(changes[0].display.identity, exc)

    def _capture(self, identity: str, exc: BaseException) -> None:
        self.worker_errors.append(f"{identity}: {exc}")

    def _lookup(self, identity: str) -> Display | None:
        with self._lock:
            for display in self.displays:
                if display.identity == identity:
                    return display
        return None

    def _generation_is(self, identity: str, feature: Feature, generation: int) -> bool:
        with self._lock:
            return self._generations.get((identity, feature)) == generation

    def confirmed_percent(self, identity: str, feature: Feature) -> int:
        with self._lock:
            state = self._confirmed.get((identity, feature))
            if state is not None:
                return state.percent
        display = self._lookup(identity)
        if display is None or feature not in display.features:
            return 0
        return display.features[feature].percent

    def feature_error(self, identity: str, feature: Feature) -> str | None:
        with self._lock:
            return self._errors.get((identity, feature))

    def _lane(self, identity: str) -> _Lane:
        lane = self._lanes.get(identity)
        if lane is None:
            lane = _Lane(self, identity)
            self._lanes[identity] = lane
        return lane

    def _seed_locked(self) -> None:
        self._confirmed.clear()
        self._desired.clear()
        self._errors.clear()
        for display in self.displays:
            for feature, state in display.features.items():
                key = (display.identity, feature)
                self._confirmed[key] = state
                self._desired[key] = state

    def _bump_locked(self, identity: str, feature: Feature) -> int:
        key = (identity, feature)
        generation = self._generations.get(key, 0) + 1
        self._generations[key] = generation
        return generation

    def refresh(self) -> list[Display]:
        stolen = [(identity, lane.steal()) for identity, lane in list(self._lanes.items())]
        with self._lock:
            for display in self.displays:
                display.close()
            self.displays = self._discover()
            self._seed_locked()
            alive = {display.identity for display in self.displays}
            gone = [identity for identity in self._lanes if identity not in alive]
        for identity in gone:
            self._lanes.pop(identity).stop()
        restored: list[Change] = []
        with self._lock:
            for identity, batch in stolen:
                if identity not in alive:
                    continue
                display = next(item for item in self.displays if item.identity == identity)
                for feature, (raw, _generation) in batch.items():
                    if feature not in display.features:
                        continue
                    maximum = display.features[feature].maximum
                    desired = FeatureState(current=max(0, min(maximum, raw)), maximum=maximum)
                    display.features[feature] = desired
                    self._desired[(identity, feature)] = desired
                    generation = self._bump_locked(identity, feature)
                    self._lane(identity).submit(feature, desired.current, generation)
                    restored.append(
                        Change(
                            display=display,
                            feature=feature,
                            state=desired,
                            confirmed=self._confirmed.get((identity, feature)),
                        )
                    )
            result = list(self.displays)
        if restored:
            self._notify(restored)
        self._notify_topology()
        return result

    def _notify_topology(self) -> None:
        displays = list(self.displays)
        for fn in list(self._topology):
            try:
                fn(displays)
            except Exception as exc:
                log.exception("topology listener failed")
                if displays:
                    self._capture(displays[0].identity, exc)

    def flush(self) -> None:
        """Write coalesced pending values now."""
        for lane in list(self._lanes.values()):
            lane.flush()

    def close(self) -> None:
        self.flush()
        for lane in list(self._lanes.values()):
            lane.stop()
        with self._lock:
            for display in self.displays:
                display.close()
            self.displays = []
            self._lanes.clear()

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
        return [display for display in self.displays if feature in display.features]

    def set_percent(
        self,
        identity: str,
        feature: Feature,
        percent: int,
        *,
        propagate: bool | None = None,
        notify: bool = True,
    ) -> list[Change]:
        identities = [identity]
        sync = self.sync if propagate is None else propagate
        if sync:
            identities = [display.identity for display in self.targets(feature)]
            if identity not in identities:
                identities.insert(0, identity)
        changes: list[Change] = []
        queued: list[tuple[str, Feature, int, int]] = []
        with self._lock:
            for display_id in identities:
                display = self.find(display_id)
                if feature not in display.features:
                    continue
                target = display.features[feature].with_percent(percent)
                display.features[feature] = target
                key = (display_id, feature)
                self._desired[key] = target
                self._errors.pop(key, None)
                generation = self._bump_locked(display_id, feature)
                self._lane(display_id)
                queued.append((display_id, feature, target.current, generation))
                changes.append(
                    Change(
                        display=display,
                        feature=feature,
                        state=target,
                        confirmed=self._confirmed.get(key),
                    )
                )
        for display_id, feat, raw, generation in queued:
            self._lanes[display_id].submit(feat, raw, generation)
        if notify and changes:
            self._notify(changes)
        return changes

    def adjust(
        self,
        feature: Feature,
        delta: int | None = None,
        *,
        identity: str | None = None,
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
                    propagate=False,
                )
            )
        return changes
