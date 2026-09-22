"""Staged boot status — what a Space shows while it warms kernels, models and probes.

Lifted from the `_BOOT` / `_set_stage` / `boot_status` pattern in
`apps/spaces/governed-agent/space_core.py` and made a class: fixed stages
declared up front, thread-safe transitions with timestamps from an injectable
clock, a JSON snapshot for `/health`, and an HTML card for the UI.
"""

from __future__ import annotations

import html
import json
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from typing import Any

from .css import rule, stylesheet
from .shell import SUBLINE_WORDS, check_copy

PENDING = "pending"
RUNNING = "running"
DONE = "done"
ERROR = "error"
STATES = (PENDING, RUNNING, DONE, ERROR)

STATE_TEXT: dict[str, str] = {
    PENDING: "waiting",
    RUNNING: "running",
    DONE: "ready",
    ERROR: "failed",
}
BOOT_TITLE = "Starting up"
READY_TITLE = "Ready"


@dataclass
class Stage:
    id: str
    label: str
    state: str = PENDING
    detail: str = ""
    started_at: float | None = None
    finished_at: float | None = None

    def elapsed_s(self, now: float) -> float:
        if self.started_at is None:
            return 0.0
        end = now if self.finished_at is None else self.finished_at
        return max(0.0, end - self.started_at)


class BootRegistry:
    """Fixed, ordered stages with thread-safe state transitions."""

    def __init__(
        self, stages: Iterable[tuple[str, str]], *, clock: Callable[[], float] = time.time
    ):
        self._clock = clock
        self._lock = threading.Lock()
        self._stages: dict[str, Stage] = {}
        for stage_id, label in stages:
            if stage_id in self._stages:
                raise ValueError(f"duplicate stage id {stage_id!r}")
            check_copy(label, max_words=SUBLINE_WORDS, what=f"stage {stage_id!r} label")
            self._stages[stage_id] = Stage(id=stage_id, label=label)
        if not self._stages:
            raise ValueError("a registry needs at least one stage")
        self._boot_started = clock()

    def set(self, stage_id: str, state: str, detail: str = "") -> None:
        if state not in STATES:
            raise ValueError(f"unknown state {state!r}; expected one of {STATES}")
        now = self._clock()
        with self._lock:
            stage = self._stages[stage_id]
            stage.state = state
            stage.detail = detail
            if state == RUNNING:
                stage.started_at = now
                stage.finished_at = None
            elif state in (DONE, ERROR):
                if stage.started_at is None:
                    stage.started_at = now
                stage.finished_at = now
            else:
                stage.started_at = None
                stage.finished_at = None

    def start(self, stage_id: str) -> None:
        self.set(stage_id, RUNNING)

    def done(self, stage_id: str, detail: str = "") -> None:
        self.set(stage_id, DONE, detail)

    def fail(self, stage_id: str, detail: str) -> None:
        self.set(stage_id, ERROR, detail)

    @property
    def ready(self) -> bool:
        with self._lock:
            return all(stage.state == DONE for stage in self._stages.values())

    @property
    def error(self) -> str | None:
        with self._lock:
            for stage in self._stages.values():
                if stage.state == ERROR:
                    return stage.detail or stage.label
            return None

    def snapshot(self) -> dict[str, Any]:
        """A plain-data copy the UI polls and `/health` returns."""
        now = self._clock()
        with self._lock:
            stages = []
            for stage in self._stages.values():
                data = asdict(stage)
                data["elapsed_s"] = round(stage.elapsed_s(now), 3)
                stages.append(data)
            states = [stage.state for stage in self._stages.values()]
            error = next(
                (s.detail or s.label for s in self._stages.values() if s.state == ERROR), None
            )
        return {
            "ready": all(state == DONE for state in states),
            "error": error,
            "elapsed_s": round(max(0.0, now - self._boot_started), 3),
            "stages": stages,
        }

    def to_json(self) -> str:
        return to_json(self.snapshot())

    def render_html(self) -> str:
        return render_boot_html(self.snapshot())


def to_json(snapshot: dict[str, Any]) -> str:
    return json.dumps(snapshot, sort_keys=True, separators=(",", ":"))


def render_boot_html(snapshot: dict[str, Any]) -> str:
    """The boot card: one row per stage, state word, detail and elapsed seconds."""
    rows = []
    for stage in snapshot["stages"]:
        state = stage["state"]
        if state not in STATE_TEXT:
            raise ValueError(f"unknown state {state!r}")
        detail = (
            f'<span class="alg-boot-detail">{html.escape(str(stage["detail"]))}</span>'
            if stage.get("detail")
            else ""
        )
        elapsed = f"{float(stage.get('elapsed_s', 0.0)):.1f} s" if stage.get("started_at") else ""
        rows.append(
            f'<li class="alg-boot-row alg-boot-{state}" data-stage="{html.escape(stage["id"])}">'
            f'<span class="alg-boot-state">{STATE_TEXT[state]}</span>'
            f'<span class="alg-boot-label">{html.escape(str(stage["label"]))}</span>'
            f"{detail}"
            f'<span class="alg-boot-elapsed">{elapsed}</span>'
            "</li>"
        )
    title = READY_TITLE if snapshot.get("ready") else BOOT_TITLE
    error = snapshot.get("error")
    error_html = f'<p class="alg-boot-fail">{html.escape(str(error))}</p>' if error else ""
    return (
        '<section class="alg-boot" aria-live="polite">'
        f'<h2 class="alg-boot-title">{title}</h2>'
        f'<ol class="alg-boot-list">{"".join(rows)}</ol>'
        f"{error_html}"
        "</section>"
    )


_CAPTION = "font-size: var(--alg-caption-size); line-height: var(--alg-caption-line);"
_BODY = "font-size: var(--alg-body-size); line-height: var(--alg-body-line);"

BOOT_CSS = stylesheet(
    rule(
        "alg-boot",
        "font-family: var(--alg-font); color: var(--alg-text); background: var(--alg-surface);"
        " border: 1px solid var(--alg-hairline); border-radius: var(--alg-radius-card);"
        " padding: 16px 24px;",
    ),
    rule(
        "alg-boot-title",
        "font-size: var(--alg-title-size); line-height: var(--alg-title-line);"
        " letter-spacing: var(--alg-title-tracking); font-weight: var(--alg-title-weight);"
        " margin: 0 0 12px;",
    ),
    rule(
        "alg-boot-list",
        "list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px;",
    ),
    rule(
        "alg-boot-row",
        f"display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; {_BODY}",
    ),
    rule(
        "alg-boot-state",
        f"flex: 0 0 64px; font-family: var(--alg-font-mono); {_CAPTION} color: var(--alg-text-2);",
    ),
    rule("alg-boot-done", "color: var(--alg-ok);", suffix=" .alg-boot-state"),
    rule("alg-boot-error", "color: var(--alg-err);", suffix=" .alg-boot-state"),
    rule("alg-boot-running", "color: var(--alg-accent-to);", suffix=" .alg-boot-state"),
    rule("alg-boot-label", "flex: 1 1 240px;"),
    rule("alg-boot-detail", f"{_CAPTION} color: var(--alg-text-2);"),
    rule(
        "alg-boot-elapsed",
        f"font-family: var(--alg-font-mono); {_CAPTION} font-variant-numeric: tabular-nums;"
        " color: var(--alg-text-2);",
    ),
    rule("alg-boot-fail", f"color: var(--alg-err); {_BODY} margin: 12px 0 0;"),
)
