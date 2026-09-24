"""Benchmark rulebook v0.5 — the measurement protocol every race in the fleet runs under.

Lifted from `apps/spaces/speed-arena/arena/harness.py` (correctness gate before
timing, interleaved round-robin repeats, median with spread, the hardware
footer) and from `apps/spaces/governed-agent/space_core.py` (cgroup-aware CPU
quota). What v0.3 added, all printed on the card by `cards.py`:

* two discarded warm-ups after the gate call;
* N = 21 interleaved repeats when the warm call takes under 250 ms, else 11;
* a cell budget (60 s) — over it the cell is "not measurable here", no numbers;
* median, P95 (N >= 20) or max, MAD, CV, min and max per lane;
* the ratio best-incumbent / algenta, both absolute times always kept;
* a stability gate (v0.5/v0.6): the robust spread 1.4826 x MAD / median <= 0.15
  on every lane and the mean within 15 % of the median, else "noisy — not
  recorded" and no numbers; the 1-minute load average is read and disclosed
  on the card's foot (`host load 14.1`), never a gate — inside a Space it is
  the host's load, not the container's (v0.6);
* the machine from `/proc/cpuinfo`, `/sys/fs/cgroup/cpu.max` and the
  `SPACE_HARDWARE` variable — never a hardcoded tier.

What v0.4 changed — one thing, the way `timeit` does it (`docs/spaces/RULEBOOK.md`;
v0.5 then made the stability gate read the robust spread and a mean/median guard, see
`LaneResult.spread`):

* **each timed sample is k back-to-back calls that together last at least
  `SAMPLE_MIN_MS` (10 ms)**, and the per-call time is the sample divided by k.
  k is chosen per lane from its fastest warm-up call (`calls_per_sample`:
  `ceil(10 ms / warm call)`, at most `CALLS_MAX`, 1 for any call already at or
  over 10 ms — a slow lane is timed exactly as before). N stays 21 interleaved
  round-robin samples per lane; median, P95, MAD and CV are computed on the
  per-call figures; the stability gate is unchanged (CV <= 15 % on every lane).
  The card prints `n = 21 × k calls` and the rule in its How-measured text.

  Why: a sub-millisecond call timed one at a time measures the scheduler and
  the timer, not the kernel. On the deployed host (AMD EPYC, 8 vCPU) the hero
  z-test at a 0.09 ms median came back "noisy — not recorded — spread above
  15 percent" on every visitor run after boot. The floor was measured, not
  guessed: on the build Mac under two busy loops beside other sessions (load
  25–30 on 16 vCPU) 2 ms samples recorded the hero 2 of 3 times and the
  Levenshtein S cell 1 of 3, 10 ms samples 3 of 3 and 3 of 3 (hero CV 3.8 %,
  S 12.5 %), 20 ms samples fewer again (`fix5-shots/shared-bench-cards/
  measure_floors.log`); 21 samples of 10 ms cost a fast lane 0.2 s.

Every clock, load reading and quota is injectable so the protocol is tested
without sleeping; `sample_min_ms=0` runs a cell the v0.3 way (one call per
sample) for side-by-side comparisons.
"""

from __future__ import annotations

import logging
import math
import os
import platform
import statistics
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .runtime import pinned_versions, utc_stamp

log = logging.getLogger(__name__)

RULEBOOK_VERSION = "0.6"
#: What every kernel timing on a card includes (rulebook rule 10); the chip on every result card.
TRANSPORT_NOTE = "compiled Mojo kernel over the C ABI · includes JSON marshalling"
WARMUPS = 2
REPEATS_FAST = 21
REPEATS_SLOW = 11
FAST_CALL_MS = 250.0
BUDGET_S = 60.0
CV_MAX = 0.15
#: v0.5 — MAD scaled to a standard deviation (normal sample); the gate reads
#: `ROBUST_SCALE × MAD / median`.
ROBUST_SCALE = 1.4826
#: v0.6 — what `load_1m()` returns where the platform has no load average. A reading is never
#: negative, so the card's foot prints every real one, an idle host's 0.0 included (Codna review
#: on #1150: 0.0 doubled as the sentinel and an idle host's load went unprinted).
LOAD_UNREAD = -1.0
P95_MIN_N = 20
#: v0.4 — a timed sample is k back-to-back calls that together last at least this long; the
#: per-call time is the sample over k. Below it the sample measures the scheduler and the timer
#: (the sweep in the module docstring: 2 and 5 ms samples still failed the gate under noise).
SAMPLE_MIN_MS = 10.0
#: The ceiling on k: a warm-up call that clocked at nearly nothing never runs unbounded
#: (10 ms / 200 = a 50 µs call; anything faster is timed at 200 calls a sample).
CALLS_MAX = 200

