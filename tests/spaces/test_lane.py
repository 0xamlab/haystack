"""algenta_spaces.lane — one worker, positions and ETAs, budgets, stalls, Gradio kwargs."""

from __future__ import annotations

import threading
import time

import pytest
from _rules import _assert_clean_copy
from algenta_spaces import lane

TIMEOUT = 5.0


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0
        self._lock = threading.Lock()

    def __call__(self) -> float:
        with self._lock:
            return self.now

    def advance(self, seconds: float) -> None:
        with self._lock:
            self.now += seconds


class Gate:
    """A callable that blocks until released and records real start/end instants."""

    def __init__(self, name: str, result: object = None):
        self.name = name
        self.result = result
        self.started = threading.Event()
        self.release = threading.Event()
        self.start_t: float | None = None
        self.end_t: float | None = None

    def __call__(self, *args: object, **kwargs: object) -> object:
        self.start_t = time.perf_counter()
        self.started.set()
        assert self.release.wait(TIMEOUT), f"{self.name} never released"
        self.end_t = time.perf_counter()
        return self.result if self.result is not None else (args, kwargs)


@pytest.fixture
def fresh_lane():
    clock = Clock()
    ln = lane.Lane(clock=clock, initial_estimate_s=0.5, alpha=0.5)
    yield ln, clock
    ln.shutdown(wait=False)


def test_single_in_flight_second_starts_after_first_ends(fresh_lane):
    ln, _ = fresh_lane
    first, second = Gate("first", "a"), Gate("second", "b")
    t1 = ln.submit(first, budget_s=TIMEOUT, label="first")
    t2 = ln.submit(second, budget_s=TIMEOUT, label="second")
    assert first.started.wait(TIMEOUT)
    assert not second.started.wait(0.1), "second started while first was running"
    assert ln.depth() == 2
    assert ln.stats()["running"] == "first"
    first.release.set()
    assert t1.result() == "a"
    assert second.started.wait(TIMEOUT)
    assert second.start_t is not None and first.end_t is not None
    assert second.start_t >= first.end_t
    second.release.set()
    assert t2.result() == "b"
    assert ln.depth() == 0
    assert (t1.state, t2.state) == (lane.DONE, lane.DONE)


def test_positions_eta_and_ewma_from_an_injectable_clock(fresh_lane):
    ln, clock = fresh_lane
    gates = [Gate(f"g{i}", i) for i in range(3)]
    tickets = [ln.submit(g, budget_s=TIMEOUT, label=g.name) for g in gates]
    assert [t.position for t in tickets] == [0, 1, 2]
    # ETA = position x EWMA; before any sample the EWMA is the initial estimate (0.5 s).
    assert [t.eta_s for t in tickets] == [0.0, 0.5, 1.0]
    assert all(t.submitted_at == 1000.0 for t in tickets)
    assert tickets[1].deadline == pytest.approx(1000.0 + 0.5 + TIMEOUT)

    assert gates[0].started.wait(TIMEOUT)
    clock.advance(2.0)  # the first call takes 2 s on the fake clock
    gates[0].release.set()
    assert tickets[0].result() == 0
    assert tickets[0].duration_s() == pytest.approx(2.0)
    # alpha 0.5: 0.5 * 2.0 + 0.5 * 0.5 = 1.25
    assert ln.ewma_s == pytest.approx(1.25)
    late = Gate("late", 9)
    t_late = ln.submit(late, budget_s=TIMEOUT, label="late")
    assert t_late.position == 2 and t_late.eta_s == pytest.approx(2.5)

    for gate, ticket in zip(gates[1:], tickets[1:], strict=True):
        assert gate.started.wait(TIMEOUT)
        clock.advance(1.0)
        gate.release.set()
        ticket.result()
    assert late.started.wait(TIMEOUT)
    late.release.set()
    assert t_late.result() == 9
    stats = ln.stats()
    assert stats["completed"] == 4 and stats["failed"] == 0 and stats["samples"] == 4
    assert stats["depth"] == 0 and stats["running"] is None and stats["max_depth_seen"] == 3
    assert stats["stalled"] is False
    assert 0 < stats["ewma_s"] < 2.0


def test_timeout_of_a_running_call_stalls_the_lane_until_it_returns(fresh_lane):
    ln, _ = fresh_lane
    runaway = Gate("runaway", "late result")
    ticket = ln.submit(runaway, budget_s=0.05, label="runaway")
    assert runaway.started.wait(TIMEOUT)
    with pytest.raises(lane.LaneTimeout) as info:
        ticket.result()
    err = info.value
    assert err.code == "lane_timeout" and err.ticket is ticket
    assert err.card() == {"error_code": "lane_timeout", "hint": lane.TIMEOUT_HINT}
    assert ticket.state == lane.TIMED_OUT and ticket.error_code == "lane_timeout"
    assert ticket.done is False
    assert ln.stalled is True
    with pytest.raises(lane.LaneBusy) as busy:
        ln.submit(lambda: 1, budget_s=1.0, label="next")
    assert busy.value.code == "lane_busy" and busy.value.card()["hint"] == lane.BUSY_HINT
    # the native call finishes in the background; the lane then takes work again
    runaway.release.set()
    assert ticket.wait(TIMEOUT)
    assert ticket.state == lane.TIMED_OUT  # a timed-out ticket stays timed out
    assert ln.stalled is False and ln.depth() == 0
    assert ln.run(lambda x: x * 2, 21, budget_s=1.0, label="next") == 42
    stats = ln.stats()
    assert stats["timed_out"] == 1 and stats["completed"] == 2 and stats["cancelled"] == 0


