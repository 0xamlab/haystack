"""Gate 0 boundary guards for the timing lane.

These encode the four rules the plan calls architectural rather than stylistic. Each one exists because
the failure it prevents is SILENT — you get a plausible number, not an error.

  * COMPUTE BOUNDARY. All modelled race, statistical, optimization, simulation and decision calculation
    executes in Mojo. "Python never computes" is not literally enforceable, so the testable form is: no
    numpy / scipy / pandas under the timing path, and no aggregation in the storage lane.
  * CLICKHOUSE ISOLATION. The decision path reads the append-only event log only. ClickHouse holds
    corrected, consolidated and final data by design, so a decision path querying it would reintroduce
    look-ahead through the storage layer.
  * NO SILENT FALLBACK. A Python fallback that quietly answers a kernel call would invalidate every
    speed and determinism claim while still returning numbers.
  * RNG PROCESS REGISTRY IS EXHAUSTIVE. A process_id used by a literal but absent from the registry is
    an aliasing hazard: registering a new process on top of it silently couples two streams. This
    already happened once — the joint bootstrap held a hardcoded 9.

The numpy exception is DOCUMENTED rather than quietly tolerated, because a guard with an undeclared hole
is worse than no guard: scripts/timing/validate_rng.py cross-checks our Philox against numpy's
Philox. That is independent triangulation of the generator the whole determinism claim rests on, and
removing numpy there would weaken the evidence rather than strengthen the boundary.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TIMING_PY = (ROOT / "scripts" / "timing", ROOT / "benchmarks" / "timing")
KERNELS = ROOT / "mojo" / "engine"

# path -> why it is allowed. Anything not listed here fails the guard.
NUMERIC_IMPORT_EXCEPTIONS = {
    "scripts/timing/validate_rng.py":
        "cross-checks our Philox against numpy's Philox — independent triangulation of the generator "
        "the determinism claim rests on, so removing it would weaken the evidence",
    "benchmarks/timing/numpy_baseline.py":
        "IS the optimised NumPy arm of the rung-2 controlled speed comparison. The claim is that the "
        "kernel is faster than an optimised NumPy implementation of the SAME model, which requires one "
        "to exist; it is a baseline, not a computation on the decision path",
}
FORBIDDEN_MODULES = {"numpy", "scipy", "pandas", "sklearn", "statsmodels", "torch"}


def _python_files() -> list[Path]:
    out: list[Path] = []
    for d in TIMING_PY:
        if d.exists():
            out.extend(sorted(p for p in d.rglob("*.py") if "__pycache__" not in p.parts))
    return out


def test_no_numeric_python_libraries_under_the_timing_path() -> None:
    """A modelled calculation done in numpy is still a modelled calculation done outside Mojo."""
    assert _python_files(), "guard found no timing Python files — it would pass vacuously"
    offences: list[str] = []
    for path in _python_files():
        rel = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or "").split(".")[0]]
            else:
                continue
            for name in names:
                if name in FORBIDDEN_MODULES and rel not in NUMERIC_IMPORT_EXCEPTIONS:
                    offences.append(f"{rel}:{node.lineno} imports {name}")
    assert not offences, (
        "modelled computation must execute in Mojo:\n  " + "\n  ".join(offences)
        + "\n\nIf an import is genuinely verification rather than computation, add it to "
          "NUMERIC_IMPORT_EXCEPTIONS with the reason."
    )


def test_numeric_import_exceptions_are_all_still_real() -> None:
    """An exception for a file that no longer imports the thing is a hole waiting to be reused."""
    stale = []
    for rel, reason in NUMERIC_IMPORT_EXCEPTIONS.items():
        p = ROOT / rel
        if not p.exists():
            stale.append(f"{rel} no longer exists")
            continue
        src = p.read_text()
        if not any(re.search(rf"\b(import|from)\s+{m}\b", src) for m in FORBIDDEN_MODULES):
            stale.append(f"{rel} no longer imports a forbidden module — drop the exception")
        assert reason.strip(), f"{rel} exception carries no reason"
    assert not stale, "stale exceptions:\n  " + "\n  ".join(stale)


def test_decision_path_holds_no_clickhouse_capability() -> None:
    """ClickHouse is a scorer and analytics surface. The decision path reads the event log only.

    Not style: ClickHouse stores corrected, consolidated and FINAL data, so a decision path with a
    route to it reintroduces look-ahead through the storage layer, and an as-of replay that consults it
    can be contaminated while every test still passes.
    """
    offences = []
    for path in _python_files():
        rel = path.relative_to(ROOT).as_posix()
        # the writer and the audit shipper are the only holders of this capability, by design
        if "clickhouse" in path.name.lower() or "outbox" in path.name.lower():
            continue
        src = path.read_text()
        for pat in (r"\bclickhouse_connect\b", r"\bclickhouse_driver\b",
                    r"CLICKHOUSE_(?:DSN|URL|PASSWORD|USER)", r"\bclickhouse://"):
            m = re.search(pat, src)
            if m:
                offences.append(f"{rel}: {m.group(0)}")
    assert not offences, (
        "the decision path must hold no ClickHouse import, DSN or credential:\n  "
        + "\n  ".join(offences)
    )


def test_rng_process_registry_covers_every_process_id_in_use() -> None:
    """Every process_id passed to the RNG must be a registered alias, never a bare integer literal.

    The joint bootstrap in option_board carried a hardcoded 9 that was absent from the registry, so
    registering a new process at 9 aliased two streams. Nothing failed — the two happened not to
    overlap. This makes the next one fail loudly instead.
    """
    rng = (KERNELS / "counter_rng.mojo").read_text()
    registered = set(re.findall(r"alias (PROCESS_[A-Z_]+): UInt64 = (\d+)", rng))
    assert registered, "no PROCESS_* aliases found — the guard would pass vacuously"

    ids = [int(v) for _, v in registered]
    assert len(ids) == len(set(ids)), (
        "two PROCESS_* aliases share a value, which silently couples their streams: "
        + ", ".join(f"{n}={v}" for n, v in sorted(registered, key=lambda kv: int(kv[1])))
    )

    names = {n for n, _ in registered}
    literals = []
    for f in sorted(KERNELS.glob("timing_*.mojo")):
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if "#" in line:
                line = line[: line.index("#")]
            # the process_id is the 6th argument of the rng/philox helpers
            for call in re.finditer(
                r"\b(?:rng_uniform|rng_uniform_left_open|rng_bernoulli|rng_exponential|"
                r"rng_normal|rng_normal_scaled|philox_word)\s*\(([^)]*)\)",
                line,
            ):
                args = [a.strip() for a in call.group(1).split(",")]
                if len(args) >= 6 and re.fullmatch(r"\d+", args[5]):
                    literals.append(f"{f.name}:{i} process_id={args[5]} is a bare literal")
                elif len(args) >= 6 and args[5].startswith("PROCESS_") and args[5] not in names:
                    literals.append(f"{f.name}:{i} process_id={args[5]} is not registered")
    assert not literals, (
        "process_id must be a registered alias:\n  " + "\n  ".join(literals)
    )


def test_kernels_declare_no_unused_parameters() -> None:
    """A parameter present in the defaults but read by no loop is a model term that does not exist.

    dirty_air_window and dirty_air_loss sat in default_contest_params for the whole build while
    appearing in no simulation loop, so the dirty-air penalty the plan specifies was simply absent while
    looking configured.
    """
    src = (KERNELS / "contest_strategy.mojo").read_text()
    aliases = re.findall(r"alias (P_[A-Z_]+): Int = \d+", src)
    assert aliases, "no P_* aliases found — the guard would pass vacuously"
    dead = []
    for name in aliases:
        # one reference is the alias, one is the assignment in default_contest_params
        if len(re.findall(rf"\b{name}\b", src)) <= 2:
            dead.append(name)
    assert not dead, (
        "declared but never read by any loop — the model term does not exist:\n  " + "\n  ".join(dead)
    )


def test_the_decision_outbox_reaches_no_database() -> None:
    """The outbox IS the boundary: the runtime appends, a separate shipper tails.

    The plan requires the decision runtime to hold no ClickHouse route, credentials or client at all --
    structurally, not by convention -- because ClickHouse stores corrected and final data and a decision
    path able to query it reintroduces look-ahead through the storage layer. So the module the runtime
    writes decisions through must not be able to reach one.
    """
    src = (ROOT / "scripts" / "timing" / "decision_outbox.py").read_text()
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    banned = {"clickhouse_connect", "clickhouse_driver", "sqlalchemy", "psycopg2", "psycopg",
              "requests", "httpx", "aiohttp", "urllib", "socket"}
    hit = imported & banned
    assert not hit, (
        f"decision_outbox imports {sorted(hit)}. It must be able to append to a local file and nothing "
        f"else; anything that can open a connection defeats the boundary."
    )


def test_the_outbox_chain_detects_an_edited_row(tmp_path) -> None:
    """A hash chain that does not actually catch a rewrite is theatre."""
    sys.path.insert(0, str(ROOT / "scripts" / "timing"))
    from decision_outbox import Outbox, verify

    path = tmp_path / "outbox.jsonl"
    ob = Outbox(path)
    for k in range(4):
        ob.append(session_key="1", decision_event_time=f"00:0{k}:00.000", event_watermark=k,
                  ingest_watermark=k, state_hash=f"{k:064d}", config_hash="c" * 64,
                  source_commit="abc", corpus_version="v1", rng_version="philox4x64-10/v1",
                  master_seed=1, theta_source="t", objective_version="o", target_car=1,
                  target_rival=2, laps_remaining=10 - k, replications=100, latency_ms=1.0,
                  p_ahead=[0.5, 0.4, 0.4, 0.4], delta=[0.0, -0.1, -0.1, -0.1],
                  ci_lo=[0.0, -0.2, -0.2, -0.2], ci_hi=[0.0, 0.0, 0.0, 0.0],
                  recommended=0, verdict=0, crn_variance_ratio=0.3)
    ok, head, problems = verify(path)
    assert ok, f"a freshly written chain must verify: {problems}"

    lines = path.read_text().splitlines()
    lines[1] = lines[1].replace('"p_ahead":[0.5', '"p_ahead":[0.9')
    path.write_text("\n".join(lines) + "\n")
    ok2, head2, problems2 = verify(path)
    assert not ok2, "an edited row verified clean — the chain is not checking content"
    assert head2 != head, "the head did not move after an edit, so a published head would not catch it"


@pytest.mark.parametrize("var,expected", [
    ("RUNTIME_FALLBACK_MODE", "deny"),
    ("MOJO_ALLOW_SUBPROCESS_FALLBACK", "false"),
])
def test_fallback_denial_is_the_documented_default(var: str, expected: str) -> None:
    """A Python fallback answering a kernel call returns plausible numbers and invalidates every claim."""
    spec = ROOT / "docs" / "timing" / "FROZEN_SPECS.md"
    plan_text = spec.read_text() if spec.exists() else ""
    build = (ROOT / "scripts" / "timing" / "build_filtered.sh").read_text()
    haystack = plan_text + build
    assert var in haystack, f"{var} is not pinned anywhere in the timing lane"
    assert expected in haystack, f"{var} must be pinned to {expected}"


def test_the_target_rival_rule_is_sticky_and_logs_every_substitution() -> None:
    """The frozen utility names a target rival; changing it silently changes the question.

    P(focal finishes ahead of the NAMED target rival) is only meaningful if the name holds. Re-selecting
    the nearest car ahead each lap makes the probability jump for a reason no operator can see, which
    reads as the model changing its mind. The spec allows exactly two substitutions -- the target retires,
    or the focal car passes it -- and requires both be logged.
    """
    sys.path.insert(0, str(ROOT / "scripts" / "timing"))
    from pitwall_tui import select_rival

    names = {1: "VER", 16: "LEC", 55: "SAI", 4: "NOR"}
    running = [{"car": 1}, {"car": 16}, {"car": 55}, {"car": 4}]   # focal at index 2 (car 55)
    states = {c: {"retired": 0} for c in names}

    # first call adopts the nearest car ahead
    locked, note, swap = select_rival(states, running, 2, None, names)
    assert locked == 16 and note is None and swap is None

    # STICKY: an unchanged order must not re-select, even though nearest is still 16
    again, note, swap = select_rival(states, running, 2, locked, names)
    assert again == 16 and note is None and swap is None, "the target moved without a reason"

    # the target RETIRES -> substitute, and say so
    retired = {**states, 16: {"retired": 1}}
    sub, note, swap = select_rival(retired, [{"car": 1}, {"car": 55}, {"car": 4}], 1, 16, names)
    assert sub == 1, f"expected fallback to the next car ahead, got {sub}"
    assert swap and swap["reason"] == "target retired"
    assert note and "retired" in note, "the substitution was performed silently"

    # the focal car PASSES the target -> substitute, and say so
    passed = [{"car": 1}, {"car": 55}, {"car": 16}, {"car": 4}]     # 55 now ahead of 16
    sub2, note2, swap2 = select_rival(states, passed, 1, 16, names)
    assert sub2 == 1, f"expected the new car ahead, got {sub2}"
    assert swap2 and swap2["reason"] == "target no longer ahead"
    assert note2 and "passed" in note2

    # a leading focal car has no rival at all, and must not invent one
    none_ahead, _n, _s = select_rival(states, running, 0, None, names)
    assert none_ahead is None