SIDE_ALGENTA = "algenta"
SIDE_INCUMBENT = "incumbent"
SIDES = (SIDE_ALGENTA, SIDE_INCUMBENT)

STATUS_MEASURED = "measured"
STATUS_NOISY = "noisy"
STATUS_GATE_FAILED = "gate_failed"
STATUS_OVER_BUDGET = "over_budget"
STATUS_ERROR = "error"

NOISY_TEXT = "noisy — not recorded"
OVER_BUDGET_TEXT = "not measurable here"
#: The stability gate's two causes as a noisy reason names them (`noisy_reason`): the robust
#: spread over the gate, or the mean too far from the median while the spread cleared it.
SPREAD_CAUSE = "spread above {gate} on {lanes}"
SKEW_CAUSE = "mean more than {gate} off the median on {lanes}"

THREAD_ENV_KEYS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
#: The library each thread-count variable pins, as people write it (for the footer when the
#: variables disagree; when they agree the footer says `threads 8` and no name).
THREAD_ENV_NAMES: Mapping[str, str] = {
    "OMP_NUM_THREADS": "OpenMP",
    "OPENBLAS_NUM_THREADS": "OpenBLAS",
    "MKL_NUM_THREADS": "MKL",
}

Gate = Callable[[dict[str, Any]], tuple[bool, str]]


@dataclass(frozen=True)
class LaneSpec:
    """One timed side of a cell: a zero-argument callable returning the materialised answer."""

    name: str
    side: str
    fn: Callable[[], Any]
    version: str = ""
    config: str = ""

    def __post_init__(self) -> None:
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")
        if not self.name.strip():
            raise ValueError("lane name is empty")


@dataclass
class LaneResult:
    name: str
    side: str
    n: int
    median_ms: float
    p95_ms: float
    mad_ms: float
    cv: float
    min_ms: float
    max_ms: float
    version: str = ""
    config: str = ""
    samples_ms: list[float] = field(default_factory=list)
    #: v0.4 — calls per timed sample (1 = one call per sample, the v0.3 way). Every figure above
    #: is per call: a sample of k calls is divided by k before it is recorded (SAMPLE_MIN_MS).
    k: int = 1

    @property
    def spread(self) -> float:
        """v0.5 — the robust spread the stability gate reads: `1.4826 × MAD / median` (the
        MAD scaled to a standard deviation for a normal sample). On a shared cloud host a few
        scheduler spikes inflate the sample standard deviation (the classical CV read 13–15 %
        on the deployed Space) while the median and MAD of the same 21 samples barely move
        (MAD 0.7–1.2 µs on an 85 µs median). The CV stays in the lane table."""
        if self.median_ms <= 0:
            return 0.0
        return ROBUST_SCALE * self.mad_ms / self.median_ms

    @property
    def skew(self) -> float:
        """How far the mean sits from the median, as a share of the median: a 50/50 alternation
        of two timings (coarse-clock jitter one call at a time) has MAD 0 but a mean far from
        its median — the spread alone would call it stable while its median is wrong. 0 when
        the per-call samples were not kept."""
        if not self.samples_ms or self.median_ms <= 0:
            return 0.0
        return abs(statistics.fmean(self.samples_ms) - self.median_ms) / self.median_ms

    @property
    def stable(self) -> bool:
        return self.spread <= CV_MAX and self.skew <= CV_MAX

    @property
    def sample_ms(self) -> float:
        """The median timed sample as the clock saw it: `median_ms × k` (the rule is ≥ 10 ms)."""
        return self.median_ms * self.k


