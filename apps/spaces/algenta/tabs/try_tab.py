"""Try it — the page opens on an already-measured result and re-measures on request.

The hero is ``algenta-stats · ab_testing.z_test_proportions`` with the family's card example
(50 of 1,000 against 65 of 1,000). ``measure_hero`` runs it under the rulebook through the
one native lane — a correctness gate against ``statsmodels.stats.proportion.proportions_ztest``
first, then interleaved repeats — and the card shows the kernel-call median, the result, the
parity bound that was actually checked (z to 1e-9, p to 1e-6: the kernel's normal CDF differs
from statsmodels' by up to 1.4e-7 on the p-value — the largest gap over 408 random inputs on
``torch25-cpu-aarch64-darwin``, 2026-09-22; 8.6e-8 on the card example — so nothing tighter is
ever claimed), the machine and the UTC stamp. Four inputs and Run measure the visitor's own
numbers the same way; the inputs are checked before anything native runs (whole numbers, trials
of at least one, successes between zero and the trials) and a refusal is one sentence under the
fields.

The opening card is robust by design: boot measures the hero up to ``boot_sequence.HERO_ATTEMPTS``
times with backoff when the rulebook says noisy, then a ``HeroTracker`` keeps re-measuring every
``retry_s`` seconds in the background until one attempt is measured. The tab paints the latest
*measured* card — on page load and again on its timer — and, while none exists, a card of the
same geometry that tells the truth about the moment: the pulsing skeleton ("Measuring on this
machine · attempt 7") only while an attempt is actually running, and otherwise the settled card
("Not measured on this host yet · attempt 7 · load 82 on 16 vCPU · next attempt at 23:41:07
UTC"), still, with the neutral `not measured yet` chip — a card never pulses while nothing is
being measured. The not-recorded card appears only for the visitor's own run, never as the
first paint. Under the form, the status row takes no space until a run puts a chip in it; the
finished chip reads `done in 6.07 ms · this container · <UTC>` — a duration with its unit, its
provenance and its stamp.

A run the rulebook did not record still ran: the kernel answered and the correctness gate
compared that answer with statsmodels before any timing began. So the not-recorded card keeps
everything that is not a timing (`render_unrecorded_hero_card`, fix round 5 — the staging review
found 10 of 10 visitor Runs ending in a quiet card that dropped the z and p the visitor asked
for): it is the fleet's not-recorded card (`cards.render_not_recorded_card`) with the two
proportions as its subtitle, the z/p result block, the parity chips (verdict, bound, reference
version), the kernel revision and the transport note; where the measured card draws its timing
(the hero figure, P95, MAD, spread, n) this card draws one quiet `timing` row — the rulebook's
cause in words and the neutral `not recorded` chip. A run that produced no answer at all (an
error before the gate) is the same card with the cause and no result.

The timing rows themselves come from the shared rulebook harness (`bench.run_cell`); the `n`
chip prints exactly what the harness ran — `n = 21` repeats, or `n = 21 × k calls` when the
harness timed each repeat over an inner batch of k back-to-back calls (`repeats_label`), the
same words in How this is measured.

The four inputs are checked before anything native runs — the contract's types and 64-bit
ranges, the form's own rule that a whole number at or above 2^53 cannot be trusted from a
number box, and the shared ``playground.FIELD_RULES`` for the z-test (trials of at least one,
successes between zero and the trials) — and a refusal is one sentence under the fields with
the field's label in front, never its identifier. The permalink protocol reports exactly what
the tab applied (``permalink_applied``): the whole numbers below 2^53 a link's ``args`` carry
for the hero's four fields, under the hero's function or none; anything else — a decimal, a
foreign function — restores nothing, and the shell's box says so.

Three chips continue the story: Race it against Python (the Races tab, betweenness selected),
Copy the 3-line install (exactly three lines — pip, ``get_kernel`` trusting this one repository,
the call with the visitor's numbers — copied to the clipboard as well as shown) and Same call
over MCP (the JSON-RPC frame). The card's primary copy is human — the title, "50 of 1,000 vs 65 of
1,000", the figures with their units — and the identifiers live in the Reproduce disclosure: the
function's dotted name, the twenty-repository ``kernels`` snippet, the build variant and pinned
revision, the library versions and a permalink that restores the visitor's numbers
(``?tab=try&args=...``). Below, "Where this runs" is a band of the design system's stat tiles
(``cards.tile``) whose figures are computed, fetched or measured — never typed: Hub kernels (the
functions and families loaded in this container, counted at boot and stamped), Hosted API + MCP
(the tool count from the ``algenta_mcp`` registry when it is installed, else from the live
``/mcp/tools`` endpoint, each labelled with its source) and, only when the Space variable
``GPU_STATUS_URL`` names the GPU stage's status endpoint, the GPU stage tile (polled every thirty
seconds; offline shows the last logged measurement with its stamp, or the code). Without that
variable the band is the two real tiles — nothing stands in for a stage that is not wired.

Every code block on the tab — the install or MCP snippet the chips show (captioned ``Install``
or ``MCP request``), the full ``kernels`` snippet under Reproduce — is ``common.code_editor``:
our caption above an editor without Gradio's block label or line-number gutter, shown and
hidden together. The form row keeps its two columns level: the four inputs on one surface, Run
beside them on the boxes' baseline, the status row under both — measured at 0 px of void under
either column at rest and after a run (fix round 4).
"""

from __future__ import annotations

import dataclasses
import logging
import math
import re
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from importlib import metadata
from typing import Any

from algenta_spaces import bench, cards, hubkernel, playground, shell
from algenta_spaces.lane import Lane, LaneClosedError, Ticket
from algenta_spaces.runtime import utc_stamp

import gpu_status
import permalink as permalink_mod
from tabs import TAB_RACE, TAB_TRY, Deps, HeroResult, ParityCheck, TabSpec, common

log = logging.getLogger(__name__)

HERO_FAMILY = "stats"
HERO_MODULE = "ab_testing"
HERO_FUNCTION = "z_test_proportions"
HERO_QUALNAME = f"{HERO_MODULE}.{HERO_FUNCTION}"
HERO_ARGS: Mapping[str, int] = {"successes_a": 50, "n_a": 1000, "successes_b": 65, "n_b": 1000}
HERO_LANE = "algenta-stats"
HERO_BUDGET_S = 20.0
Z_TOL = 1e-9
#: The kernel's p agrees with statsmodels to 1.4e-7 at worst over 408 random inputs (measured
#: 2026-09-22 on `torch25-cpu-aarch64-darwin`); the bound the card claims keeps a decade of room.
P_TOL = 1e-6
REFERENCE_DIST = "statsmodels"
FEATURE = "kernels"
RACE_PRESELECT = "betweenness"
#: The shell's handle in `connect(gr, tabs, handles)`: its permalink box and public base.
SHELL_HANDLE = "shell"
#: Rulebook verdicts a later attempt can change; a gate failure or an error is final.
TRANSIENT_STATUSES: tuple[str, ...] = (bench.STATUS_NOISY, bench.STATUS_OVER_BUDGET)

GPU_POLL_S = 30.0
#: The Space variable that wires the GPU stage tile (`gpu_status.STATUS_URL_ENV`, an https
#: endpoint); unset, the band has no GPU tile at all.
GPU_STATUS_URL_ENV: str = gpu_status.STATUS_URL_ENV
GPU_LOG_URL_ENV = "ALGENTA_GPU_LOG_URL"
GPU_LOG_URL_DEFAULT = (
    "https://huggingface.co/datasets/thyn-ai/algenta-arena-results/resolve/main/gpu_status.jsonl"
)
MCP_TOOLS_URL = "https://api.algenta.ai/mcp/tools"
#: The live tile's meta in words — the host itself belongs in Reproduce, never in primary copy.
LIVE_HOSTED = "live · hosted API"
MCP_DIST = "algenta-mcp"
CODE_MCP_UNREACHABLE = "mcp_tools_unreachable"