def test_timeout_of_a_queued_ticket_cancels_it_without_stalling(fresh_lane):
    ln, clock = fresh_lane
    blocker = Gate("blocker", 1)
    t_block = ln.submit(blocker, budget_s=TIMEOUT, label="blocker")
    calls: list[str] = []

    def never_runs() -> None:
        calls.append("ran")

    queued = ln.submit(never_runs, budget_s=0.05, label="queued")
    assert blocker.started.wait(TIMEOUT)
    # the fake clock makes the deadline arithmetic explicit: past it, the wait is zero
    clock.advance(queued.eta_s + 1.0)
    with pytest.raises(lane.LaneTimeout):
        queued.result()
    assert queued.state == lane.CANCELLED and queued.done is True
    assert ln.stalled is False and ln.depth() == 1
    blocker.release.set()
    assert t_block.result() == 1
    time.sleep(0.05)
    assert calls == []
    assert ln.stats()["cancelled"] == 1 and ln.stats()["timed_out"] == 0


def test_exceptions_propagate_from_result_and_are_counted(fresh_lane):
    ln, _ = fresh_lane

    def boom() -> None:
        raise KeyError("no such key")

    ticket = ln.submit(boom, budget_s=1.0, label="boom")
    with pytest.raises(KeyError, match="no such key"):
        ticket.result()
    assert ticket.state == lane.FAILED and ticket.error_code is None
    assert isinstance(ticket.exception(), KeyError)
    assert ln.stats()["failed"] == 1 and ln.stats()["completed"] == 0
    # the lane keeps working after a failure
    assert ln.run(sorted, [3, 1, 2], budget_s=1.0, label="sort") == [1, 2, 3]
    assert ln.run(dict, a=1, budget_s=1.0, label="kwargs") == {"a": 1}


def test_depth_bound_validation_and_shutdown(fresh_lane):
    ln, _ = fresh_lane
    small = lane.Lane(max_depth=1)
    blocker = Gate("blocker")
    small.submit(blocker, budget_s=TIMEOUT, label="one")
    with pytest.raises(lane.LaneFull) as full:
        small.submit(blocker, budget_s=TIMEOUT, label="two")
    assert full.value.code == "lane_full"
    blocker.release.set()
    small.shutdown()
    with pytest.raises(lane.LaneClosed):
        small.submit(lambda: 1, budget_s=1.0, label="late")
    with pytest.raises(ValueError):
        ln.submit(lambda: 1, budget_s=0, label="x")
    with pytest.raises(ValueError):
        ln.submit(lambda: 1, budget_s=1, label=" ")
    with pytest.raises(ValueError):
        lane.Lane(alpha=0)
    with pytest.raises(ValueError):
        lane.Lane(initial_estimate_s=0)
    with pytest.raises(ValueError):
        lane.Lane(max_depth=0)
    with pytest.raises(RuntimeError):
        lane.Ticket("orphan", 1.0, 0, 0.0, 0.0).result()


def test_ticket_snapshot_is_plain_data(fresh_lane):
    ln, clock = fresh_lane
    gate = Gate("snap", "ok")
    ticket = ln.submit(gate, budget_s=2.0, label="snap")
    assert gate.started.wait(TIMEOUT)
    assert ticket.snapshot() == {
        "label": "snap",
        "state": "running",
        "position": 0,
        "eta_s": 0.0,
        "budget_s": 2.0,
        "duration_s": None,
        "error_code": None,
    }
    clock.advance(0.25)
    gate.release.set()
    ticket.result()
    snap = ticket.snapshot()
    assert snap["state"] == "done" and snap["duration_s"] == 0.25


def test_gradio_hooks_are_plain_dicts_without_gradio():
    hooks = lane.gradio_hooks()
    assert hooks == {
        "event": {"concurrency_id": "native", "concurrency_limit": 1},
        "queue": {"default_concurrency_limit": 1, "max_size": 8},
    }
    assert lane.gradio_hooks(max_size=3)["queue"]["max_size"] == 3
    with pytest.raises(ValueError):
        lane.gradio_hooks(max_size=0)


def test_hints_obey_the_copy_rules():
    for text in (lane.TIMEOUT_HINT, lane.BUSY_HINT, lane.FULL_HINT, lane.CLOSED_HINT):
        _assert_clean_copy(text)