@dataclass
class CellResult:
    status: str
    lanes: list[LaneResult] = field(default_factory=list)
    ratio: float | None = None
    parity_label: str = ""
    reason: str = ""
    n: int = 0
    warmups: int = WARMUPS
    load_1m: float = LOAD_UNREAD
    cpu_quota: int = 1
    elapsed_s: float = 0.0
    ts_utc: str = ""
    seed: int | None = None
    rulebook: str = RULEBOOK_VERSION

    @property
    def measured(self) -> bool:
        return self.status == STATUS_MEASURED

    @property
    def k(self) -> int | None:
        """Calls per timed sample when every lane batched alike (1 = one call per sample); None
        when the lanes differ (a race whose lanes run at different speeds) or nothing was timed.
        `cards.n_chips` prints `n = 21 × k calls` from this, per lane when it is None."""
        calls = {lane.k for lane in self.lanes}
        return calls.pop() if len(calls) == 1 else None

    def lane(self, side: str) -> LaneResult | None:
        """The algenta lane, or the fastest incumbent lane by median."""
        picks = [lane for lane in self.lanes if lane.side == side]
        if not picks:
            return None
        return min(picks, key=lambda lane: lane.median_ms)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def p95(samples: Sequence[float]) -> float:
    """Nearest-rank P95 for N >= 20, else the maximum (a P95 of 11 samples is a guess)."""
    if not samples:
        raise ValueError("no samples")
    ordered = sorted(samples)
    if len(ordered) < P95_MIN_N:
        return ordered[-1]
    rank = math.ceil(0.95 * len(ordered)) - 1
    return ordered[rank]


def mad(samples: Sequence[float]) -> float:
    """Median absolute deviation."""
    med = statistics.median(samples)
    return statistics.median(abs(x - med) for x in samples)


def robust_cv(samples: Sequence[float]) -> float:
    """The gate's spread: `ROBUST_SCALE × MAD / median` (0 for a non-positive median)."""
    med = statistics.median(samples)
    if med <= 0:
        return 0.0
    return ROBUST_SCALE * mad(samples) / med


def cv(samples: Sequence[float]) -> float:
    """Coefficient of variation (sample standard deviation over mean): printed, not gated."""
    if len(samples) < 2:
        return 0.0
    mean = statistics.fmean(samples)
    if mean <= 0:
        return 0.0
    return statistics.stdev(samples) / mean


def summarise(spec: LaneSpec, samples_ms: Sequence[float], *, k: int = 1) -> LaneResult:
    """Every statistic of one lane from its per-call figures; `k` is the calls per sample."""
    if k < 1:
        raise ValueError("calls per sample is at least 1")
    return LaneResult(
        name=spec.name,
        side=spec.side,
        n=len(samples_ms),
        median_ms=statistics.median(samples_ms),
        p95_ms=p95(samples_ms),
        mad_ms=mad(samples_ms),
        cv=cv(samples_ms),
        min_ms=min(samples_ms),
        max_ms=max(samples_ms),
        version=spec.version,
        config=spec.config,
        samples_ms=list(samples_ms),
        k=k,
    )


def ratio_of(lanes: Iterable[LaneResult]) -> float | None:
    """best incumbent median / algenta median; None without an incumbent lane."""
    lanes = list(lanes)
    algenta = [lane for lane in lanes if lane.side == SIDE_ALGENTA]
    incumbents = [lane for lane in lanes if lane.side == SIDE_INCUMBENT]
    if not algenta:
        raise ValueError("a cell needs an algenta lane")
    if not incumbents:
        return None
    best_incumbent = min(lane.median_ms for lane in incumbents)
    ours = min(lane.median_ms for lane in algenta)
    if ours <= 0:
        raise ValueError("algenta median must be positive")
    return best_incumbent / ours


def auto_repeats(warm_call_ms: float) -> int:
    return REPEATS_FAST if warm_call_ms < FAST_CALL_MS else REPEATS_SLOW