TITLE = "Two-proportion z-test"
HERO_LABEL = "per kernel call · median"
LABEL_A = "Successes A"
LABEL_NA = "Trials A"
LABEL_B = "Successes B"
LABEL_NB = "Trials B"
LABELS: Mapping[str, str] = {
    "successes_a": LABEL_A,
    "n_a": LABEL_NA,
    "successes_b": LABEL_B,
    "n_b": LABEL_NB,
}
LABEL_RUN = "Run"
LABEL_RACE = "Race it against Python"
LABEL_INSTALL = "Copy the 3-line install"
LABEL_MCP = "Same call over MCP"
#: The captions of the snippet the two chips show (`common.code_editor`, no stock block label).
CAPTION_INSTALL = "Install"
CAPTION_MCP = "MCP request"
LABEL_HOW = "How this is measured"
LABEL_REPRODUCE = "Reproduce"
LABEL_FULL_SNIPPET = "kernels, every published repository trusted"
LABEL_PERMALINK = "Permalink"
TILE_HUB = "Mojo kernels on the Hub"
TILE_HOSTED = "Hosted API + MCP"
TILE_GPU = "GPU stage"
OFFLINE = "offline"
GPU_OFFLINE = "GPU stage offline"
MEASURING = "Measuring on this machine"
NOT_MEASURED = "Not measured on this host yet"
NEXT_ATTEMPT = "next attempt at"
COUNTED_AT_BOOT = "counted at boot"
API_NAMES = ("try_run", "try_snippet_install", "try_snippet_mcp", "try_gpu_status")

#: Rulebook v0.4's inner batch in the shared card's one sentence (`cards.HOW_TIMED`), so How
#: this is measured and the card's `n = 21 × k calls` chip say the same thing on every tab.
HOW_TIMED: str = getattr(cards, "HOW_TIMED", "")
HOW_MEASURED = (
    f"Rulebook v{bench.RULEBOOK_VERSION}: the call runs once and its result is compared with "
    f"{REFERENCE_DIST} (z within {Z_TOL:g}, p within {P_TOL:g}); {bench.WARMUPS} warm-ups are "
    f"discarded; {bench.REPEATS_FAST} timed repeats follow"
    + (f" — {HOW_TIMED}" if HOW_TIMED else "")
    + f"; the card shows the median, P95, MAD and the spread. A spread above {bench.CV_MAX:.0%}, "
    f"or a mean more than {bench.CV_MAX:.0%} off the median, is noisy and not recorded — the card "
    "then keeps the result and the parity check and withholds only the timing; the foot prints "
    "the machine's 1-minute load average at the time. Every timing includes the JSON "
    "marshalling across the C ABI."
)
#: Plain words for the contract's refusals, said with the field's label in front.
REASON_WORDS: Mapping[str, str] = {
    "must be an int": "must be a whole number",
    "must be an int, not a bool": "must be a whole number",
    "is required": "is required",
}
_IDENT_WORD_RE = re.compile(r"\b(successes_a|n_a|successes_b|n_b)\b")


# ---------------------------------------------------------------------------
# Input rules
# ---------------------------------------------------------------------------


def relation_error(named: Mapping[str, Any]) -> tuple[str, str] | None:
    """``(field, reason)`` when the four whole numbers do not describe two proportions — the
    shared `playground.FIELD_RULES` entry for the z-test, the same rule the Playground applies
    (`parse_inputs` enforces it; this is the pure form for callers holding named values)."""
    return playground.field_rule_error(HERO_MODULE, HERO_FUNCTION, named)


def validated_args(kernel: hubkernel.LoadedKernel, raw: Mapping[str, Any]) -> dict[str, Any]:
    """The four inputs as the kernel takes them; `playground.ValidationError` names the field.

    `parse_inputs` carries every rule: the contract's types and ranges, the 2^53 bound of a
    number box, and the z-test's field rules (`relation_error`)."""
    form = playground.form_spec(kernel, HERO_MODULE, HERO_FUNCTION)
    values = playground.parse_inputs(form, raw)
    return playground.named_args(form, values)


def field_message(exc: playground.ValidationError) -> str:
    """One sentence with the field's label, never its identifier: `Trials A must be at least 1.`,
    `Successes A cannot exceed Trials A.` — an identifier inside the reason becomes its label."""
    label = LABELS.get(exc.field, exc.field)
    reason = REASON_WORDS.get(exc.reason, exc.reason)
    reason = _IDENT_WORD_RE.sub(lambda m: LABELS[m.group(1)], reason)
    return f"{label} {reason}."


def check_args(
    kernel: hubkernel.LoadedKernel, raw: Mapping[str, Any]
) -> tuple[dict[str, Any] | None, str]:
    """``(named args, "")`` when the inputs are acceptable, else ``(None, one sentence)``."""
    try:
        return validated_args(kernel, raw), ""
    except playground.ValidationError as exc:
        return None, field_message(exc)


#: The form's fields in the order the boxes stand in the row (`render_field_messages` cells).
FORM_FIELDS = ("successes_a", "n_a", "successes_b", "n_b")


#: What every non-refusal step writes into the four message slots: nothing.
NO_FIELD_MESSAGES: tuple[str, str, str, str] = ("", "", "", "")


def field_messages(
    kernel: hubkernel.LoadedKernel, raw: Mapping[str, Any], msg: str
) -> tuple[str, str, str, str]:
    """The four message slots for a refusal: `msg` (as the alert) under the field that failed,
    the other slots empty; the first slot when the field cannot be told."""
    field = FORM_FIELDS[0]
    try:
        validated_args(kernel, raw)
    except playground.ValidationError as exc:
        if exc.field in FORM_FIELDS:
            field = exc.field
    a, b, c, d = (common.render_field_message(msg) if f == field else "" for f in FORM_FIELDS)
    return a, b, c, d


# ---------------------------------------------------------------------------
# Reference and measurement
# ---------------------------------------------------------------------------


def statsmodels_reference(values: list[int]) -> tuple[list[float], str] | None:
    """``([z, p], "statsmodels==x.y")`` from `proportions_ztest`, or None when not installed."""
    try:
        from statsmodels.stats.proportion import proportions_ztest
    except ImportError:
        return None
    successes_a, n_a, successes_b, n_b = values
    z, p = proportions_ztest([successes_a, successes_b], [n_a, n_b])
    version = metadata.version(REFERENCE_DIST)
    return [float(z), float(p)], f"{REFERENCE_DIST}=={version}"


def parity_of(result: Any, reference: list[float]) -> ParityCheck:
    z, p = float(result[0]), float(result[1])
    deltas = {"z": abs(z - reference[0]), "p": abs(p - reference[1])}
    return ParityCheck(REFERENCE_DIST, "", deltas, {"z": Z_TOL, "p": P_TOL})


