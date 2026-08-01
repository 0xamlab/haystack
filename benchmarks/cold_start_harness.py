#!/usr/bin/env python3
"""Multi-process COLD/WARM/HOT harness for the Mojo benchmarks.

Why this file has to exist
--------------------------
A benchmark must state cold, warm AND hot. Hot alone flatters whichever path
allocates most, because its one-time setup is hidden; cold alone understates
everything. The spread between the tiers is itself the interesting quantity:
cold/hot near 1 means a path is compute-bound and the first call costs what
every call costs, while a large ratio means it is allocation- and
first-touch-bound, so a service handling one request per process never reaches
the hot figure at all.

The hard part is methodological, not mechanical:

    **A cold reading can only be taken once per process, by definition.**

Once a path has run, that process is warm forever. So cold cannot be min-of-N
in-process the way hot is, and a single cold reading is at the mercy of whatever
else the machine is doing. On this machine, at the time of writing, that is a
lot: load average ~400 against 16 cores (~25x oversubscribed) with ~20
concurrent `mojo` processes from other work. Measured consequence: one run of
`measure_columnar_arrow_wire` reported `C2 cold/hot = 26.4x` and the next
reported `0.97x`; a lean-JSON WARM reading came back 9x its own COLD. That is
contention, not cache state. The hot figures survived because min-of-N filters
contention. Cold and warm did not.

So the only way to get a defensible cold number is to take one cold reading per
process and repeat across K PROCESSES:

  * the MINIMUM across K is the floor statistic, and it is the right one:
    contention can only make a reading slower than the work actually takes,
    never faster;
  * the MEDIAN across K is what a reader should expect on a machine in this
    state;
  * the SPREAD (max/min) says whether the tier means anything at all right now.

Every cold figure this harness prints carries K. A cold figure that does not
say how many processes it came from is not a measurement and must not be
published as one.

Runs are STRICTLY SEQUENTIAL and there is deliberately no `--jobs` flag.
K processes in parallel would measure the contention between them, which is the
opposite of the intent.

What it parses
--------------
Any benchmark that prints one of these shapes, in ns or ms or anything else —
the harness does not interpret the unit, it only aggregates like with like:

  1. The reference shape, as emitted by
     `benchmarks/mojo_benchmarks/measure_columnar_arrow_wire.mojo`:

         -- cold / warm / hot, ns per cell --
           B json lean .......... 41.7 / 30.2 / 25.9   cold/hot 1.61
           D layout only ........ unresolved / unresolved / 0.86   cold/hot unresolved

  2. Its ratio line:

           B/C2 advantage: cold 3.4x   warm 2.9x   hot 5.4x

  3. A machine-readable line, for benchmarks converted later (the generator in
     `tests/benchmark_mojo_vs_python.py` should emit this, since a stable
     grammar beats a pretty one when 531 files share an emitter):

         COLD_WARM_HOT <label> <cold> <warm> <hot> [unit]

`unresolved` (also `unavailable`, `n/a`, `-`) is propagated as UNRESOLVED and
never as 0. A sub-microsecond path's single cold reading can fall below the
clock's resolution; printing `0.0 ns` would be a wrong answer — the work
happened, the clock could not see it — and dividing by it yields a meaningless
ratio. Absence is a flag, never a fabricated number.

Context lines (`value profile 0`, `rows=1000 cols=4 cells=4000`) are tracked so
the same label at two sizes is not pooled into one bogus average.

Usage
-----
    scripts/run_repo_python.sh benchmarks/cold_start_harness.py \
        measure_columnar_arrow_wire --processes 25

    # JIT instead of a compiled binary (cold then also pays lazy compilation):
    ... --mode run

    # machine-readable, for a docs page or a later diff:
    ... --json-out /tmp/cold.json

Exit status is 0 if at least one process produced figures, 1 otherwise. It does
NOT fail on a wide spread: a wide spread is a reported fact about the machine,
not a harness error. Nanoseconds are never gated here — gates belong in the
benchmarks, on shape and correctness.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MOJO_BENCH_DIR = _REPO_ROOT / "benchmarks" / "mojo_benchmarks"
_MOJO_ENV = _REPO_ROOT / "mojo_env"
_ENGINE_INCLUDE = "-I../mojo/engine"

UNRESOLVED = "unresolved"
_UNRESOLVED_TOKENS = frozenset({"unresolved", "unavailable", "n/a", "na", "none", "-", "--"})

TIERS = ("cold", "warm", "hot")

# ── output grammar ────────────────────────────────────────────────────────────
# Kept deliberately narrow: every token in a triple must be a number or an
# explicit unresolved marker, so a line like
#   "wire bytes: json rows 900 | @u8 arg 300   (json/@u8 = 3.0)"
# cannot be mistaken for a cold/warm/hot triple just because it contains "/".
_UNIT_HEADER = re.compile(
    r"cold\s*/\s*warm\s*/\s*hot\s*[,:]\s*(?P<unit>[^─\-=]+?)\s*(?:[─\-=]{2,}\s*)?$"
)
_TRIPLE = re.compile(
    r"^\s*(?P<label>\S.*?)\s*[.·…]{3,}\s*"
    r"(?P<cold>[^\s/]+)\s*/\s*(?P<warm>[^\s/]+)\s*/\s*(?P<hot>[^\s/]+)\s*(?P<rest>.*)$"
)
_ADVANTAGE = re.compile(
    r"^\s*(?P<label>\S.*?)\s*:\s*cold\s+(?P<cold>\S+?)x?\s+"
    r"warm\s+(?P<warm>\S+?)x?\s+hot\s+(?P<hot>\S+?)x?\s*$"
)
_MACHINE = re.compile(
    r"^\s*COLD_WARM_HOT\s+(?P<label>\S+)\s+(?P<cold>\S+)\s+(?P<warm>\S+)\s+"
    r"(?P<hot>\S+)(?:\s+(?P<unit>\S+))?\s*$"
)
_CTX_PROFILE = re.compile(r"value profile\s+(?P<profile>\d+)")
# Anchored: a size line is a size line, not any line that happens to contain "rows=".
_CTX_SIZE = re.compile(
    r"^\s*(?:rows|size|n)=(?P<rows>\d+)"
    r"(?:\s+cols=(?P<cols>\d+))?(?:\s+cells=(?P<cells>\d+))?\s*$"
)
_GATE = re.compile(r"^\s*BENCH_GATE\s+(?P<name>\S+)\s+(?P<verdict>PASS|FAIL)\b(?P<rest>.*)$")


def _parse_value(token: str) -> float | None:
    """A tier reading: a float, or None meaning UNRESOLVED. Never 0-for-absent."""
    cleaned = token.strip().strip(",;")
    if cleaned.lower() in _UNRESOLVED_TOKENS:
        return None
    if cleaned.endswith("x"):
        cleaned = cleaned[:-1]
    try:
        value = float(cleaned)
    except ValueError:
        return None
    # A reported 0 is the clock failing to see the work, not the work being free.
    # Treat it as unresolved rather than publishing 0 or dividing by it.
    if value <= 0.0:
        return None
    return value


@dataclass
class RunResult:
    """One process: its exit status, its wall time, and the figures it printed."""

    index: int
    returncode: int | None
    wall_s: float
    figures: dict[tuple[str, str], dict[str, float | None]] = field(default_factory=dict)
    units: dict[tuple[str, str], str] = field(default_factory=dict)
    gate_pass: int = 0
    gate_fail: int = 0
    error_lines: list[str] = field(default_factory=list)
    timed_out: bool = False
    stdout: str = ""

    @property
    def ok(self) -> bool:
        return (not self.timed_out) and self.returncode == 0 and bool(self.figures)


def _context_key(ctx: dict[str, str]) -> str:
    if not ctx:
        return "(no context)"
    order = ("profile", "size")
    return " ".join(ctx[name] for name in order if name in ctx)


def parse_output(text: str) -> RunResult:
    """Pull every cold/warm/hot triple out of one process's stdout.

    Defensive on purpose: an unparseable line is skipped, not guessed at, and a
    process that printed nothing parseable is reported as such rather than
    silently contributing zero rows to a published average.
    """
    result = RunResult(index=-1, returncode=0, wall_s=0.0)
    ctx: dict[str, str] = {}
    unit = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue

        if "❌" in line or "⚠" in line:
            result.error_lines.append(line.strip())

        gate = _GATE.match(line)
        if gate:
            if gate.group("verdict") == "PASS":
                result.gate_pass += 1
            else:
                result.gate_fail += 1
            continue

        profile = _CTX_PROFILE.search(line)
        if profile:
            ctx["profile"] = f"profile={profile.group('profile')}"
            ctx.pop("size", None)
            continue
        size = _CTX_SIZE.match(line)
        if size:
            parts = [f"rows={size.group('rows')}"]
            if size.group("cols"):
                parts.append(f"cols={size.group('cols')}")
            if size.group("cells"):
                parts.append(f"cells={size.group('cells')}")
            ctx["size"] = " ".join(parts)
            continue

        header = _UNIT_HEADER.search(line)
        if header:
            unit = header.group("unit").strip()
            continue

        machine = _MACHINE.match(line)
        if machine:
            key = (_context_key(ctx), machine.group("label"))
            result.figures[key] = {tier: _parse_value(machine.group(tier)) for tier in TIERS}
            result.units[key] = (machine.group("unit") or unit or "").strip()
            continue

        advantage = _ADVANTAGE.match(line)
        if advantage:
            key = (_context_key(ctx), advantage.group("label"))
            values = {tier: _parse_value(advantage.group(tier)) for tier in TIERS}
            if any(value is not None for value in values.values()):
                result.figures[key] = values
                result.units[key] = "x (ratio)"
            continue

        triple = _TRIPLE.match(line)
        if triple:
            tokens = {tier: triple.group(tier) for tier in TIERS}
            # Require the HOT token to be a real number. A row whose every token
            # is unparseable is not a figure, it is prose that happened to fit.
            if _parse_value(tokens["hot"]) is None and all(
                token.strip().lower() not in _UNRESOLVED_TOKENS for token in tokens.values()
            ):
                continue
            label = triple.group("label").strip()
            key = (_context_key(ctx), label)
            result.figures[key] = {tier: _parse_value(tokens[tier]) for tier in TIERS}
            result.units[key] = unit
    return result


# ── environment ───────────────────────────────────────────────────────────────
def _find_pixi() -> str | None:
    explicit = os.environ.get("PIXI_BIN")
    if explicit and os.access(explicit, os.X_OK):
        return explicit
    found = shutil.which("pixi")
    if found:
        return found
    fallback = _REPO_ROOT / ".pixi" / "bin" / "pixi"
    if fallback.is_file() and os.access(fallback, os.X_OK):
        return str(fallback)
    return None


def _loadavg() -> tuple[float, float, float]:
    try:
        return os.getloadavg()
    except OSError:  # pragma: no cover - platform without getloadavg
        return (float("nan"),) * 3


def _mojo_process_count() -> int | None:
    """Concurrent `mojo` processes. Part of the measurement on this machine.

    `-x` on purpose: `pgrep -f mojo` also matches editor and browser helpers whose
    command line happens to contain the string, which inflates the figure by an order
    of magnitude and would misdescribe the load a reader is being asked to weigh.
    """
    pgrep = shutil.which("pgrep")
    if pgrep is None:
        return None
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell, resolved path
            [pgrep, "-x", "mojo"], capture_output=True, text=True, timeout=15
        )
    # Two handlers, not `except (OSError, subprocess.SubprocessError)`: ruff 0.15.11's
    # formatter rewrites that tuple into the Python-2 `except A, B:` and leaves the file
    # unparseable. Reproduced with `ruff format` on a five-line file, so it is the tool.
    except OSError:
        return None
    except subprocess.SubprocessError:
        return None
    return len([line for line in proc.stdout.split() if line.strip()])


def _hardware() -> dict[str, object]:
    info: dict[str, object] = {
        "machine": platform.machine(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
    }
    sysctl = shutil.which("sysctl")
    if sysctl is None:
        return info
    for key, sysctl_name in (("cpu_brand", "machdep.cpu.brand_string"), ("ncpu", "hw.ncpu")):
        try:
            proc = subprocess.run(  # noqa: S603 - fixed argv, no shell, resolved path
                [sysctl, "-n", sysctl_name], capture_output=True, text=True, timeout=15
            )
            if proc.returncode == 0:
                info[key] = proc.stdout.strip()
        except OSError:
            pass
        except subprocess.SubprocessError:
            pass
    return info


# ── running ───────────────────────────────────────────────────────────────────
def resolve_source(target: str) -> Path:
    candidate = Path(target)
    if candidate.is_file():
        return candidate.resolve()
    for name in (target, f"{target}.mojo"):
        path = _MOJO_BENCH_DIR / name
        if path.is_file():
            return path.resolve()
    raise SystemExit(f"benchmark not found: {target!r} (looked in {_MOJO_BENCH_DIR} and as a path)")


def build_binary(source: Path, out_dir: Path, force: bool, timeout_s: float) -> Path:
    """Compile once, run K times.

    Compiled rather than JIT for the default path: `mojo run` pays lazy
    compilation inside the process, which lands ON TOP of the cold reading and
    is not what a deployed worker pays. `--mode run` is offered for the case
    where JIT-inclusive cold is what you actually want to know, and it is
    labelled as such in the output.
    """
    pixi = _find_pixi()
    if pixi is None:
        raise SystemExit("no pixi binary found; set PIXI_BIN or run scripts/install_mojo.sh")
    out_dir.mkdir(parents=True, exist_ok=True)
    binary = out_dir / source.stem
    if not force and binary.is_file() and binary.stat().st_mtime >= source.stat().st_mtime:
        print(f"reusing binary {binary} (newer than source; --force-build to recompile)")
        return binary
    cmd = [pixi, "run", "mojo", "build", _ENGINE_INCLUDE, str(source), "-o", str(binary)]
    print(f"building: {' '.join(cmd)}  (cwd={_MOJO_ENV})")
    started = time.monotonic()
    proc = subprocess.run(  # noqa: S603 - repo toolchain, fixed argv, no shell
        cmd, cwd=str(_MOJO_ENV), capture_output=True, text=True, timeout=timeout_s
    )
    elapsed = time.monotonic() - started
    if proc.returncode != 0 or not binary.is_file():
        sys.stderr.write(proc.stdout[-4000:])
        sys.stderr.write(proc.stderr[-4000:])
        raise SystemExit(f"build failed after {elapsed:.1f}s (rc={proc.returncode})")
    print(f"built in {elapsed:.1f}s -> {binary}")
    return binary


def run_command(mode: str, source: Path, binary: Path | None) -> tuple[list[str], str]:
    if mode == "build":
        assert binary is not None
        return [str(binary)], str(source.parent)
    pixi = _find_pixi()
    if pixi is None:
        raise SystemExit("no pixi binary found; set PIXI_BIN or run scripts/install_mojo.sh")
    return [pixi, "run", "mojo", "run", _ENGINE_INCLUDE, str(source)], str(_MOJO_ENV)


def run_k_processes(
    cmd: list[str], cwd: str, processes: int, timeout_s: float, settle_s: float
) -> list[RunResult]:
    """K separate processes, one after another. Never in parallel — see module docstring."""
    results: list[RunResult] = []
    for index in range(processes):
        started = time.monotonic()
        timed_out = False
        stdout = ""
        returncode: int | None = None
        try:
            proc = subprocess.run(  # noqa: S603 - the benchmark itself, fixed argv, no shell
                cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout_s
            )
            stdout = proc.stdout + proc.stderr
            returncode = proc.returncode
        except subprocess.TimeoutExpired as expired:
            timed_out = True
            stdout = (
                (expired.stdout or b"").decode("utf-8", "replace")
                if isinstance(expired.stdout, bytes)
                else (expired.stdout or "")
            )
        wall = time.monotonic() - started
        parsed = parse_output(stdout)
        parsed.index = index
        parsed.returncode = returncode
        parsed.wall_s = wall
        parsed.timed_out = timed_out
        parsed.stdout = stdout
        results.append(parsed)
        status = "ok" if parsed.ok else ("TIMEOUT" if timed_out else f"rc={returncode}")
        print(
            f"  process {index + 1}/{processes}: {status}  {wall:.1f}s  "
            f"{len(parsed.figures)} figures  load1={_loadavg()[0]:.0f}",
            flush=True,
        )
        if settle_s > 0 and index + 1 < processes:
            time.sleep(settle_s)
    return results


# ── aggregation ───────────────────────────────────────────────────────────────
@dataclass
class TierStats:
    resolved: int
    unresolved: int
    minimum: float | None
    median: float | None
    maximum: float | None

    @property
    def spread(self) -> float | None:
        if self.minimum is None or self.maximum is None or self.minimum <= 0:
            return None
        return self.maximum / self.minimum

    def to_json(self) -> dict[str, object]:
        return {
            "resolved_processes": self.resolved,
            "unresolved_processes": self.unresolved,
            "min": self.minimum,
            "median": self.median,
            "max": self.maximum,
            "spread_x": self.spread,
        }

    def render(self, tier: str) -> str:
        if self.minimum is None:
            return (
                f"    {tier:<5} {UNRESOLVED} in every one of "
                f"{self.resolved + self.unresolved} processes"
            )
        spread = self.spread
        spread_text = f"{spread:.2f}x" if spread is not None else UNRESOLVED
        tail = ""
        if self.unresolved:
            tail = f"   [{self.unresolved} process(es) {UNRESOLVED}]"
        return (
            f"    {tier:<5} min {self.minimum:>12.4f}   median {self.median:>12.4f}   "
            f"max {self.maximum:>12.4f}   spread {spread_text:>9}"
            f"   n={self.resolved}{tail}"
        )


def summarise(values: list[float | None]) -> TierStats:
    resolved = [value for value in values if value is not None]
    return TierStats(
        resolved=len(resolved),
        unresolved=len(values) - len(resolved),
        minimum=min(resolved) if resolved else None,
        median=statistics.median(resolved) if resolved else None,
        maximum=max(resolved) if resolved else None,
    )


def aggregate(results: list[RunResult]) -> dict[tuple[str, str], dict[str, object]]:
    usable = [result for result in results if result.ok]
    keys: list[tuple[str, str]] = []
    for result in usable:
        for key in result.figures:
            if key not in keys:
                keys.append(key)
    table: dict[tuple[str, str], dict[str, object]] = {}
    for key in keys:
        per_tier: dict[str, object] = {}
        for tier in TIERS:
            samples = [result.figures[key][tier] for result in usable if key in result.figures]
            per_tier[tier] = summarise(samples)
        unit = ""
        for result in usable:
            if result.units.get(key):
                unit = result.units[key]
                break
        per_tier["unit"] = unit
        per_tier["present_in"] = sum(1 for result in usable if key in result.figures)
        table[key] = per_tier
    return table


def _is_ratio_row(unit: str) -> bool:
    """Is this row a derived RATIO rather than a cost?

    It matters because the `cold < hot` plausibility check below is only valid for a
    monotone cost. An ADVANTAGE ratio is legitimately smaller when cold — that is the
    finding, not damage: a path whose lead collapses on a first call is the wrong one to
    quote for a service that handles one request per process.
    """
    lowered = unit.strip().lower()
    return "ratio" in lowered or lowered in {"x", "×"}


def _cold_floor_below_hot_floor(stats: dict[str, object]) -> bool | None:
    """True when this row's cold floor undercuts its own hot floor — measurement damage.

    None when either tier never resolved (an absent reading is not a comparison) or when
    the row is a ratio (where cold < hot is a legitimate result).
    """
    cold: TierStats = stats["cold"]  # type: ignore[assignment]
    hot: TierStats = stats["hot"]  # type: ignore[assignment]
    if cold.minimum is None or hot.minimum is None:
        return None
    if _is_ratio_row(str(stats.get("unit") or "")):
        return None
    return cold.minimum < hot.minimum


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Multi-process cold/warm/hot harness for the Mojo benchmarks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="A cold figure without a process count K is not publishable.",
    )
    parser.add_argument(
        "target",
        help="benchmark name (e.g. measure_columnar_arrow_wire) or a path to a .mojo file",
    )
    parser.add_argument(
        "-K",
        "--processes",
        type=int,
        default=25,
        help="how many SEPARATE processes to launch (default 25: one cold reading each)",
    )
    parser.add_argument(
        "--mode",
        choices=("build", "run"),
        default="build",
        help="build = compile once then run the binary K times (default); "
        "run = `mojo run` K times, so cold also includes lazy JIT compilation",
    )
    parser.add_argument("--force-build", action="store_true", help="recompile even if cached")
    parser.add_argument(
        "--binary-dir",
        default=str(Path(tempfile.gettempdir()) / "algenta_cold_harness"),
        help="where compiled benchmark binaries are cached",
    )
    parser.add_argument(
        "--timeout", type=float, default=1800.0, help="per-process timeout, seconds"
    )
    parser.add_argument(
        "--build-timeout", type=float, default=3600.0, help="compile timeout, seconds"
    )
    parser.add_argument(
        "--settle",
        type=float,
        default=0.25,
        help="seconds between processes, so one teardown does not land in the next cold read",
    )
    parser.add_argument(
        "--spread-threshold",
        type=float,
        default=3.0,
        help="max/min above this is called out prominently as machine noise (default 3.0)",
    )
    parser.add_argument(
        "--json-out", help="also write the full result, including per-process readings"
    )
    parser.add_argument(
        "--show-first-output", action="store_true", help="echo the first process's stdout"
    )
    args = parser.parse_args()

    if args.processes < 1:
        raise SystemExit("--processes must be >= 1")

    source = resolve_source(args.target)
    binary = None
    if args.mode == "build":
        binary = build_binary(source, Path(args.binary_dir), args.force_build, args.build_timeout)
    cmd, cwd = run_command(args.mode, source, binary)

    hardware = _hardware()
    load_start = _loadavg()
    mojo_start = _mojo_process_count()
    wall_started = time.monotonic()

    print("")
    print("=" * 78)
    print(f"COLD / WARM / HOT across K={args.processes} SEPARATE PROCESSES")
    print(f"  benchmark ....... {source}")
    print(
        f"  mode ............ {args.mode}"
        + (
            "  (compiled binary; cold excludes JIT)"
            if args.mode == "build"
            else "  (mojo run; cold INCLUDES lazy JIT compilation)"
        )
    )
    print(f"  command ......... {' '.join(cmd)}")
    print(
        f"  hardware ........ {hardware.get('cpu_brand', '?')}  {hardware.get('machine')}  "
        f"ncpu={hardware.get('ncpu', hardware.get('cpu_count'))}"
    )
    print(
        f"  load at start ... {load_start[0]:.2f} {load_start[1]:.2f} {load_start[2]:.2f}"
        f"   concurrent mojo processes: {mojo_start}"
    )
    print("  runs are sequential: K in parallel would measure contention, not cold")
    print("=" * 78)

    results = run_k_processes(cmd, cwd, args.processes, args.timeout, args.settle)

    load_end = _loadavg()
    mojo_end = _mojo_process_count()
    total_wall = time.monotonic() - wall_started
    usable = [result for result in results if result.ok]
    table = aggregate(results)

    print("")
    print("-" * 78)
    bad_exit = sum(
        1 for result in results if not result.timed_out and result.returncode not in (0, None)
    )
    print(
        f"processes launched {len(results)}   produced figures {len(usable)}   "
        f"timed out {sum(1 for r in results if r.timed_out)}   "
        f"nonzero exit {bad_exit}"
    )
    print(
        f"load at end ..... {load_end[0]:.2f} {load_end[1]:.2f} {load_end[2]:.2f}"
        f"   concurrent mojo processes: {mojo_end}"
    )
    print(
        f"total wall ...... {total_wall:.1f}s   per-process wall: "
        f"min {min((r.wall_s for r in results), default=0):.1f}s "
        f"median {statistics.median([r.wall_s for r in results]) if results else 0:.1f}s "
        f"max {max((r.wall_s for r in results), default=0):.1f}s"
    )
    gate_fail = sum(result.gate_fail for result in results)
    gate_pass = sum(result.gate_pass for result in results)
    if gate_pass or gate_fail:
        print(f"BENCH_GATE ...... {gate_pass} PASS / {gate_fail} FAIL across all processes")
    if gate_fail:
        print("  !! a gate FAILED: correctness is not established, so no timing below is a result")
    errors = sorted({line for result in results for line in result.error_lines})
    if errors:
        print(f"benchmark-reported problems ({len(errors)} distinct):")
        for line in errors[:10]:
            print(f"    {line}")
    print("-" * 78)

    if not usable:
        print("")
        print("NO PROCESS PRODUCED A COLD/WARM/HOT FIGURE.")
        print("Either the benchmark does not report the three tiers yet, or every run failed.")
        if results and results[0].stdout:
            print("first process output (tail):")
            for line in results[0].stdout.splitlines()[-25:]:
                print(f"    {line}")
        return 1

    if args.show_first_output:
        print("")
        print("── first process, verbatim ──")
        print(usable[0].stdout)

    print("")
    print(f"Each row below: min / median / max ACROSS {len(usable)} PROCESSES.")
    print(
        "cold and warm are ONE reading per process (a cold reading cannot be repeated"
        " in-process); hot is each process's own min-of-N, so `hot min` is a min of mins."
    )
    print(
        "The MINIMUM is the floor statistic: contention can only slow a reading, never"
        " speed it. The MEDIAN is what this machine currently delivers."
    )
    print("")

    noisy: list[tuple[tuple[str, str], str, float]] = []
    implausible: list[tuple[tuple[str, str], float]] = []
    last_context = None
    for (context, label), stats in table.items():
        if context != last_context:
            print(f"┌ {context}")
            last_context = context
        unit = stats["unit"] or "(unit as printed)"
        print(f"│ {label}   [{unit}]   reported by {stats['present_in']}/{len(usable)} processes")
        for tier in TIERS:
            tier_stats: TierStats = stats[tier]  # type: ignore[assignment]
            print(tier_stats.render(tier))
            spread = tier_stats.spread
            if spread is not None and spread > args.spread_threshold and tier != "hot":
                noisy.append(((context, label), tier, spread))
        cold: TierStats = stats["cold"]  # type: ignore[assignment]
        hot: TierStats = stats["hot"]  # type: ignore[assignment]
        if cold.minimum is not None and hot.minimum is not None and hot.median:
            # min/min is the defensible ratio: both terms are floors. median/median is
            # printed beside it because that is what this machine currently delivers,
            # and if the two disagree wildly the tier is contention-dominated.
            ratio = cold.minimum / hot.minimum
            print(f"    cold/hot  floor {ratio:.2f}x   median {cold.median / hot.median:.2f}x")
            # A cold call does STRICTLY MORE than a steady-state one — first-touch page
            # faults, cold i-cache, cold predictors — so cold < hot cannot be a property
            # of the work. When it happens, one of the two readings is contaminated:
            # either every sample in the hot min-of-N was contended, or the single cold
            # reading landed at the clock's granularity (one tick spread over many cells
            # reads as a suspiciously tiny per-cell figure without ever being exactly 0,
            # so the benchmark's own `<= 0 means unresolved` check cannot catch it).
            # Either way the row is not publishable, and saying so beats printing 0.00x.
            if ratio < 1.0 and not _is_ratio_row(str(stats["unit"] or "")):
                implausible.append(((context, label), ratio))
                print(
                    f"      !! cold floor is BELOW the hot floor ({ratio:.3f}x): not a"
                    " property of the work. Reading contaminated (contended hot loop or"
                    " clock-granularity cold tick) — do not publish this row's cold tier."
                )
            elif ratio < 1.0:
                print(
                    f"      note: this ADVANTAGE shrinks when cold ({ratio:.2f}x of its"
                    " hot value). The hot ratio is not the one to quote for a service"
                    " that handles one request per process."
                )
        elif cold.minimum is None:
            print(f"    cold/hot  {UNRESOLVED} (cold never resolved above the clock)")

    print("")
    if implausible:
        print("!" * 78)
        print(f"!! {len(implausible)} row(s) report a cold floor BELOW their own hot floor.")
        print("!! Cold does strictly more work than hot, so this is measurement damage, not")
        print("!! a result. Treat these rows' cold tier as unresolved:")
        for (context, label), ratio in sorted(implausible, key=lambda item: item[1])[:12]:
            print(f"!!   {ratio:8.3f}x  {context} | {label}")
        print("!" * 78)
        print("")
    if noisy:
        print("!" * 78)
        print(
            f"!! SPREAD WARNING: {len(noisy)} cold/warm row(s) vary by more than "
            f"{args.spread_threshold:.1f}x across the K={len(usable)} processes."
        )
        print("!! At this load the cold tier is NOT a point estimate. Publish the MIN as a")
        print("!! floor, state K, and state the load — do not quote the median as a result.")
        for (context, label), tier, spread in sorted(noisy, key=lambda item: -item[2])[:12]:
            print(f"!!   {spread:8.1f}x  {tier:<4}  {context} | {label}")
        print("!" * 78)
    else:
        print(
            f"Spread across K={len(usable)} processes is within {args.spread_threshold:.1f}x on "
            "every cold and warm row: the cold tier is stable enough to quote a median."
        )

    print("")
    print(
        f"K = {len(usable)} processes with figures (of {len(results)} launched). "
        f"Load {load_start[0]:.0f} -> {load_end[0]:.0f} (1-min), "
        f"{hardware.get('ncpu', hardware.get('cpu_count'))} cores. "
        "Every figure here is an UPPER BOUND on the work: nothing on a loaded machine "
        "measures faster than the work takes."
    )

    if args.json_out:
        payload = {
            "benchmark": str(source),
            "mode": args.mode,
            "command": cmd,
            "processes_launched": len(results),
            "processes_with_figures": len(usable),
            "K": len(usable),
            "hardware": hardware,
            "load_average_start": list(load_start),
            "load_average_end": list(load_end),
            "concurrent_mojo_processes_start": mojo_start,
            "concurrent_mojo_processes_end": mojo_end,
            "total_wall_s": total_wall,
            "spread_threshold_x": args.spread_threshold,
            "gate_pass": gate_pass,
            "gate_fail": gate_fail,
            "note": (
                "cold and warm are one reading per process; hot is each process's own "
                "min-of-N. 'unresolved' means the clock could not see the work and is "
                "never 0."
            ),
            "figures": [
                {
                    "context": context,
                    "label": label,
                    "unit": stats["unit"],
                    "present_in_processes": stats["present_in"],
                    "cold_floor_below_hot_floor": _cold_floor_below_hot_floor(stats),
                    **{
                        tier: stats[tier].to_json()  # type: ignore[union-attr]
                        for tier in TIERS
                    },
                    "per_process": [
                        {
                            "process": result.index,
                            **{tier: result.figures[(context, label)][tier] for tier in TIERS},
                        }
                        for result in usable
                        if (context, label) in result.figures
                    ],
                }
                for (context, label), stats in table.items()
            ],
            "per_process_runs": [
                {
                    "process": result.index,
                    "returncode": result.returncode,
                    "timed_out": result.timed_out,
                    "wall_s": result.wall_s,
                    "figures": len(result.figures),
                    "gate_pass": result.gate_pass,
                    "gate_fail": result.gate_fail,
                }
                for result in results
            ],
        }
        Path(args.json_out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