def calls_per_sample(
    warm_call_ms: float, sample_min_ms: float = SAMPLE_MIN_MS, cap: int = CALLS_MAX
) -> int:
    """v0.4: the k back-to-back calls that make one timed sample last `sample_min_ms` or more.

    `ceil(sample_min_ms / warm_call_ms)`, never above `cap`, and 1 for a call already at or
    over the floor — so a lane at 10 ms or slower is timed exactly as v0.3 timed it. A warm
    call of zero (or less), or none at all (`warmups=0` leaves a lane at `math.inf`; a NaN reads
    the same), gets the cap — never 1, which would switch batching off for the lane whose cost
    is unknown (Codna review on #1150); `sample_min_ms <= 0` switches batching off (k = 1).
    """
    if sample_min_ms <= 0:
        return 1
    if cap < 1:
        raise ValueError("the cap on calls per sample is at least 1")
    if not (math.isfinite(warm_call_ms) and warm_call_ms > 0):
        return cap
    if warm_call_ms >= sample_min_ms:
        return 1
    # the ratio is rounded before the ceiling so a call clocked at 1.0000000000000009 ms gets
    # k = 2, not 3: the floor is a rule about the sample, not about the clock's last digit
    return max(1, min(cap, math.ceil(round(sample_min_ms / warm_call_ms, 6))))


# ---------------------------------------------------------------------------
# Hardware disclosure
# ---------------------------------------------------------------------------

_CPUINFO = Path("/proc/cpuinfo")
_CPU_MAX = Path("/sys/fs/cgroup/cpu.max")
_CFS_QUOTA = Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
_CFS_PERIOD = Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us")


#: The architecture as people write it: no snake_case token in a caption.
ARCH_NAMES = {"x86_64": "x86-64", "amd64": "x86-64", "aarch64": "arm64", "arm64": "arm64"}


def arch_name(machine: str) -> str:
    """`platform.machine()` spelled the human way (`x86-64`, `arm64`); other values unchanged."""
    return ARCH_NAMES.get(machine.strip().lower(), machine.strip())