def start_hero(
    kernel: hubkernel.LoadedKernel,
    lane: Lane,
    *,
    hardware: str,
    args: Mapping[str, Any] = HERO_ARGS,
    budget_s: float = HERO_BUDGET_S,
    execute: Callable[..., Any] = hubkernel.execute,
    reference: Callable[[list[int]], tuple[list[float], str] | None] = statsmodels_reference,
    run_cell: Callable[..., bench.CellResult] = bench.run_cell,
    **cell_kwargs: Any,
) -> tuple[Ticket, Callable[[], HeroResult]]:
    """Validate `args`, queue the measurement on the lane, return the ticket and its finisher.

    The ticket carries the queue position for the lane chip; calling the finisher waits for the
    cell and builds the `HeroResult`. Raises `playground.ValidationError` for bad input before
    anything native runs; the finisher raises the lane's own errors past the budget.
    """
    form = playground.form_spec(kernel, HERO_MODULE, HERO_FUNCTION)
    values = playground.parse_inputs(form, args)  # types, ranges, 2^53 and the z-test rules
    named = playground.named_args(form, values)
    ref = reference(values)
    captured: dict[str, Any] = {}

    def ours() -> Any:
        result = execute(kernel, HERO_MODULE, HERO_FUNCTION, values).result
        captured.setdefault("result", result)
        return result

    def gate(outputs: dict[str, Any]) -> tuple[bool, str]:
        result = outputs[HERO_LANE]
        if not isinstance(result, list) or len(result) != 2:
            return False, "the kernel did not return [z, p]"
        if ref is None:
            return True, ""
        check = parity_of(result, ref[0])
        if check.ok:
            return True, f"vs {REFERENCE_DIST} · {check.label()}"
        return (
            False,
            f"differs from {REFERENCE_DIST}: z Δ {check.deltas['z']:.2g}, "
            f"p Δ {check.deltas['p']:.2g}",
        )

    def job() -> bench.CellResult:
        spec = bench.LaneSpec(
            HERO_LANE, bench.SIDE_ALGENTA, ours, version=kernel.short_sha, config=HERO_QUALNAME
        )
        return run_cell([spec], correctness_gate=gate, budget_s=budget_s, **cell_kwargs)

    ticket = lane.submit(job, budget_s=budget_s, label="hero z-test")

    def finish() -> HeroResult:
        cell = ticket.result()
        result = captured.get("result")
        parity = None
        if ref is not None and isinstance(result, list) and len(result) == 2:
            check = parity_of(result, ref[0])
            parity = ParityCheck(REFERENCE_DIST, ref[1], check.deltas, check.tolerances)
        return HeroResult(
            args=dict(named),
            result=list(result) if isinstance(result, list) else [math.nan, math.nan],
            cell=cell,
            parity=parity,
            hardware=hardware,
            ts_utc=cell.ts_utc or utc_stamp(),
        )

    return ticket, finish


def measure_hero(
    kernel: hubkernel.LoadedKernel,
    lane: Lane,
    *,
    hardware: str,
    args: Mapping[str, Any] = HERO_ARGS,
    budget_s: float = HERO_BUDGET_S,
    on_queued: Callable[[Ticket], None] | None = None,
    **kwargs: Any,
) -> HeroResult:
    """`start_hero` and wait: the boot-time and test-time one-liner.

    A cell that fails its gate or is noisy comes back with that status and no number.
    """
    ticket, finish = start_hero(
        kernel, lane, hardware=hardware, args=args, budget_s=budget_s, **kwargs
    )
    if on_queued is not None:
        on_queued(ticket)
    return finish()


class HeroTracker:
    """The opening card over time: every attempt is kept, the page shows the last measured one.

    `measure` runs one attempt (boot passes `measure_hero` bound to the kernel and the lane).
    `attempt()` runs and records it; `record()` keeps a result measured elsewhere (a visitor's
    run of the card example) and counts it in `recorded`; `start(interval_s)` re-measures on a
    daemon thread until one
    attempt is measured or a verdict is final. `measuring` is True only while an attempt runs,
    and `next_attempt_at()` is the clock reading (epoch seconds) of the next one — the last
    attempt's end, or the thread's start, plus the interval — so the card can say what is
    happening now and when the next try is, truthfully. `snapshot()` is what `/health` reports.
    """

    def __init__(
        self,
        measure: Callable[[], HeroResult] | None = None,
        *,
        hero: HeroResult | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._measure = measure
        self._clock = clock
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.latest: HeroResult | None = hero
        self.measured: HeroResult | None = hero if hero is not None and hero.cell.measured else None
        self.attempts = 0 if hero is None else 1
        self.recorded = 0
        self.retry_s = 0.0
        self.measuring = False
        self.last_attempt_at: float | None = None if hero is None else clock()
        self.started_at: float | None = None

    @property
    def hero(self) -> HeroResult | None:
        """The card's data: the last measured attempt, else the last attempt of any status."""
        return self.measured or self.latest

    @property
    def pending(self) -> bool:
        """True while nothing is measured and the last verdict could still change."""
        if self.measured is not None:
            return False
        return self.latest is None or self.latest.cell.status in TRANSIENT_STATUSES

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def record(self, hero: HeroResult) -> None:
        """Keep a result measured outside this tracker (a visitor's run of the card example)."""
        with self._lock:
            self.recorded += 1
        self._keep(hero)

    def _keep(self, hero: HeroResult) -> None:
        with self._lock:
            self.latest = hero
            if hero.cell.measured:
                self.measured = hero

    def attempt(self) -> HeroResult:
        if self._measure is None:
            raise RuntimeError("this tracker has no measurement to run")
        with self._lock:
            self.attempts += 1
            self.measuring = True
        try:
            hero = self._measure()
        finally:
            with self._lock:
                self.measuring = False
                self.last_attempt_at = self._clock()
        self._keep(hero)
        return hero

    def next_attempt_at(self) -> float | None:
        """When the background thread tries again (epoch seconds), or None when it will not:
        the later of the last attempt's end and the thread's start, plus the interval."""
        if not self.running or not self.pending or self.retry_s <= 0:
            return None
        marks = [t for t in (self.last_attempt_at, self.started_at) if t is not None]
        return None if not marks else max(marks) + self.retry_s

    def next_attempt_utc(self) -> str | None:
        """`23:41:07 UTC` for `next_attempt_at()`, or None."""
        at = self.next_attempt_at()
        return None if at is None else clock_utc(at)

    def start(self, interval_s: float) -> bool:
        """Re-measure every `interval_s` on a daemon thread; False when there is nothing to do."""
        if interval_s <= 0 or self._measure is None or not self.pending:
            return False
        with self._lock:
            if self.running:
                return True
            self.retry_s = float(interval_s)
            self.started_at = self._clock()
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._loop, args=(float(interval_s),), name="hero-remeasure", daemon=True
            )
            self._thread.start()
        return True

    def stop(self, *, wait: bool = False) -> None:
        self._stop.set()
        thread = self._thread
        if wait and thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def _loop(self, interval_s: float) -> None:
        try:
            while not self._stop.wait(interval_s):
                if not self.pending:
                    break
                try:
                    hero = self.attempt()
                except LaneClosedError:
                    break
                except Exception as exc:  # reported, then the next interval tries again
                    log.warning("hero re-measurement failed: %s", exc)
                    continue
                log.info("hero attempt %d: %s", self.attempts, hero.cell.reason or hero.cell.status)
        finally:
            self.retry_s = 0.0

    def snapshot(self) -> dict[str, Any]:
        latest = self.latest
        return {
            "attempts": self.attempts,
            "recorded": self.recorded,
            "measured": self.measured is not None,
            "pending": self.pending,
            "measuring": self.measuring,
            "latest_status": None if latest is None else latest.cell.status,
            "latest_reason": None if latest is None else latest.cell.reason,
            "retry_s": self.retry_s if self.running else None,
            "next_attempt_utc": self.next_attempt_utc(),
        }


