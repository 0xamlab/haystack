"""Benchmark rulebook v0.3 — the measurement protocol every race in the fleet runs under.

Lifted from `apps/spaces/speed-arena/arena/harness.py` (correctness gate before
timing, interleaved round-robin repeats, median with spread, the hardware
footer) and from `apps/spaces/governed-agent/space_core.py` (cgroup-aware CPU
quota). What v0.3 adds, all printed on the card by `cards.py`:

* two discarded warm-ups after the gate call;
* N = 21 interleaved repeats when the warm call takes under 250 ms, else 11;
* a cell budget (60 s) — over it the cell is "not measurable here", no numbers;
* median, P95 (N >= 20) or max, MAD, CV, min and max per lane;
* the ratio best-incumbent / algenta, both absolute times always kept;
* a stability gate: CV <= 0.15 on every lane and the 1-minute load average
  <= CPU quota x 1.5, else "noisy — not recorded" and no numbers;
* the machine from `/proc/cpuinfo`, `/sys/fs/cgroup/cpu.max` and the
  `SPACE_HARDWARE` variable — never a hardcoded tier.

Every clock, load reading and quota is injectable so the protocol is tested
without sleeping.
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

RULEBOOK_VERSION = "0.3"
WARMUPS = 2
REPEATS_FAST = 21
REPEATS_SLOW = 11
FAST_CALL_MS = 250.0
BUDGET_S = 60.0
CV_MAX = 0.15
LOAD_FACTOR = 1.5
P95_MIN_N = 20

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

THREAD_ENV_KEYS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")

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

    @property
    def stable(self) -> bool:
        return self.cv <= CV_MAX


@dataclass
class CellResult:
    status: str
    lanes: list[LaneResult] = field(default_factory=list)
    ratio: float | None = None
    parity_label: str = ""
    reason: str = ""
    n: int = 0
    warmups: int = WARMUPS
    load_1m: float = 0.0
    cpu_quota: int = 1
    elapsed_s: float = 0.0
    ts_utc: str = ""
    seed: int | None = None
    rulebook: str = RULEBOOK_VERSION

    @property
    def measured(self) -> bool:
        return self.status == STATUS_MEASURED

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


def cv(samples: Sequence[float]) -> float:
    """Coefficient of variation (sample standard deviation over mean)."""
    if len(samples) < 2:
        return 0.0
    mean = statistics.fmean(samples)
    if mean <= 0:
        return 0.0
    return statistics.stdev(samples) / mean


def summarise(spec: LaneSpec, samples_ms: Sequence[float]) -> LaneResult:
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


# ---------------------------------------------------------------------------
# Hardware disclosure
# ---------------------------------------------------------------------------

_CPUINFO = Path("/proc/cpuinfo")
_CPU_MAX = Path("/sys/fs/cgroup/cpu.max")
_CFS_QUOTA = Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
_CFS_PERIOD = Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us")


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
    """The 1-minute load average, 0.0 where the platform has none."""
    try:
        return os.getloadavg()[0]
    except (OSError, AttributeError):
        return 0.0


def thread_env(env: Mapping[str, str] | None = None) -> str:
    """`OMP=1 · OPENBLAS=1` from the thread-count variables that are set (same for all lanes)."""
    env = os.environ if env is None else env
    parts = [f"{key.split('_', 1)[0]}={env[key]}" for key in THREAD_ENV_KEYS if key in env]
    return " · ".join(parts)


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
        f"{platform.system()} {platform.machine()}",
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
) -> CellResult:
    """Run one cell under rulebook v0.3 and return every statistic the card prints.

    `correctness_gate` receives the gate-call outputs keyed by lane name and
    returns `(ok, parity_label)`. `repeats=None` picks 21 or 11 from the slowest
    warm-up call. `clock` returns seconds; `loadavg` the 1-minute load.
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

        warm_ms: dict[str, float] = dict.fromkeys(names, 0.0)
        for lane in _round_robin(lanes, warmups, interleave):
            t0 = clock()
            lane.fn()
            warm_ms[lane.name] = (clock() - t0) * 1e3
        n = auto_repeats(max(warm_ms.values())) if repeats is None else repeats
        if n < 2:
            raise ValueError("repeats must be at least 2")
        result.n = n
        say(f"timing {n} interleaved runs")

        samples: dict[str, list[float]] = {name: [] for name in names}
        for lane in _round_robin(lanes, n, interleave):
            if over_budget():
                result.status = STATUS_OVER_BUDGET
                result.reason = f"{OVER_BUDGET_TEXT} — over {budget_s:g} s"
                say(result.reason)
                return result
            t0 = clock()
            lane.fn()
            samples[lane.name].append((clock() - t0) * 1e3)

        result.lanes = [summarise(lane, samples[lane.name]) for lane in lanes]
        result.load_1m = float(loadavg())
        unstable = [lane.name for lane in result.lanes if not lane.stable]
        overloaded = result.load_1m > quota_n * LOAD_FACTOR
        if unstable or overloaded:
            result.status = STATUS_NOISY
            causes = []
            if unstable:
                causes.append("spread above 15 percent on " + ", ".join(unstable))
            if overloaded:
                causes.append(f"load {result.load_1m:.1f} on {quota_n} vCPU")
            result.reason = f"{NOISY_TEXT} — " + "; ".join(causes)
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