def cpu_model(cpuinfo: Path | str = _CPUINFO) -> str:
    """The CPU model line from /proc/cpuinfo; on macOS the sysctl brand string."""
    try:
        with open(cpuinfo, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    if platform.system() == "Darwin":
        import subprocess

        try:
            out = subprocess.run(  # noqa: S603 - fixed argv, no user input
                ["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if out.stdout.strip():
                return out.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return platform.processor() or platform.machine() or "unknown cpu"


def cpu_quota(
    cpu_max: Path | str = _CPU_MAX,
    cfs_quota: Path | str = _CFS_QUOTA,
    cfs_period: Path | str = _CFS_PERIOD,
    fallback: int | None = None,
) -> int:
    """Effective CPU count: cgroup v2 `cpu.max`, then cgroup v1, then os.cpu_count()."""
    try:
        parts = Path(cpu_max).read_text(encoding="utf-8").split()
        if parts and parts[0] != "max":
            return max(1, int(parts[0]) // int(parts[1]))
    except (OSError, ValueError, IndexError):
        pass
    try:
        quota = int(Path(cfs_quota).read_text(encoding="utf-8").strip())
        period = int(Path(cfs_period).read_text(encoding="utf-8").strip())
        if quota > 0 and period > 0:
            return max(1, quota // period)
    except (OSError, ValueError):
        pass
    if fallback is not None:
        return max(1, fallback)
    return max(1, os.cpu_count() or 1)


def load_1m() -> float:
    """The 1-minute load average, `LOAD_UNREAD` where the platform has none."""
    try:
        return os.getloadavg()[0]
    except (OSError, AttributeError):
        return LOAD_UNREAD


def thread_env(env: Mapping[str, str] | None = None) -> str:
    """`threads 8` from the thread-count variables that are set (the same for every lane).

    One figure when the variables that are set agree; `threads OpenMP 8 · OpenBLAS 1` when they
    differ; empty when none is set. Written as words — `OMP=8` is an env-style token, and the
    footer is a caption on the primary card."""
    env = os.environ if env is None else env
    found = [(THREAD_ENV_NAMES[key], env[key].strip()) for key in THREAD_ENV_KEYS if key in env]
    if not found:
        return ""
    if len({value for _, value in found}) == 1:
        return f"threads {found[0][1]}"
    return "threads " + " · ".join(f"{name} {value}" for name, value in found)


def hardware_footer(
    env: Mapping[str, str] | None = None,
    *,
    packages: Iterable[str] = (),
    cpuinfo: Path | str = _CPUINFO,
    cpu_max: Path | str = _CPU_MAX,
) -> str:
    """The machine, disclosed on every card: tier, CPU, quota, OS, interpreter, pins."""
    env = os.environ if env is None else env
    space = env.get("SPACE_ID", "").strip()
    tier = env.get("SPACE_HARDWARE", "").strip()
    if space:
        host = f"Space {space}" + (f" · {tier}" if tier else "")
    else:
        host = "local run" + (f" · {tier}" if tier else "")
    parts = [
        host,
        cpu_model(cpuinfo),
        f"{cpu_quota(cpu_max)} vCPU",
        f"{platform.system()} {arch_name(platform.machine())}",
        f"Python {platform.python_version()}",
    ]
    threads = thread_env(env)
    if threads:
        parts.append(threads)
    for name, version in pinned_versions(packages).items():
        parts.append(f"{name}=={version}" if version else f"{name} not installed")
    parts.append(f"rulebook v{RULEBOOK_VERSION}")
    return " · ".join(parts)


# ---------------------------------------------------------------------------
# The protocol
# ---------------------------------------------------------------------------


def _round_robin(lanes: Sequence[LaneSpec], rounds: int, interleave: bool) -> list[LaneSpec]:
    if interleave:
        return [lane for _ in range(rounds) for lane in lanes]
    return [lane for lane in lanes for _ in range(rounds)]


def _calls_note(calls: Mapping[str, int]) -> str:
    """` × 16 calls` for the progress line when a lane batches; `× 16/1 calls` when lanes differ."""
    distinct = sorted(set(calls.values()), reverse=True)
    if distinct == [1]:
        return ""
    return " × " + "/".join(str(k) for k in distinct) + " calls"


def gate_percent(cv_max: float = CV_MAX) -> str:
    """The gate in a reason's words: `15 percent` (the card's chip prints `15%`)."""
    return f"{cv_max * 100:.0f} percent"


def noisy_reason(lanes: Iterable[LaneResult], cv_max: float = CV_MAX) -> str:
    """`noisy — not recorded — spread above 15 percent on ours`: the gate that failed, named per
    lane, never a stand-in — a lane whose spread cleared the gate while its mean sat too far from
    its median reads `mean more than 15 percent off the median on ours` (a 50/50 alternation has
    MAD 0). The card's chip names the same gate (`cards.stability_chip`: the spread when any lane's
    spread is over, else the mean), so the two never disagree; lanes failing different gates are
    listed cause by cause, the spread first (Codna review on #1150: every noisy verdict said
    "spread"). ValueError when every lane is stable."""
    lanes = list(lanes)
    spread = [lane.name for lane in lanes if lane.spread > cv_max]
    skew = [lane.name for lane in lanes if lane.spread <= cv_max and lane.skew > cv_max]
    gate = gate_percent(cv_max)
    causes = []
    if spread:
        causes.append(SPREAD_CAUSE.format(gate=gate, lanes=", ".join(spread)))
    if skew:
        causes.append(SKEW_CAUSE.format(gate=gate, lanes=", ".join(skew)))
    if not causes:
        raise ValueError("every lane is stable: nothing to report as noisy")
    return f"{NOISY_TEXT} — " + "; ".join(causes)


def run_cell(
    lanes: Sequence[LaneSpec],
    *,
    correctness_gate: Gate,
    warmups: int = WARMUPS,
    repeats: int | None = None,
    budget_s: float = BUDGET_S,
    interleave: bool = True,
    seed: int | None = None,
    clock: Callable[[], float] = time.perf_counter,
    loadavg: Callable[[], float] = load_1m,
    quota: int | None = None,
    progress: Callable[[str], None] | None = None,
    sample_min_ms: float = SAMPLE_MIN_MS,
    calls_max: int = CALLS_MAX,
) -> CellResult:
    """Run one cell under the rulebook (`RULEBOOK_VERSION`); every statistic the card prints.

    `correctness_gate` receives the gate-call outputs keyed by lane name and
    returns `(ok, parity_label)`. `repeats=None` picks 21 or 11 from the slowest
    lane's fastest warm-up call. Each lane's k (`calls_per_sample`) comes from
    that same fastest warm-up call and `sample_min_ms`; `sample_min_ms=0` is the
    v0.3 protocol, one call per sample. `clock` returns seconds; `loadavg` the
    1-minute load.
    """
    if not lanes:
        raise ValueError("no lanes")
    names = [lane.name for lane in lanes]
    if len(set(names)) != len(names):
        raise ValueError(f"lane names must be unique: {names}")
    if not any(lane.side == SIDE_ALGENTA for lane in lanes):
        raise ValueError("a cell needs an algenta lane")

    def say(message: str) -> None:
        log.info(message)
        if progress is not None:
            progress(message)

    quota_n = cpu_quota() if quota is None else quota
    result = CellResult(
        status=STATUS_ERROR,
        warmups=warmups,
        cpu_quota=quota_n,
        seed=seed,
        ts_utc=utc_stamp(),
    )
    t_start = clock()

    def over_budget() -> bool:
        return clock() - t_start > budget_s

    try:
        outputs: dict[str, Any] = {}
        for lane in lanes:
            say(f"checking {lane.name}")
            outputs[lane.name] = lane.fn()
        ok, parity_label = correctness_gate(outputs)
        result.parity_label = parity_label
        if not ok:
            result.status = STATUS_GATE_FAILED
            result.reason = parity_label or "outputs differ"
            say(f"held — {result.reason}")
            return result

        # the fastest warm-up call per lane is the least jittered estimate of its cost
        warm_ms: dict[str, float] = {}
        for lane in _round_robin(lanes, warmups, interleave):
            t0 = clock()
            lane.fn()
            elapsed = (clock() - t0) * 1e3
            warm_ms[lane.name] = min(warm_ms.get(lane.name, elapsed), elapsed)
        n = auto_repeats(max(warm_ms.values(), default=0.0)) if repeats is None else repeats
        if n < 2:
            raise ValueError("repeats must be at least 2")
        result.n = n
        calls = {
            name: calls_per_sample(warm_ms.get(name, math.inf), sample_min_ms, calls_max)
            for name in names
        }
        say(f"timing {n} interleaved runs{_calls_note(calls)}")

        samples: dict[str, list[float]] = {name: [] for name in names}
        for lane in _round_robin(lanes, n, interleave):
            if over_budget():
                result.status = STATUS_OVER_BUDGET
                result.reason = f"{OVER_BUDGET_TEXT} — over {budget_s:g} s"
                say(result.reason)
                return result
            k = calls[lane.name]
            fn = lane.fn
            t0 = clock()
            for _ in range(k):
                fn()
            samples[lane.name].append((clock() - t0) * 1e3 / k)

        result.lanes = [summarise(lane, samples[lane.name], k=calls[lane.name]) for lane in lanes]
        # v0.6: the 1-minute load average is read and disclosed on the card (`host load 14.1`),
        # never a gate — inside a Space the container reads the host's /proc/loadavg, not its
        # own, and the spread + mean/median guard already measure what the load only predicts
        result.load_1m = float(loadavg())
        if not all(lane.stable for lane in result.lanes):
            result.status = STATUS_NOISY
            result.reason = noisy_reason(result.lanes)
            say(result.reason)
            return result

        result.ratio = ratio_of(result.lanes)
        result.status = STATUS_MEASURED
        say("measured")
        return result
    except Exception as exc:
        result.status = STATUS_ERROR
        result.reason = f"{type(exc).__name__}: {exc}"
        log.exception("cell failed")
        if progress is not None:
            progress(result.reason)
        return result
    finally:
        result.elapsed_s = clock() - t_start