def clock_utc(epoch_s: float) -> str:
    """`23:41:07 UTC` — a clock reading with seconds, for a cycle shorter than a minute."""
    return time.strftime("%H:%M:%S UTC", time.gmtime(epoch_s))


def clock_iso(epoch_s: float) -> str:
    """`2026-09-22T23:41:07Z` — the same instant for a `<time datetime>` attribute."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch_s))


def hero_tracker_of(deps: Deps) -> HeroTracker:
    """The shell's tracker when the boot state carries one, else one holding `deps.hero`."""
    tracker = getattr(deps, "hero_tracker", None)
    if isinstance(tracker, HeroTracker):
        return tracker
    return HeroTracker(hero=deps.hero)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _fmt_stat(value: float) -> str:
    if math.isnan(value):
        return "—"
    return f"{value:.6f}"


def human_args(args: Mapping[str, Any]) -> str:
    """``50 of 1,000 vs 65 of 1,000`` — the two proportions in words, no identifiers."""
    return (
        f"{int(args['successes_a']):,} of {int(args['n_a']):,} vs "
        f"{int(args['successes_b']):,} of {int(args['n_b']):,}"
    )


def human_reason(reason: str) -> str:
    """The rulebook's cause without the lane's internal name (`… on algenta-stats`)."""
    return reason.replace(f" on {HERO_LANE}", "")


def human_cell(cell: bench.CellResult) -> bench.CellResult:
    """The same cell with its reason in human words, for the cards that print it."""
    if not cell.reason:
        return cell
    return dataclasses.replace(cell, reason=human_reason(cell.reason))


def calls_per_repeat(cell: bench.CellResult) -> int:
    """How many back-to-back calls the harness timed per repeat — rulebook v0.4's inner batch,
    read from the cell (`bench.CellResult.k`; the hero has one lane, so the lane's `k`) and
    never assumed: 1 for a harness that timed single calls or a cell built before the field."""
    k = getattr(cell, "k", None)
    if k is None:
        ours = cell.lane(bench.SIDE_ALGENTA)
        k = getattr(ours, "k", 1) if ours is not None else 1
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        return 1
    return k


def repeats_label(cell: bench.CellResult) -> str:
    """`n = 21` when each repeat timed one call; `n = 21 × 8 calls` when the harness timed an
    inner batch of eight calls per repeat — the count the card prints is the count that ran,
    in the shared card's words (`cards.calls_text`)."""
    calls_text = getattr(cards, "calls_text", None)
    calls = calls_per_repeat(cell)
    if calls_text is not None and cell.n >= 1:
        return calls_text(cell.n, calls)
    return f"n = {cell.n}" if calls == 1 else f"n = {cell.n} × {calls} calls"


def parity_chips(hero: HeroResult) -> list[str]:
    """The correctness gate's chips, each short enough for a 375 px card: the verdict, the
    bound checked, the reference's version; nothing without a reference."""
    if hero.parity is None:
        return []
    chips = []
    if hero.parity.ok:
        chips.append(common.chip(f"parity vs {hero.parity.reference}", "ok"))
        chips.append(common.chip(hero.parity.label()))
    else:
        chips.append(common.chip(f"parity differs from {hero.parity.reference}", "err"))
    chips.append(common.chip(hero.parity.version))
    return chips


def has_result(hero: HeroResult) -> bool:
    """True when the kernel answered: two finite numbers the card can print as z and p."""
    return len(hero.result) == 2 and all(
        isinstance(v, int | float) and math.isfinite(float(v)) for v in hero.result
    )


def result_block(hero: HeroResult) -> str:
    """The z/p the kernel answered, as the card prints it on every run that has an answer."""
    return f'<pre class="alg-result">z {_fmt_stat(hero.z)}\np {_fmt_stat(hero.p)}</pre>'


def render_unrecorded_hero_card(hero: HeroResult, *, kernel_label: str = "") -> str:
    """The run the rulebook did not record, with everything that is not a timing kept: the
    shared not-recorded card (`cards.render_not_recorded_card`) with the two proportions as
    its subtitle, the z/p block as its result, the Try tab's parity chips (verdict, bound,
    reference version — two short chips in place of the cell's one long gate label, so nothing
    wraps on a 375 px card), the kernel revision and the transport note; where the measured
    card draws its timing (the hero figure, P95, MAD, spread, n) the shared card draws one quiet
    `timing` row — the rulebook's cause in words and the neutral `not recorded` chip. A
    documented state: the hairline card, `data-state="not_recorded"`, the same contract the
    verifier reads on every not-recorded card of the fleet."""
    cell = hero.cell
    if cell.measured:
        raise ValueError("a measured cell renders the result card")
    chips = parity_chips(hero)
    if kernel_label:
        chips.append(common.chip(kernel_label))
    chips.append(common.chip(common.TRANSPORT_NOTE))
    # the cell's own gate label is the two chips above, said once; the cause in human words
    quiet = dataclasses.replace(human_cell(cell), parity_label="")
    return cards.render_not_recorded_card(
        quiet,
        title=TITLE,
        hardware=hero.hardware,
        subtitle=human_args(hero.args),
        result_html=result_block(hero),
        chips=chips,
    )


def render_hero_card(hero: HeroResult, *, kernel_label: str = "") -> str:
    """The opening card: kernel-call median as the hero, the result, parity, machine, stamp.

    A run the rulebook did not record keeps its result and parity (`render_unrecorded_hero_card`);
    only a run with no answer at all is the shared not-recorded card without a result."""
    cell = hero.cell
    if not cell.measured:
        if has_result(hero):
            return render_unrecorded_hero_card(hero, kernel_label=kernel_label)
        return cards.render_not_recorded_card(human_cell(cell), title=TITLE, hardware=hero.hardware)
    ours = cell.lane(bench.SIDE_ALGENTA)
    if ours is None:
        raise ValueError("the hero cell has no algenta lane")
    chips = parity_chips(hero)
    if kernel_label:
        chips.append(common.chip(kernel_label))
    chips.append(common.chip(repeats_label(cell)))
    chips.append(common.chip(f"P95 {cards.fmt_ms(ours.p95_ms)}"))
    chips.append(common.chip(f"MAD {cards.fmt_ms(ours.mad_ms)}"))
    chips.append(cards.stability_chip([ours]))  # the gate's verdict, as on every race card
    chips.append(common.chip(f"CV {cards.fmt_cv(ours.cv)}"))
    chips.append(common.chip(common.TRANSPORT_NOTE))
    chips.append(cards.status_chip("measured", f"measured {cell.ts_utc}"))
    return (
        '<article class="alg-card alg-card-result" data-tab="try">'
        '<div class="alg-card-head">'
        f'<div><h2 class="alg-card-title">{common.esc(TITLE)}</h2>'
        f'<div class="alg-card-sub">{common.esc(human_args(hero.args))}</div></div>'
        '<div class="alg-hero">'
        f'<div class="alg-hero-num alg-accent-text">{cards.fmt_ms(ours.median_ms)}</div>'
        f'<div class="alg-hero-label">{HERO_LABEL}</div>'
        "</div></div>"
        f"{result_block(hero)}"
        f'<div class="alg-chips">{"".join(chips)}</div>'
        f"{cards.foot_html(hero.hardware, cell.ts_utc, cell.load_1m)}"
        "</article>"
    )


