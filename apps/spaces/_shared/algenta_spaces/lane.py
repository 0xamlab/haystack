"""The one native lane — every native call in a Space goes through a single worker.

Why one worker. ABI §9: the compiled Community libraries hold one device-wide
worker slot (a blocking `flock` on `/dev/null`, no timeout). A second native
call from any thread or process does not run in parallel; it waits inside the
library, holding its thread, and any timing taken from that thread reads the
queue as work. So a Space never issues two native calls at once: Gradio's queue
serialises requests at the HTTP layer (`gradio_hooks()` gives the kwargs), and
`Lane` serialises inside the process for everything native — Hub kernels,
`algenta-runtime-native`, the arena subprocess (uncapped, but sharing the CPU).

What a ticket knows. `Lane.submit` returns a `Ticket` with its queue position
at submit time (0 runs at once) and an ETA of `position × EWMA` of recent call
durations, so the UI can show "2 ahead · about 3 s" before the call starts.

Budgets. A native call cannot be interrupted from Python, so the budget bounds
the WAIT, not the call: `ticket.result()` waits until `submitted_at + eta_s +
budget_s`; past that it raises `LaneTimeout` (code `lane_timeout`, the code an
unavailable card prints). A ticket that has not started is cancelled outright
and never runs. A ticket that is running keeps running in the background; the
lane is then *stalled* and refuses new work with `LaneBusy` (`lane_busy`) until
the runaway call returns, because queueing behind a call of unknown length
would only manufacture more timeouts. Depth is bounded too (`lane_full`).

Every clock read is injectable; the tests drive fake callables with events.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

log = logging.getLogger(__name__)

NATIVE_CONCURRENCY_ID = "native"
QUEUE_MAX_SIZE = 8
DEFAULT_ESTIMATE_S = 0.5
EWMA_ALPHA = 0.3

CODE_TIMEOUT = "lane_timeout"
CODE_BUSY = "lane_busy"
CODE_FULL = "lane_full"
CODE_CLOSED = "lane_closed"

QUEUED = "queued"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
TIMED_OUT = "timed_out"
CANCELLED = "cancelled"
STATES = (QUEUED, RUNNING, DONE, FAILED, TIMED_OUT, CANCELLED)

TIMEOUT_HINT = "The call is still running; the lane takes new work when it returns."
BUSY_HINT = "A previous call is still running; try again in a moment."
FULL_HINT = "The lane is full; try again in a moment."
CLOSED_HINT = "The lane has shut down."


class LaneError(Exception):
    """A lane refusal; `code` is what the unavailable card prints."""

    code = "lane_error"
    hint = ""

    def __init__(self, message: str):
        super().__init__(f"{self.code}: {message}")
        self.message = message

    def card(self) -> dict[str, str]:
        """`{"error_code": ..., "hint": ...}` — the kwargs `cards.render_unavailable_card` takes."""
        return {"error_code": self.code, "hint": self.hint}


class LaneTimeoutError(LaneError):
    """The wait for a ticket exceeded its budget; the call itself may still be running."""

    code = CODE_TIMEOUT
    hint = TIMEOUT_HINT

    def __init__(self, ticket: Ticket):
        super().__init__(f"{ticket.label} waited past its {ticket.budget_s:g} s budget")
        self.ticket = ticket


class LaneBusyError(LaneError):
    """The lane refuses new work while a timed-out call is still running."""

    code = CODE_BUSY
    hint = BUSY_HINT


class LaneFullError(LaneError):
    code = CODE_FULL
    hint = FULL_HINT


class LaneClosedError(LaneError):
    code = CODE_CLOSED
    hint = CLOSED_HINT


# The short names the Space handlers and the runbook use.
LaneTimeout = LaneTimeoutError
LaneBusy = LaneBusyError
LaneFull = LaneFullError
LaneClosed = LaneClosedError


class Ticket:
    """One submitted call: where it stood, when it ran, what it returned."""

    def __init__(self, label: str, budget_s: float, position: int, eta_s: float, now: float):
        self.label = label
        self.budget_s = budget_s
        self.position = position
        self.eta_s = eta_s
        self.submitted_at = now
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.state = QUEUED
        self._done = threading.Event()
        self._result: Any = None
        self._exception: BaseException | None = None
        self._future: Future[None] | None = None
        self._lane: Lane | None = None

    @property
    def deadline(self) -> float:
        """The clock instant after which waiting stops: submit + ETA + budget."""
        return self.submitted_at + self.eta_s + self.budget_s

    @property
    def done(self) -> bool:
        return self._done.is_set()

    @property
    def timed_out(self) -> bool:
        return self.state == TIMED_OUT

    @property
    def error_code(self) -> str | None:
        """`lane_timeout` after a timeout, else None (a failed call carries its own exception)."""
        return CODE_TIMEOUT if self.timed_out else None

    def duration_s(self) -> float | None:
        if self.started_at is None or self.finished_at is None:
            return None
        return max(0.0, self.finished_at - self.started_at)

    def wait(self, timeout: float | None = None) -> bool:
        """Block up to `timeout` seconds for completion; True when the call finished."""
        return self._done.wait(timeout)

    def exception(self) -> BaseException | None:
        """The exception the callable raised, once done; None otherwise."""
        return self._exception if self.done else None

    def result(self) -> Any:
        """The callable's return value, waiting until the deadline.

        Raises `LaneTimeout` when the deadline passes first (cancelling the call
        if it has not started), or re-raises the callable's own exception.
        """
        if self._lane is None:
            raise RuntimeError("ticket was not issued by a lane")
        remaining = max(0.0, self.deadline - self._lane.clock())
        if not self._done.wait(remaining):
            self._lane._time_out(self)
            if self.timed_out or self.state == CANCELLED:
                raise LaneTimeoutError(self)
        if self._exception is not None:
            raise self._exception
        return self._result

    def snapshot(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "state": self.state,
            "position": self.position,
            "eta_s": round(self.eta_s, 3),
            "budget_s": self.budget_s,
            "duration_s": None if self.duration_s() is None else round(self.duration_s() or 0, 4),
            "error_code": self.error_code,
        }


class Lane:
    """A single-worker executor with queue position, ETA, budgets and a stall guard."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        alpha: float = EWMA_ALPHA,
        initial_estimate_s: float = DEFAULT_ESTIMATE_S,
        max_depth: int = QUEUE_MAX_SIZE,
        name: str = NATIVE_CONCURRENCY_ID,
    ):
        if not 0.0 < alpha <= 1.0:
            raise ValueError("alpha is a fraction in (0, 1]")
        if initial_estimate_s <= 0:
            raise ValueError("initial_estimate_s must be positive")
        if max_depth < 1:
            raise ValueError("max_depth must be at least 1")
        self.clock = clock
        self.name = name
        self.alpha = alpha
        self.max_depth = max_depth
        self._ewma_s = float(initial_estimate_s)
        self._samples = 0
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"algenta-{name}")
        self._pending: list[Ticket] = []
        self._running: Ticket | None = None
        self._stalled = 0
        self._completed = 0
        self._failed = 0
        self._timed_out = 0
        self._cancelled = 0
        self._max_depth_seen = 0
        self._closed = False

    # -- public -------------------------------------------------------------------------

    @property
    def ewma_s(self) -> float:
        with self._lock:
            return self._ewma_s

    @property
    def stalled(self) -> bool:
        """True while a timed-out call is still running (new work is refused)."""
        with self._lock:
            return self._stalled > 0

    def depth(self) -> int:
        """Tickets queued or running right now."""
        with self._lock:
            return len(self._pending)

    def submit(
        self,
        fn: Callable[..., Any],
        /,
        *args: Any,
        budget_s: float,
        label: str,
        **kwargs: Any,
    ) -> Ticket:
        """Queue `fn(*args, **kwargs)` on the one worker and return its ticket at once."""
        if budget_s <= 0:
            raise ValueError("budget_s must be positive")
        if not label.strip():
            raise ValueError("label is empty")
        with self._lock:
            if self._closed:
                raise LaneClosedError(f"{label}: the lane is closed")
            if self._stalled:
                raise LaneBusyError(f"{label}: a timed-out call is still running")
            if len(self._pending) >= self.max_depth:
                raise LaneFullError(f"{label}: {len(self._pending)} tickets already waiting")
            position = len(self._pending)
            ticket = Ticket(label, budget_s, position, position * self._ewma_s, self.clock())
            ticket._lane = self
            self._pending.append(ticket)
            self._max_depth_seen = max(self._max_depth_seen, len(self._pending))
            ticket._future = self._pool.submit(self._run, ticket, fn, args, kwargs)
        return ticket

    def run(
        self, fn: Callable[..., Any], /, *args: Any, budget_s: float, label: str, **kwargs: Any
    ) -> Any:
        """`submit` then `result`: the handler-side one-liner."""
        return self.submit(fn, *args, budget_s=budget_s, label=label, **kwargs).result()

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "depth": len(self._pending),
                "running": None if self._running is None else self._running.label,
                "stalled": self._stalled > 0,
                "ewma_s": round(self._ewma_s, 4),
                "samples": self._samples,
                "completed": self._completed,
                "failed": self._failed,
                "timed_out": self._timed_out,
                "cancelled": self._cancelled,
                "max_depth_seen": self._max_depth_seen,
                "max_depth": self.max_depth,
            }

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            self._closed = True
        self._pool.shutdown(wait=wait, cancel_futures=True)

    # -- internals ----------------------------------------------------------------------

    def _run(self, ticket: Ticket, fn: Callable[..., Any], args: tuple, kwargs: dict) -> None:
        with self._lock:
            ticket.started_at = self.clock()
            if ticket.state == QUEUED:
                ticket.state = RUNNING
            self._running = ticket
        try:
            ticket._result = fn(*args, **kwargs)
        except Exception as exc:  # the caller re-raises it from result(); nothing is hidden
            ticket._exception = exc
            log.warning("%s failed: %s: %s", ticket.label, type(exc).__name__, exc)
        except BaseException as exc:  # SystemExit / KeyboardInterrupt: record, then let it go
            ticket._exception = exc
            raise
        finally:
            with self._lock:
                ticket.finished_at = self.clock()
                duration = ticket.duration_s() or 0.0
                self._ewma_s = self.alpha * duration + (1.0 - self.alpha) * self._ewma_s
                self._samples += 1
                if ticket.state == TIMED_OUT:
                    self._stalled -= 1
                    log.info("%s returned %.3f s after its timeout", ticket.label, duration)
                elif ticket._exception is not None:
                    ticket.state = FAILED
                else:
                    ticket.state = DONE
                if ticket._exception is not None:
                    self._failed += 1
                else:
                    self._completed += 1
                self._running = None
                self._forget(ticket)
                ticket._done.set()

    def _forget(self, ticket: Ticket) -> None:
        if ticket in self._pending:
            self._pending.remove(ticket)

    def _time_out(self, ticket: Ticket) -> None:
        """Called from `Ticket.result` after the deadline: cancel if queued, else mark stalled.

        A ticket whose future refuses to cancel is running, or about to (the
        worker has taken it and is waiting for this lock), so it is a stall
        either way; `_run` keeps the `timed_out` state when it starts.
        """
        with self._lock:
            if ticket.done:
                return
            future = ticket._future
            if future is not None and future.cancel():
                ticket.state = CANCELLED
                ticket.finished_at = self.clock()
                self._cancelled += 1
                self._forget(ticket)
                ticket._done.set()
                log.info("%s cancelled before it started", ticket.label)
                return
            ticket.state = TIMED_OUT
            self._stalled += 1
            self._timed_out += 1
            log.warning("%s still running past its %.3g s budget", ticket.label, ticket.budget_s)


def gradio_hooks(*, max_size: int = QUEUE_MAX_SIZE) -> dict[str, dict[str, Any]]:
    """The kwargs every native handler and the queue take — plain dicts, no gradio import.

    `btn.click(fn, inputs, outputs, **gradio_hooks()["event"])` and
    `blocks.queue(**gradio_hooks()["queue"])`.
    """
    if max_size < 1:
        raise ValueError("max_size must be at least 1")
    return {
        "event": {"concurrency_id": NATIVE_CONCURRENCY_ID, "concurrency_limit": 1},
        "queue": {"default_concurrency_limit": 1, "max_size": max_size},
    }
