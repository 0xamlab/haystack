#!/usr/bin/env python3
"""A-Z pipeline benchmark: codna extraction -> telys ingest -> instant recall.

The full loop the CI-side repo-aware selection and the agent's code memory run on:

  1. SNAPSHOT   copy the real source dirs into a clean temp repo (the working copy carries local
                scratch trees — codex-* clones, mojo envs, mcp_venv — that no CI checkout has).
  2. EXTRACT    codna codeunits.extract_repo — structural units, speed (files/s, units/s).
  3. INDEX-COLD CodeMemory.index() — extraction + on-device embedding + telys upsert, from zero.
  4. RECALL     representative queries — per-query latency and recall@k against ground truth
                derived from the extraction itself (no hardcoded repo facts).
  5. INDEX-WARM immediate re-index — the unchanged-content fast path (the CI shape: every push).
  6. INDEX-DELTA touch one file, re-index — only changed symbols re-embed.

Requires the codna checkout (imported via --codna-cli) and its telys runtime (the same one
``codna memory`` uses). Usage:

    python scripts/bench_codna_telys_a2z.py --root /Users/angel/Developer/decision-engine \
        --codna-cli /Users/angel/Developer/codna/cli
"""

from __future__ import annotations

import argparse
import random
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

# The real source of this repo — everything else in the working copy is local scratch.
_SNAPSHOT_DIRS = ("apps", "tests", "packages", "benchmarks", "scripts", "integrations")
_COPY_IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    "node_modules", "dist", "build", ".codna-memory",
)


def _snapshot(root: Path, dest: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name in _SNAPSHOT_DIRS:
        src = root / name
        if not src.is_dir():
            continue
        shutil.copytree(src, dest / name, ignore=_COPY_IGNORE, dirs_exist_ok=True)
        counts[name] = sum(1 for p in (dest / name).rglob("*") if p.is_file())
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description="A-Z codna+telys pipeline benchmark")
    ap.add_argument("--root", default="/Users/angel/Developer/decision-engine")
    ap.add_argument("--codna-cli", default="/Users/angel/Developer/codna/cli")
    ap.add_argument("--queries", type=int, default=20, help="ground-truth recall queries")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    # APPEND, not insert(0): codna's source checkout carries a vendored `memengine/` package next to
    # the `codna` package. sys.path.insert(0, cli) would let that STALE vendored runtime shadow the
    # installed telys-runtime-native (editable dev tree here), silently measuring the old engine.
    sys.path.append(str(Path(args.codna_cli).resolve()))
    from codna.codeunits import extract_repo  # noqa: E402
    from codna.memory import CodeMemory  # noqa: E402

    root = Path(args.root).resolve()
    work = Path(tempfile.mkdtemp(prefix="codna-a2z-"))
    repo = work / "repo"
    db = work / "telys-db"
    print(f"snapshot {root.name} -> {repo}")

    t0 = time.perf_counter()
    counts = _snapshot(root, repo)
    dt_snap = time.perf_counter() - t0
    total_files = sum(counts.values())
    print(f"  {total_files} files in {dt_snap:.2f}s  {counts}")

    # ---- 2. EXTRACT ----
    t0 = time.perf_counter()
    units, stats = extract_repo(str(repo), "a2z-bench")
    dt_ex = time.perf_counter() - t0
    print()
    print("== EXTRACT (codna) ==")
    print(f"  {stats.files} files -> {stats.units} units in {dt_ex:.2f}s "
          f"(skipped {stats.skipped})")
    if dt_ex > 0:
        print(f"  {stats.files / dt_ex:,.0f} files/s   {stats.units / dt_ex:,.0f} units/s")
    langs: dict[str, int] = {}
    for u in units:
        langs[u.language] = langs.get(u.language, 0) + 1
    print(f"  languages: {dict(sorted(langs.items(), key=lambda kv: -kv[1]))}")

    # ---- 3. INDEX-COLD (codna -> telys ingest + on-device embedding) ----
    t0 = time.perf_counter()
    mem = CodeMemory(str(repo), str(db))
    dt_ctor = time.perf_counter() - t0
    t0 = time.perf_counter()
    res = mem.index()
    dt_cold = time.perf_counter() - t0
    print()
    print("== INDEX-COLD (codna -> telys) ==")
    print(f"  engine construct: {dt_ctor:.2f}s")
    print(f"  {res}")
    print(f"  wall {dt_cold:.2f}s", end="")
    if res["indexed"] and dt_cold > 0:
        print(f"   ->   {res['indexed'] / dt_cold:,.0f} units embedded+upserted/s")
    else:
        print()

    # ---- 4. RECALL — ground truth from the extraction itself ----
    # Pick test units spread across distinct files; query by their distinctive qualname and check
    # the file comes back in the final-k. This measures retrieval quality with no hardcoded facts.
    rng = random.Random(args.seed)
    test_units = [u for u in units if u.symbol_type == "test" and len(u.qualname) > len("test_")]
    by_file: dict[str, list] = {}
    for u in test_units:
        by_file.setdefault(u.path, []).append(u)
    picked_files = rng.sample(sorted(by_file), min(args.queries, len(by_file)))
    probes = [(p, rng.choice(by_file[p])) for p in picked_files]

    latencies: list[float] = []
    hits_at_k = 0
    print()
    print(f"== RECALL ({len(probes)} ground-truth queries) ==")
    for path, unit in probes:
        t0 = time.perf_counter()
        out = mem.recall(unit.qualname, top_k=40, final_k=8)
        dt_q = time.perf_counter() - t0
        latencies.append(dt_q)
        got_paths = {s["path"] for s in out["symbols"]}
        hit = path in got_paths
        hits_at_k += int(hit)
        if not hit:
            print(f"  MISS  q={unit.qualname!r} expected={path} got={sorted(got_paths)[:3]}")
    recall_at_k = hits_at_k / len(probes) if probes else 0.0
    print(f"  recall@8: {hits_at_k}/{len(probes)} = {recall_at_k:.3f}")
    print(f"  latency:  min {min(latencies)*1000:.0f}ms  "
          f"median {statistics.median(latencies)*1000:.0f}ms  "
          f"max {max(latencies)*1000:.0f}ms")

    # ---- 5. INDEX-WARM (unchanged fast path — the every-push CI shape) ----
    t0 = time.perf_counter()
    res_warm = mem.index()
    dt_warm = time.perf_counter() - t0
    print()
    print("== INDEX-WARM (no changes) ==")
    print(f"  {res_warm}")
    print(f"  wall {dt_warm:.2f}s")

    # ---- 6. INDEX-DELTA (one file changed — add a NEW symbol so one unit actually re-embeds;
    # a comment-only edit would hash-identical on every existing unit and measure nothing) ----
    candidates = [repo / "tests" / "test_test_impact.py",
                  next(p for p in (repo / "packages").rglob("*.py"))]
    victim = next((p for p in candidates if p.exists()), None)
    if victim is not None:
        victim.write_text(victim.read_text() +
                          "\n\ndef a2z_bench_delta_marker():\n    return 'delta'\n")
        t0 = time.perf_counter()
        res_delta = mem.index()
        dt_delta = time.perf_counter() - t0
        print()
        print(f"== INDEX-DELTA (touched {victim.relative_to(repo)}) ==")
        print(f"  {res_delta}")
        print(f"  wall {dt_delta:.2f}s")

    print()
    print(f"workdir kept at {work} (rm -rf to clean up)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