def pending_parts(tracker: HeroTracker) -> list[str]:
    """The note's pieces, in order: what is happening, the attempt count, the last cause, and —
    when the thread will try again — `next attempt at 23:41:07 UTC`. Never a value."""
    parts = [MEASURING if tracker.measuring else NOT_MEASURED]
    latest = tracker.latest
    if tracker.attempts:
        parts.append(f"attempt {tracker.attempts}")
    if latest is not None and (latest.cell.reason or latest.cell.status):
        # The rulebook's cause without its verdict words: the card is still waiting.
        reason = human_reason(latest.cell.reason or latest.cell.status)
        parts.append(reason.removeprefix(f"{bench.NOISY_TEXT} — "))
    next_at = tracker.next_attempt_at()
    if next_at is not None and not tracker.measuring:
        parts.append(f"{NEXT_ATTEMPT} {clock_utc(next_at)}")
    return parts


def pending_note(tracker: HeroTracker) -> str:
    """`Not measured on this host yet · attempt 6 · load 82 on 16 vCPU · next attempt at 23:41:07
    UTC` between attempts; `Measuring on this machine · attempt 7` while one runs."""
    return " · ".join(pending_parts(tracker))


def pending_note_html(tracker: HeroTracker) -> str:
    """The same note, escaped, with the clock reading as a `<time datetime>` element."""
    parts = [common.esc(part) for part in pending_parts(tracker)]
    next_at = tracker.next_attempt_at()
    if next_at is not None and parts and parts[-1].startswith(NEXT_ATTEMPT):
        parts[-1] = (
            f"{NEXT_ATTEMPT} "
            f'<time class="alg-time" datetime="{clock_iso(next_at)}">{clock_utc(next_at)}</time>'
        )
    return " · ".join(parts)


def render_loading_card(tracker: HeroTracker, hardware: str) -> str:
    """The measured card's geometry while no attempt has been measured yet: pulsing only while
    an attempt runs (`tracker.measuring`), settled and still between attempts."""
    latest = tracker.latest
    stamp = latest.ts_utc if latest is not None else utc_stamp()
    return common.render_loading_card(
        title=TITLE,
        subtitle=human_args(HERO_ARGS),
        hero_label=HERO_LABEL,
        note=pending_note(tracker),
        note_html=pending_note_html(tracker),
        hardware=hardware,
        ts_utc=stamp,
        settled=not tracker.measuring,
    )


def card_pending(html: str) -> bool:
    """True for a card HTML in either pending state (measuring, or settled between attempts)."""
    return any(
        f'data-state="{state}"' in html
        for state in (common.CARD_STATE_LOADING, common.CARD_STATE_PENDING)
    )


def opening_card(deps: Deps, tracker: HeroTracker) -> str:
    """What the page paints first: the measured card, else loading; a final verdict is shown."""
    kernel = deps.kernel(HERO_FAMILY)
    if kernel is None:
        return common.no_kernel_card(TITLE, HERO_FAMILY, deps)
    if tracker.measured is not None:
        return render_hero_card(tracker.measured, kernel_label=kernel.label())
    if tracker.pending or tracker.latest is None:
        return render_loading_card(tracker, common.hardware_line(deps))
    return render_hero_card(tracker.latest, kernel_label=kernel.label())


def kernel_counts(deps: Deps) -> tuple[int, int, str]:
    """Families and callable functions loaded here, plus the build variants — counted, not typed."""
    families = 0
    functions = 0
    variants: set[str] = set()
    for loaded in deps.kernels.values():
        if loaded.is_umbrella:
            continue
        families += 1
        functions += int(hubkernel.describe(loaded)["function_count"])
        variants.add(loaded.variant)
    return families, functions, ", ".join(sorted(variants))


def loaded_counts(deps: Deps) -> tuple[int, int, int]:
    """``(families loaded, families published, functions loaded)`` — the boot facts' one truth.

    The facts record (`boot_sequence.compute_facts`) is read when it carries the counts; a
    `Deps` built without one (tests, a bare shell) counts the loaded contracts the same way.
    The umbrella is never a family here.
    """
    facts = deps.facts if isinstance(deps.facts, Mapping) else {}
    families, functions, _variants = kernel_counts(deps)
    loaded = facts.get("families_loaded")
    if isinstance(loaded, list | tuple):
        families = len(loaded)
    counted = facts.get("functions_loaded")
    if isinstance(counted, int) and not isinstance(counted, bool):
        functions = counted
    published = facts.get("families_published")
    if not isinstance(published, int) or isinstance(published, bool) or published <= 0:
        published = len(hubkernel.TRUST) - 1
    return families, published, functions


def boot_stamp(deps: Deps) -> str:
    """The UTC stamp the boot facts were counted at, else now (a shell without facts)."""
    facts = deps.facts if isinstance(deps.facts, Mapping) else {}
    stamp = facts.get("generated_utc")
    return stamp if isinstance(stamp, str) and stamp.strip() else utc_stamp()


def hub_tile(deps: Deps) -> str:
    families, published, functions = loaded_counts(deps)
    if families == 0:
        return common.render_tile(
            title=TILE_HUB,
            value=OFFLINE,
            caption="no family loaded in this container",
            kind="unavailable",
            code=common.CODE_NO_KERNEL,
            link=shell.KERNELS_HUB_URL,
        )
    noun = "family" if families == 1 else "families"
    loaded = f"{families} of {published} families" if families < published else f"{families} {noun}"
    return common.render_tile(
        title=TILE_HUB,
        value=f"{functions:,} functions",
        caption=f"{loaded} loaded here · {COUNTED_AT_BOOT} · {boot_stamp(deps)}",
        kind="measured",
        link=shell.KERNELS_HUB_URL,
    )


def mcp_tool_count(
    fetch_json: Callable[[str], common.Fetched] = common.fetch_json,
) -> tuple[int | None, str, str]:
    """``(count, caption, kind)``: the registry when installed, else the live endpoint."""
    try:
        from algenta_mcp.registry import TOOLS
    except ImportError:
        TOOLS = None  # noqa: N806 - mirrors the imported name
    if TOOLS is not None:
        try:
            version = metadata.version(MCP_DIST)
        except metadata.PackageNotFoundError:
            version = "installed"
        return (
            len(TOOLS),
            f"{MCP_DIST} {version} registry · {COUNTED_AT_BOOT} · {utc_stamp()}",
            "measured",
        )
    fetched = fetch_json(MCP_TOOLS_URL)
    tools = fetched.data.get("tools") if fetched.ok and isinstance(fetched.data, Mapping) else None
    if isinstance(tools, list):
        return len(tools), f"{LIVE_HOSTED} · {utc_stamp()}", "live"
    reason = fetched.error or "no tools list in the response"
    return None, f"unavailable · {CODE_MCP_UNREACHABLE} · {reason}", "unavailable"


def hosted_tile(fetch_json: Callable[[str], common.Fetched] = common.fetch_json) -> str:
    count, caption, kind = mcp_tool_count(fetch_json)
    if count is None:
        reason = caption.removeprefix(f"unavailable · {CODE_MCP_UNREACHABLE} · ")
        return common.render_tile(
            title=TILE_HOSTED,
            value=OFFLINE,
            caption=reason,
            kind="unavailable",
            code=CODE_MCP_UNREACHABLE,
            link=shell.DOCS_URL,
        )
    return common.render_tile(
        title=TILE_HOSTED,
        value=f"{count:,} MCP tools",
        caption=caption,
        kind=kind,
        link=shell.DOCS_URL,
    )


