"""Turns a stream of telemetry frames into recorded laps"""

import threading
from dataclasses import dataclass, field

PLAYING = 2
PAUSED = 3
INMENU = 4
RESTARTING = 5
FROZEN = {PAUSED, INMENU}

MIN_LAP_FRACTION = 0.7 # A counted lap shorter than this fraction of the track length is discarded as invalid
REWIND_M = 20.0
TELEPORT_M = 400.0


@dataclass
class Sample:
    x: float
    y: float
    z: float
    distance: float
    speed: float


@dataclass
class Lap:
    id: int
    game_lap: int
    lap_time: float
    invalid: bool
    track: str
    variation: str
    car: str
    track_length: float
    samples: list[Sample]
    length_m: float


@dataclass
class View:
    status: str
    detail: str
    laps: list[Lap] = field(default_factory=list)
    recording: bool = False


def path_length(samples: list[Sample]) -> float:
    total = 0.0
    for a, b in zip(samples, samples[1:]):
        total += _step(a, b) ** 0.5
    return total


def _step(a: Sample, b: Sample) -> float:
    return (a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2


class Recorder:
    def __init__(self):
        self.spacing = 1.0
        self._lock = threading.Lock()
        self._laps: list[Lap] = []
        self._next_id = 1
        self._partial: list[Sample] = []
        self._prev_completed: int | None = None
        self._prev_lap_time = 0.0
        self._pending_time: Lap | None = None
        self._prev_invalid = False
        self._track_key: tuple[str, str] | None = None
        self._status = "Waiting for Automobilista 2"
        self._detail = ""
        self._recording = False

    def set_spacing(self, meters: float) -> None:
        with self._lock:
            self.spacing = max(0.25, float(meters))

    def mark_disconnected(self) -> None:
        with self._lock:
            self._partial.clear()
            self._prev_completed = None
            self._pending_time = None
            self._prev_lap_time = 0.0
            self._recording = False
            self._status = "Waiting for Automobilista 2"

    def view(self) -> View:
        with self._lock:
            return View(self._status, self._detail, list(self._laps), self._recording)

    def lap_by_id(self, lap_id: int) -> Lap | None:
        with self._lock:
            for lap in self._laps:
                if lap.id == lap_id:
                    return lap
        return None

    def delete(self, lap_id: int) -> None:
        with self._lock:
            self._laps = [lap for lap in self._laps if lap.id != lap_id]

    def ingest(self, frame) -> None:
        with self._lock:
            if frame.version != 14:
                self._recording = False
                self._status = f"Shared memory version {frame.version} (expected 14)"
                return

            if frame.game_state == RESTARTING:
                self._drop_partial("Session restarted")
                return

            if frame.game_state in FROZEN:
                self._recording = False
                self._status = "Paused"
                return

            if frame.game_state != PLAYING:
                self._drop_partial("Not on track")
                return

            if not frame.active or frame.track_length <= 1.0:
                self._recording = False
                self._status = "Waiting for a car on track"
                return

            track_key = (frame.track, frame.variation)
            if track_key != self._track_key:
                self._partial.clear()
                self._prev_completed = None
                self._prev_lap_time = 0.0
                self._pending_time = None
                self._track_key = track_key

            if self._prev_completed is None:
                self._prev_completed = frame.laps_completed
            elif frame.laps_completed != self._prev_completed:
                if frame.laps_completed == self._prev_completed + 1:
                    self._commit(frame)
                else:
                    self._partial.clear()
                    self._detail = "Lap counter reset"
                self._prev_completed = frame.laps_completed
                self._partial.clear()

            pending = self._pending_time
            if pending is not None and frame.last_lap_time > 0 and frame.last_lap_time != self._prev_lap_time:
                pending.lap_time = frame.last_lap_time
                self._detail = f"Saved lap {format_laptime(frame.last_lap_time)}"
                self._pending_time = None
            if frame.last_lap_time > 0:
                self._prev_lap_time = frame.last_lap_time

            self._append(frame)
            self._prev_invalid = frame.invalidated
            self._recording = True
            where = frame.track or "track"
            if frame.variation:
                where = f"{where} {frame.variation}"
            driven = self._partial[-1].distance if self._partial else 0.0
            speed = frame.speed * 3.6
            self._status = f"Recording {where} -- {frame.car} -- {speed:.0f} km/h -- {driven:.0f} m"

    def _drop_partial(self, status: str) -> None:
        self._partial.clear()
        self._prev_completed = None
        self._pending_time = None
        self._prev_lap_time = 0.0
        self._recording = False
        self._status = status

    def _append(self, frame) -> None:
        sample = Sample(frame.x, frame.y, frame.z, frame.lap_distance, frame.speed)
        if not self._partial:
            self._partial.append(sample)
            return
        last = self._partial[-1]
        if frame.lap_distance + REWIND_M < last.distance and frame.lap_distance > 50.0:
            self._partial = [sample]
            self._detail = "In-progress lap cleared after a rewind"
            return
        step = _step(last, sample)
        if step < self.spacing * self.spacing:
            return
        if step > TELEPORT_M * TELEPORT_M:
            self._partial = [sample]
            self._detail = "In-progress lap cleared after a position jump"
            return
        self._partial.append(sample)

    def _commit(self, frame) -> None:
        samples = self._partial
        length = path_length(samples)
        if len(samples) < 2 or length < MIN_LAP_FRACTION * frame.track_length:
            self._detail = "Incomplete lap discarded"
            return
        lap_time = 0.0
        if frame.last_lap_time > 0 and frame.last_lap_time != self._prev_lap_time:
            lap_time = frame.last_lap_time
        lap = Lap(
            id=self._next_id,
            game_lap=frame.laps_completed,
            lap_time=lap_time,
            invalid=self._prev_invalid,
            track=frame.track,
            variation=frame.variation,
            car=frame.car,
            track_length=frame.track_length,
            samples=list(samples),
            length_m=length,
        )
        self._next_id += 1
        self._laps.append(lap)
        self._pending_time = None if lap_time > 0 else lap
        self._detail = f"Saved lap {format_laptime(lap_time)}" if lap_time > 0 else "Saved lap"


def format_laptime(seconds: float) -> str:
    if seconds <= 0:
        return "—"
    minutes = int(seconds // 60)
    return f"{minutes}:{seconds - minutes * 60:06.3f}"


def self_test() -> None:
    from shared_memory import Frame

    def frame(**kw):
        base = dict(
            version=14, game_state=PLAYING, sequence=2, active=True,
            track="Test", variation="GP", car="Car", track_length=1000.0,
            laps_completed=0, lap_distance=0.0, last_lap_time=0.0,
            invalidated=False, x=0.0, y=1.0, z=0.0, speed=50.0,
        )
        base.update(kw)
        return Frame(**base)

    rec = Recorder()
    rec.set_spacing(1.0)
    for i in range(0, 1001, 1):
        rec.ingest(frame(x=float(i), lap_distance=float(i), invalidated=i > 500))
    rec.ingest(frame(x=1000, lap_distance=1, laps_completed=1, last_lap_time=91.25, invalidated=False))
    view = rec.view()
    assert len(view.laps) == 1, len(view.laps)
    lap = view.laps[0]
    assert lap.invalid
    assert abs(lap.lap_time - 91.25) < 1e-6
    assert lap.length_m > 900
    assert len(lap.samples) == 1001

    rec.ingest(frame(x=0, lap_distance=0, laps_completed=1))
    for i in range(0, 200, 10):
        rec.ingest(frame(x=float(i), lap_distance=float(i), laps_completed=1))
    rec.ingest(frame(x=200, lap_distance=0, laps_completed=2, last_lap_time=40))
    assert len(rec.view().laps) == 1

    rec.ingest(frame(game_state=PAUSED, x=9999, laps_completed=2))
    held = rec.view().status
    assert held == "Paused"

    rec.ingest(frame(game_state=RESTARTING))
    assert rec.view().status == "Session restarted"

    timed = Recorder()
    for i in range(0, 1001):
        timed.ingest(frame(x=float(i), lap_distance=float(i), last_lap_time=0))
    timed.ingest(frame(x=1000, lap_distance=2, laps_completed=1, last_lap_time=0))
    assert timed.view().laps[0].lap_time == 0
    timed.ingest(frame(x=1002, lap_distance=4, laps_completed=1, last_lap_time=88.5))
    assert abs(timed.view().laps[0].lap_time - 88.5) < 1e-6
    for i in range(0, 1001):
        timed.ingest(frame(x=1000 + float(i), lap_distance=float(i), laps_completed=1, last_lap_time=88.5))
    timed.ingest(frame(x=2000, lap_distance=2, laps_completed=2, last_lap_time=88.5))
    assert timed.view().laps[1].lap_time == 0
    timed.ingest(frame(x=2002, lap_distance=4, laps_completed=2, last_lap_time=87.0))
    assert abs(timed.view().laps[1].lap_time - 87.0) < 1e-6
    print("recorder self-test ok")


if __name__ == "__main__":
    self_test()
