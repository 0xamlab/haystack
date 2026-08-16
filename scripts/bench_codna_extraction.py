#!/usr/bin/env python3
"""Benchmark: Codna multi-language extraction — speed + accuracy, on this repo.

Measures the two things that matter for repo-aware test selection and instant repo memory:
  * SPEED     — wall time, files/sec and structural-units/sec, per-language attribution
                (which grammar is the slow one?), python-only vs all-languages.
  * ACCURACY  — precision/recall of test-unit detection vs the ground-truth set of test files
                (files named test_*.py / *_test.py), plus the symbol-type and language mix.

Codna is imported from a local checkout (``--codna-cli <path>``). Tree-sitter grammars must be
installed for the non-Python languages; languages without a grammar are reported, not fatal.

Usage:
    python scripts/bench_codna_extraction.py --root /path/to/repo \
        --codna-cli /Users/angel/Developer/codna/cli
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Superset of codna's own _DEFAULT_IGNORE, matching scripts/test_impact.py's skips so the bench
# scope mirrors what a CI checkout contains: the local scratch trees (codex-* agent clones,
# mojo envs/builds, mcp_venv) exist only in this working copy and would inflate every number.
_IGNORE = (
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build", ".codna-memory",
    "mojo_env", "mma_forge", "mojo_build", "vendor", "mcp_venv",
    "codex-fly-fix-clone", "codex-oracle-connector", "codex-pr329-fix",
)


def _ground_truth_test_files(root: Path) -> set[str]:
    """Ground truth over the WHOLE repo: .py files named test_*.py or *_test.py."""
    out: set[str] = set()
    ignore = set(_IGNORE)
    for p in root.rglob("*.py"):
        rel = p.relative_to(root)
        if any(part in ignore or part.startswith(".") for part in rel.parts):
            continue
        if p.name.startswith("test_") or p.name.endswith("_test.py"):
            out.add(str(rel))
    return out


def _load_codna(cli_path: str):
    sys.path.insert(0, str(Path(cli_path).resolve()))
    from codna import codeunits  # noqa: E402
    return codeunits


def main() -> int:
    ap = argparse.ArgumentParser(description="Benchmark codna extraction speed + accuracy")
    ap.add_argument("--root", default=".", help="repo root to extract")
    ap.add_argument("--codna-cli", default="/Users/angel/Developer/codna/cli",
                    help="path to a codna checkout's cli/ dir")
    ap.add_argument("--repo-id", default="bench", help="repo_id for codna units")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    codeunits = _load_codna(args.codna_cli)
    langs = codeunits.registered_languages()
    print(f"root={root}")
    print(f"codna registered languages ({len(langs)}): {', '.join(langs)}")

    truth = _ground_truth_test_files(root)
    print(f"ground-truth test files (whole repo): {len(truth)}")
    print()

    # ---- SPEED, per-language attribution (each pass re-walks the tree; walk cost is negligible
    # vs parse cost, and this is the only way to blame slowness on a specific grammar) ----
    print("== SPEED (per-language passes) ==")
    per_lang: dict[str, tuple[float, object]] = {}
    for lang in langs:
        t0 = time.perf_counter()
        units, stats = codeunits.extract_repo(str(root), args.repo_id,
                                              languages=(lang,), ignore=_IGNORE)
        dt = time.perf_counter() - t0
        per_lang[lang] = (dt, stats)
        rate = f"{stats.units / dt:,.0f} u/s" if dt > 0 and stats.units else "-"
        print(f"  {lang:<12} {dt:7.2f}s  files={stats.files:5d}  units={stats.units:6d}  "
              f"skipped={stats.skipped:3d}  {rate}")

    # ---- SPEED, single all-languages pass (the real end-to-end shape) ----
    t0 = time.perf_counter()
    units, stats = codeunits.extract_repo(str(root), args.repo_id, languages=None,
                                          ignore=_IGNORE)
    dt_all = time.perf_counter() - t0
    print()
    print("== SPEED (all-languages single pass) ==")
    print(f"  {stats.files} files -> {stats.units} units in {dt_all:.2f}s "
          f"(skipped/unparseable: {stats.skipped})")
    if dt_all > 0:
        print(f"  {stats.files / dt_all:,.0f} files/sec   {stats.units / dt_all:,.0f} units/sec")
    sum_single = sum(dt for dt, _ in per_lang.values())
    print(f"  (sum of per-language passes: {sum_single:.2f}s — overhead of N extra walks)")

    # ---- ACCURACY: test-unit detection ----
    detected: set[str] = set()
    lang_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for u in units:
        lang_counts[u.language] = lang_counts.get(u.language, 0) + 1
        type_counts[u.symbol_type] = type_counts.get(u.symbol_type, 0) + 1
        if u.symbol_type == "test":
            detected.add(u.path)

    print()
    print("== ACCURACY (test-unit detection vs filename ground truth) ==")
    tp = len(detected & truth)
    fp = len(detected - truth)
    fn = len(truth - detected)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    print(f"  detected files with >=1 test unit: {len(detected)}   (truth: {len(truth)})")
    print(f"  TP={tp}  FP={fp}  FN={fn}")
    print(f"  precision={precision:.3f}   recall={recall:.3f}")
    if fn:
        print(f"  missed (FN) sample: {sorted(truth - detected)[:5]}")
    if fp:
        print(f"  extra (FP) sample:  {sorted(detected - truth)[:5]}")
    print()
    print("  units by language:   ", dict(sorted(lang_counts.items(), key=lambda kv: -kv[1])))
    print("  units by symbol_type:", dict(sorted(type_counts.items(), key=lambda kv: -kv[1])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