def last_logged(text: Any) -> gpu_status.GpuStatus | None:
    """The newest status record in a JSON Lines log (same contract as the endpoint), or None."""
    if not isinstance(text, str):
        return None
    for line in reversed(text.splitlines()):
        if not line.strip():
            continue
        try:
            return gpu_status.parse_status(line.encode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
    return None


def gpu_configured(env: Mapping[str, str]) -> bool:
    """True when the Space variable names the GPU stage's https status endpoint
    (`gpu_status.configured`); an unset stage never gets a tile."""
    return gpu_status.configured(env)


def gpu_url(env: Mapping[str, str]) -> str:
    """The wired status endpoint (`gpu_status.status_url`), else the published one."""
    return gpu_status.status_url(env) or gpu_status.STATUS_URL


def gpu_tile(
    env: Mapping[str, str],
    *,
    snapshot: gpu_status.Snapshot | None = None,
    fetch_text: Callable[[str], common.Fetched] = common.fetch_text,
) -> str:
    """The GPU stage as a tile of the band's geometry: live, offline with its last log, or none.

    Rendered only when `gpu_configured(env)`; the band drops the tile otherwise. `snapshot` is
    the shared poller's latest reading (fetched here when none is given). Online: the decode
    throughput with its stamp and machine. Offline: "GPU stage offline — last measured N tok/s ·
    <UTC>" from the results Dataset's log when that log has a record, else the code alone —
    quiet, never red, never a static figure.
    """
    if snapshot is None:
        poller = gpu_status.shared_poller(gpu_url(env))
        snapshot = poller.latest()
        if snapshot.error_code == gpu_status.CODE_NOT_FETCHED:
            snapshot = poller.refresh()
    status = snapshot.status
    if status is not None and status.online:
        where = " · ".join(part for part in (status.hardware, status.model) if part)
        return common.render_tile(
            title=TILE_GPU,
            value=gpu_status.fmt_tok_s(status.tok_per_s),
            caption=f"{where} · measured {status.measured_utc}",
            kind="live",
            link=gpu_status.OPEN_URL,
        )
    if status is not None:
        where = " · ".join(part for part in (status.hardware, status.model) if part)
        return common.render_tile(
            title=TILE_GPU,
            value=gpu_status.fmt_tok_s(status.tok_per_s),
            caption=f"{GPU_OFFLINE} · last measured {status.measured_utc} · {where}",
            kind="fallback",
            link=gpu_status.OPEN_URL,
        )
    log_url = env.get(GPU_LOG_URL_ENV, "").strip() or GPU_LOG_URL_DEFAULT
    logged = fetch_text(log_url)
    last = last_logged(logged.data if logged.ok else None)
    if last is not None:
        hint = (
            f"{GPU_OFFLINE} — last measured {gpu_status.fmt_tok_s(last.tok_per_s)}"
            f" · {last.measured_utc}"
        )
    else:
        hint = GPU_OFFLINE
    if snapshot.fetched_utc:
        hint += f" · {snapshot.fetched_utc}"
    return common.render_tile(
        title=TILE_GPU,
        value=OFFLINE,
        caption=hint,
        kind="unavailable",
        code=snapshot.error_code or gpu_status.CODE_NOT_FETCHED,
        link=gpu_status.OPEN_URL,
    )


def where_band(deps: Deps, gpu_html: str, hosted_html: str) -> str:
    """Hub kernels, Hosted API + MCP and — only when wired — the GPU stage, on one grid."""
    return common.render_tiles(hub_tile(deps), hosted_html, gpu_html)


def build_note(deps: Deps) -> str:
    """The Reproduce disclosure's provenance chips: variant, pinned revision, library versions."""
    kernel = deps.kernel(HERO_FAMILY)
    _families, _functions, variants = kernel_counts(deps)
    chips = [common.chip(HERO_QUALNAME)]
    if variants:
        chips.append(common.chip(f"build {variants}"))
    if kernel is not None:
        chips.append(common.chip(kernel.label()))
    versions = deps.facts.get("versions") if isinstance(deps.facts, Mapping) else None
    if isinstance(versions, Mapping):
        for name in ("kernels", "torch", REFERENCE_DIST):
            version = versions.get(name)
            if version:
                chips.append(common.chip(f"{name} {version}"))
    chips.append(common.chip(f"rulebook v{bench.RULEBOOK_VERSION}"))
    return f'<div class="alg-chips">{"".join(chips)}</div>'


# ---------------------------------------------------------------------------
# Snippets and permalinks
# ---------------------------------------------------------------------------


def install_snippet(args: Mapping[str, Any]) -> str:
    """Exactly three lines: pip, `get_kernel` trusting this one repository, the call.

    `algenta-stats` has no kernel dependencies, so its own repository is the whole trust list;
    the twenty-repository form lives in `reproduce_snippet`.
    """
    repo = playground.repo_id(HERO_FAMILY)
    call = playground.render_call(f"k.{HERO_MODULE}.{HERO_FUNCTION}", dict(args), width=10_000)
    load = (
        f'from kernels import get_kernel; k = get_kernel("{repo}", '
        f'version={playground.KERNEL_VERSION}, backend="{playground.BACKEND}", '
        f'trust_remote_code=["{repo}"])'
    )
    return f"# {playground.PIP_KERNELS}\n{load}\n{call}\n"


def reproduce_snippet(args: Mapping[str, Any]) -> str:
    """The long `kernels` form with every published repository in the trust list."""
    return playground.snippet(
        HERO_FAMILY, HERO_MODULE, HERO_FUNCTION, dict(args), mode=playground.MODE_KERNELS
    )


def args_or_defaults(kernel: hubkernel.LoadedKernel | None, raw: Mapping[str, Any]) -> dict:
    """The visitor's numbers when they are acceptable, else the card example."""
    if kernel is not None:
        try:
            return validated_args(kernel, raw)
        except playground.PlaygroundError:
            pass
    return dict(HERO_ARGS)


def snippet_for(kernel: hubkernel.LoadedKernel | None, raw: Mapping[str, Any], mode: str) -> str:
    """The three-line `kernels` snippet or the `mcp` frame with the visitor's numbers."""
    args = args_or_defaults(kernel, raw)
    if mode == playground.MODE_KERNELS:
        return install_snippet(args)
    return playground.snippet(HERO_FAMILY, HERO_MODULE, HERO_FUNCTION, args, mode=mode)


def try_permalink(args: Mapping[str, Any], env: Mapping[str, str]) -> str:
    """``?tab=try&fn=ab_testing.z_test_proportions&args={...}`` on the Space's public base."""
    return common.permalink(
        TAB_TRY, fn=HERO_QUALNAME, args=dict(args), base=permalink_mod.public_base(env)
    )


def applied_values(fn: str | None, args: Mapping[str, Any] | None) -> dict[str, int]:
    """What this tab can put in its four boxes from a link: whole numbers below 2^53 (a number
    box shows nothing larger exactly) for the hero's fields, under the hero's function or none.
    A decimal, a bool, text, a foreign name or a foreign function applies nothing."""
    if args is None or fn not in (None, HERO_QUALNAME):
        return {}
    out: dict[str, int] = {}
    for name in LABELS:
        value = args.get(name)
        if isinstance(value, bool) or not isinstance(value, int | float):
            continue
        if isinstance(value, float) and not value.is_integer():
            continue
        if abs(value) >= playground.BROWSER_EXACT_MAX:
            continue
        out[name] = int(value)
    return out


def restore_values(text: Any) -> dict[str, int]:
    """The four inputs a restore payload applies (`applied_values`), by field name."""
    fn, args = common.permalink_request(text)
    return applied_values(fn, args)


def permalink_applied(
    fn: str | None, args: Mapping[str, Any] | None
) -> tuple[str | None, dict[str, int] | None] | None:
    """The shell's report hook: exactly what a link to this tab restores, so the box never
    promises more. `(fn, values)` with the hero's function when the link named it (or None when
    it named none) and the whole numbers that landed in the boxes; None when nothing did —
    a foreign function, or arguments none of which this form can show."""
    if fn not in (None, HERO_QUALNAME):
        return None
    values = applied_values(fn, args)
    if not values and fn is None:
        return None
    return fn, values or None


def permalink_outputs(handles: Mapping[str, Any]) -> list[Any]:
    """The shell's restore protocol: one hidden box the page load writes into."""
    box = handles.get("restore")
    return [box] if box is not None else []


def permalink_restore(fn: str | None, args: Mapping[str, Any] | None) -> list[Any]:
    return [common.permalink_payload(fn, args)]


# ---------------------------------------------------------------------------
# Handlers (pure: the UI maps their outputs onto components)
# ---------------------------------------------------------------------------


def raw_args(successes_a: Any, n_a: Any, successes_b: Any, n_b: Any) -> dict[str, Any]:
    return {"successes_a": successes_a, "n_a": n_a, "successes_b": successes_b, "n_b": n_b}


def run_hero(
    deps: Deps,
    raw: Mapping[str, Any],
    request: Any = None,
    *,
    tracker: HeroTracker | None = None,
) -> Iterator[tuple[str, str | None, str]]:
    """Yield ``(lane chip, card or None, field message)``: the queue chip first, then the card.

    A run of the card example that is measured is recorded on `tracker`, so a visitor's
    measurement can fill the opening card when boot's own attempts were noisy.
    """
    kernel = deps.kernel(HERO_FAMILY)
    hardware = common.hardware_line(deps)
    if kernel is None:
        yield "", common.no_kernel_card(TITLE, HERO_FAMILY, deps), ""
        return
    named, message = check_args(kernel, raw)
    if named is None:
        yield "", None, message
        return
    if not deps.feature_on(FEATURE):
        yield "", common.switched_off_card(TITLE, hardware), ""
        return
    decision = common.check_limit(deps, request)
    if decision is not None and not decision.allowed:
        yield "", common.limited_card(TITLE, decision, hardware), ""
        return
    try:
        ticket, finish = start_hero(kernel, deps.lane, hardware=hardware, args=named)
    except Exception as exc:  # a lane refusal is a card with a code, never a traceback
        log.warning("hero measurement refused: %s", exc)
        yield "", common.error_card(TITLE, exc, hardware), ""
        return
    yield common.lane_chip(ticket), None, ""
    try:
        hero = finish()
    except Exception as exc:  # every failure is a card with a code, never a traceback
        log.warning("hero measurement failed: %s", exc)
        yield "", common.error_card(TITLE, exc, hardware), ""
        return
    if tracker is not None and dict(hero.args) == dict(HERO_ARGS):
        tracker.record(hero)
    yield common.done_chip(ticket), render_hero_card(hero, kernel_label=kernel.label()), ""


# ---------------------------------------------------------------------------
# The tab
# ---------------------------------------------------------------------------


def build(deps: Deps) -> TabSpec:
    hosted_html = hosted_tile()
    gpu_wired = gpu_configured(deps.env)
    gpu_html = gpu_tile(deps.env) if gpu_wired else ""
    kernel = deps.kernel(HERO_FAMILY)
    tracker = hero_tracker_of(deps)
    built_hero = tracker.measured
    built_latest = tracker.latest
    opening = opening_card(deps, tracker)
    defaults = dict(HERO_ARGS)
    provenance = build_note(deps)

    def fresh_card() -> str | None:
        """The card to paint now, or None when the one the page was built with is still right:
        a measured card the page has not shown yet; the pending card re-read (its attempt count
        and next-attempt clock move); a final verdict that landed after the build."""
        if kernel is None:
            return None
        if tracker.measured is not None:
            if tracker.measured is built_hero:
                return None
            return render_hero_card(tracker.measured, kernel_label=kernel.label())
        if tracker.pending or tracker.latest is None:
            return render_loading_card(tracker, common.hardware_line(deps))
        if tracker.latest is built_latest:
            return None
        return render_hero_card(tracker.latest, kernel_label=kernel.label())

    def render(gr: Any) -> dict[str, Any]:
        hooks = _event_hooks()
        quiet = {"show_progress": "hidden"}
        card = gr.HTML(opening, elem_classes=["alg-try-card"])
        with gr.Row(elem_classes=["alg-chip-row"]):
            race_chip = gr.Button(LABEL_RACE, variant="secondary", elem_classes=["alg-chip-btn"])
            install_chip = gr.Button(
                LABEL_INSTALL, variant="secondary", elem_classes=["alg-chip-btn"]
            )
            mcp_chip = gr.Button(LABEL_MCP, variant="secondary", elem_classes=["alg-chip-btn"])
        snippet_caption, snippet = common.code_editor(
            gr, value="", language="python", caption=CAPTION_INSTALL, lines=3, visible=False
        )
        with gr.Row(elem_classes=["alg-copy-row"], visible=False) as snippet_row:
            snippet_copy = gr.Button(
                common.LABEL_COPY, variant="secondary", elem_classes=["alg-chip-btn"], scale=0
            )
        with gr.Row(elem_classes=["alg-form-row"]):
            # No `minimum=`: Gradio would answer an out-of-range value with its own error toast;
            # `check_args` refuses it with one designed sentence under the fields instead. No
            # `precision=0` either: the browser would round 2.5 to 2 before the handler saw it;
            # the handler refuses a decimal with "Successes A must be a whole number." instead.
            # Each field is a column of its box and a message slot right under it, so a
            # refusal's alert lands under the offending box in every layout (the boxes stack on
            # a phone); the status row beside Run repeats it as a status — one convention.
            boxes: list[Any] = []
            slots: list[Any] = []
            labels = (LABEL_A, LABEL_NA, LABEL_B, LABEL_NB)
            for name, label in zip(FORM_FIELDS, labels, strict=True):
                # min_width 160: four fields and Run share the 1,120 px row; on a phone the
                # row wraps and the fields stack full-width (a 34 px-wide box is no target).
                with gr.Column(elem_classes=["alg-field"], min_width=160):
                    boxes.append(gr.Number(defaults[name], label=label, precision=None))
                    slots.append(gr.HTML("", elem_classes=["alg-status-row", "alg-field-slot"]))
            a, na, b, nb = boxes
            run = gr.Button(LABEL_RUN, variant="primary", elem_classes=["alg-run"])
        status = gr.HTML(common.render_status(), elem_classes=["alg-status-row"])
        with gr.Accordion(LABEL_HOW, open=False, elem_classes=["alg-disclosure"]):
            gr.HTML(common.render_note(HOW_MEASURED))
        with gr.Accordion(LABEL_REPRODUCE, open=False, elem_classes=["alg-disclosure"]):
            gr.HTML(provenance, elem_classes=["alg-provenance"])
            _full_caption, full = common.code_editor(
                gr,
                value=reproduce_snippet(defaults),
                language="python",
                caption=LABEL_FULL_SNIPPET,
                lines=12,
            )
            with gr.Row(elem_classes=["alg-copy-row"]):
                full_copy = gr.Button(
                    common.LABEL_COPY, variant="secondary", elem_classes=["alg-chip-btn"], scale=0
                )
            link = gr.Textbox(
                try_permalink(defaults, deps.env),
                label=LABEL_PERMALINK,
                interactive=False,
                buttons=[],
            )
            with gr.Row(elem_classes=["alg-copy-row"]):
                link_copy = gr.Button(
                    common.LABEL_COPY, variant="secondary", elem_classes=["alg-chip-btn"], scale=0
                )
        band = gr.HTML(where_band(deps, gpu_html, hosted_html), elem_classes=["alg-where"])
        timer = gr.Timer(GPU_POLL_S)
        restore = gr.Textbox("", visible=False, elem_classes=["alg-restore"])

        def on_run(sa: Any, n_a: Any, sb: Any, n_b: Any, request: gr.Request | None = None):
            raw = raw_args(sa, n_a, sb, n_b)
            for chip, html, msg in run_hero(deps, raw, request, tracker=tracker):
                if html is None:
                    if msg and not chip:
                        # A refusal: the alert under the offending box; beside Run, the status
                        # row says the run did not happen — not the sentence again (round 6).
                        yield (
                            common.render_status(echo=common.STATUS_NOT_RUN),
                            *field_messages(kernel, raw, msg),
                            gr.update(),
                            gr.update(),
                            gr.update(),
                        )
                    else:
                        yield (
                            common.render_status(chip, msg),
                            *NO_FIELD_MESSAGES,
                            gr.update(),
                            gr.update(),
                            gr.update(),
                        )
                    continue
                args = args_or_defaults(kernel, raw)
                yield (
                    common.render_status(chip, msg),
                    *NO_FIELD_MESSAGES,
                    html,
                    reproduce_snippet(args),
                    try_permalink(args, deps.env),
                )

        def on_install(sa: Any, n_a: Any, sb: Any, n_b: Any) -> Any:
            """The three-line install in the snippet block, captioned `Install`."""
            text = snippet_for(kernel, raw_args(sa, n_a, sb, n_b), playground.MODE_KERNELS)
            return (
                gr.update(value=text, language="python", visible=True),
                gr.update(visible=True),
                common.LABEL_COPY,
                gr.update(value=common.render_code_caption(CAPTION_INSTALL), visible=True),
            )

        def on_mcp(sa: Any, n_a: Any, sb: Any, n_b: Any) -> Any:
            """The JSON-RPC frame in the same block, captioned `MCP request`."""
            text = snippet_for(kernel, raw_args(sa, n_a, sb, n_b), playground.MODE_MCP)
            return (
                gr.update(value=text, language="json", visible=True),
                gr.update(visible=True),
                common.LABEL_COPY,
                gr.update(value=common.render_code_caption(CAPTION_MCP), visible=True),
            )

        def on_tick(current: Any) -> Any:
            """The tiles refreshed; the card too while it still shows a pending state (measuring
            or settled), so it flips to the measured card the tick after a run records."""
            update = gr.update()
            if isinstance(current, str) and card_pending(current):
                fresh = fresh_card()
                if fresh is not None:
                    update = fresh
            gpu = gpu_tile(deps.env) if gpu_wired else ""
            return where_band(deps, gpu, hosted_html), update

        def on_edit() -> Any:
            """A refusal clears the moment the visitor edits a number: the alert under the box
            and the echo beside Run both go."""
            return common.render_status(), *NO_FIELD_MESSAGES

        def on_load() -> Any:
            fresh = fresh_card()
            return gr.update() if fresh is None else fresh

        def on_restore(text: Any) -> Any:
            values = restore_values(text)
            return tuple(values.get(name, gr.update()) for name in LABELS)

        inputs = [a, na, b, nb]
        run.click(
            on_run,
            inputs,
            [status, *slots, card, full, link],
            api_name=API_NAMES[0],
            **hooks,
            **quiet,
        )
        snippet_outputs = [snippet, snippet_row, snippet_copy, snippet_caption]
        install_chip.click(
            on_install, inputs, snippet_outputs, api_name=API_NAMES[1], **quiet
        ).then(None, [snippet], [snippet_copy], js=common.COPY_JS, api_name=False, **quiet)
        mcp_chip.click(on_mcp, inputs, snippet_outputs, api_name=API_NAMES[2], **quiet).then(
            None, [snippet], [snippet_copy], js=common.COPY_JS, api_name=False, **quiet
        )
        timer.tick(on_tick, [card], [band, card], api_name=API_NAMES[3], **quiet)
        gr.on(None, on_load, None, [card], api_name=False, **quiet)
        restore.change(on_restore, restore, inputs, api_name=False, **quiet)
        for box in inputs:
            box.input(on_edit, None, [status, *slots], api_name=False, **quiet)
        for button, source in ((snippet_copy, snippet), (full_copy, full), (link_copy, link)):
            button.click(None, [source], [button], js=common.COPY_JS, api_name=False, **quiet)
        return {
            "card": card,
            "race_chip": race_chip,
            "install_chip": install_chip,
            "mcp_chip": mcp_chip,
            "snippet": snippet,
            "snippet_copy": snippet_copy,
            "snippet_caption": snippet_caption,
            "inputs": inputs,
            "run": run,
            "status": status,
            "field_slots": slots,
            "full": full,
            "link": link,
            "band": band,
            "timer": timer,
            "restore": restore,
            "on_run": on_run,
            "on_restore": on_restore,
            "on_tick": on_tick,
            "on_load": on_load,
            "on_edit": on_edit,
        }

    def connect(gr: Any, tabs: Any, handles: Mapping[str, Mapping[str, Any]]) -> None:
        race = handles.get(TAB_RACE, {})
        candidate = race.get("candidate")
        # `.input` never fires for a programmatic value, so the chip drives the Races cascade
        # itself — size, card and the applied id — with what `on_candidate` answers for the
        # preselect (round 5: the box read Betweenness over a Levenshtein card)
        on_candidate = race.get("on_candidate")
        cascade = [race.get(name) for name in ("size", "card", "applied_id")]
        drives_cascade = (
            candidate is not None
            and on_candidate is not None
            and all(c is not None for c in cascade)
        )
        # A programmatic `gr.Tabs(selected=…)` fires no strip event, so the shell offers its
        # permalink box (`handles["shell"]["permalink"]`) and the chip writes it in the same
        # event: the box always reads the tab the page shows.
        shell_handles = handles.get(SHELL_HANDLE, {})
        link_box = shell_handles.get("permalink")
        base = str(shell_handles.get("base", "") or "")
        outputs = [tabs]
        if candidate is not None:
            outputs.append(candidate)
        if drives_cascade:
            outputs.extend(cascade)
        if link_box is not None:
            outputs.append(link_box)

        def go_race() -> Any:
            values: list[Any] = [gr.Tabs(selected=TAB_RACE)]
            if drives_cascade:
                # candidate box, size radio, opening card, applied id — the first offered
                # candidate when the preselect is not offered here (`on_candidate`'s own rule)
                values.extend(on_candidate(RACE_PRESELECT, None))
            elif candidate is not None:
                values.append(gr.update(value=RACE_PRESELECT))
            if link_box is not None:
                values.append(common.permalink(TAB_RACE, base=base))
            return values[0] if len(values) == 1 else tuple(values)

        handles[TAB_TRY]["race_chip"].click(
            go_race, None, outputs, api_name=False, show_progress="hidden"
        )

    return TabSpec(TAB_TRY, "Try it", render, API_NAMES, connect)


def _event_hooks() -> dict[str, Any]:
    from algenta_spaces.lane import gradio_hooks

    return gradio_hooks()["event"]
