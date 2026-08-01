#!/usr/bin/env python3
"""Corpus-scale self-validation: recalc every formula cell of every workbook
and compare against Excel's cached values, via the compiled Mojo binary.

Per workbook: extract (Python stdlib, staged reader) -> sheet_validate
(compiled Mojo, the actual engine) -> parse the key/value report. Aggregates
per corpus and overall; every non-comparable cell lands in a NAMED bucket
(unsupported-by-function, volatile, no-cached-value, cycles, budget), so
    matched_exact + matched_tol + error_matched + mismatched +
    error_mismatched + unsupported + volatile + cycle + no_cached +
    unsupported_compare + not_evaluated == formula_cells
holds per workbook and is asserted here.

Usage:
    validate_corpus.py --binary build/sheet_validate \
        [--corpus name=/path ...] [--limit N] [--jobs 8] --out report.json
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import subprocess
import sys
import tempfile
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_CORPORA = {  # noqa: S108 — documentation defaults; pass --corpus for real runs
    "spreadsheetbench_912": "/tmp/bb/corpora/SpreadsheetBench/data/all_data_912_v0.1",  # noqa: S108
    "spreadsheetbench_v2": "/tmp/bb/corpora/sbv2/spreadsheetbench-v2",  # noqa: S108
    "finch": "/tmp/bb/corpora/finch",  # noqa: S108
    "bluefin": "/tmp/bb/corpora/bluefin",  # noqa: S108
}

INT_KEYS = [
    "status",
    "load_line",
    "sheets",
    "cells",
    "formula_cells",
    "evaluated",
    "not_evaluated",
    "no_cached",
    "matched_exact",
    "matched_tol",
    "matched_snap",
    "error_matched",
    "mismatched",
    "error_mismatched",
    "unsupported",
    "volatile_cells",
    "cycle_cells",
    "cycle_count",
    "unsupported_compare",
    "ops",
    "max_chain",
]

_BINARY = None
_BUDGET = None


def unesc(s: str) -> str:
    return s.replace("%09", "\t").replace("%0A", "\n").replace("%0D", "\r").replace("%25", "%")


def one(path: str) -> dict:
    r: dict = {"path": path, "ok": False, "error": None}
    with tempfile.NamedTemporaryFile(suffix=".swt", delete=False) as tf:
        swt = tf.name
    try:
        ex = subprocess.run(  # noqa: S603 — fixed local extractor, no shell
            [sys.executable, "-P", os.path.join(HERE, "extract_xlsx.py"), path, swt],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if ex.returncode != 0:
            r["error"] = f"extract: {ex.stderr.strip()[:300]}"
            return r
        cmd = [_BINARY, swt]
        if _BUDGET:
            cmd.append(str(_BUDGET))
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # noqa: S603 — the compiled validator binary
        if run.returncode != 0:
            r["error"] = f"validate: rc={run.returncode} {run.stderr.strip()[:300]}"
            return r
        rep: dict = {}
        for line in run.stdout.splitlines():
            if "\t" not in line:
                continue
            k, _, v = line.partition("\t")
            rep[k] = int(v) if k in INT_KEYS else unesc(v)
        if rep.get("status") not in (1320, 1321):
            r["error"] = f"engine-refused: status={rep.get('status')} line={rep.get('load_line')}"
            return r
        # bucket accounting must close exactly — a cell that vanishes from
        # every bucket would be a silent skip, which is the one dishonesty
        # this harness exists to prevent
        total = sum(
            rep.get(k, 0)
            for k in (
                "matched_exact",
                "matched_tol",
                "matched_snap",
                "error_matched",
                "mismatched",
                "error_mismatched",
                "unsupported",
                "volatile_cells",
                "cycle_cells",
                "no_cached",
                "unsupported_compare",
                "not_evaluated",
            )
        )
        if total != rep.get("formula_cells", -1):
            r["error"] = f"bucket-leak: buckets={total} formula_cells={rep.get('formula_cells')}"
            return r
        r.update(rep)
        r["ok"] = True
        return r
    except subprocess.TimeoutExpired:
        r["error"] = "timeout"
        return r
    except Exception as exc:
        r["error"] = f"{type(exc).__name__}: {exc}"
        return r
    finally:
        try:
            os.unlink(swt)
        except OSError:
            pass


def _init(binary: str, budget: int) -> None:
    global _BINARY, _BUDGET
    _BINARY = binary
    _BUDGET = budget


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", required=True)
    ap.add_argument("--corpus", action="append", default=[])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--budget", type=int, default=0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    corpora = {}
    for spec in args.corpus or []:
        name, _, root = spec.partition("=")
        corpora[name] = root
    if not corpora:
        corpora = DEFAULT_CORPORA

    binary = os.path.abspath(args.binary)
    out = {"per_corpus": {}, "overall": {}}
    overall = Counter()
    overall_unsup = Counter()
    overall_files = {"workbooks": 0, "failed": 0}
    failures: list[dict] = []
    sample_mismatches: list[str] = []
    sample_cycles: list[str] = []

    for name, root in corpora.items():
        files = []
        for dirpath, _, fnames in os.walk(root):
            for fn in fnames:
                if fn.endswith(".xlsx") and not fn.startswith("~$"):
                    files.append(os.path.join(dirpath, fn))
        files.sort()
        if args.limit:
            files = files[: args.limit]
        agg = Counter()
        unsup = Counter()
        nfail = 0
        with mp.Pool(args.jobs, initializer=_init, initargs=(binary, args.budget)) as pool:
            for r in pool.imap_unordered(one, files, chunksize=4):
                if not r["ok"]:
                    nfail += 1
                    if len(failures) < 200:
                        failures.append({"path": r["path"], "error": r["error"]})
                    continue
                for k in INT_KEYS:
                    if k in ("status", "load_line"):
                        continue
                    agg[k] += r.get(k, 0)
                agg["budget_stopped"] += 1 if r.get("status") == 1321 else 0
                for pair in (r.get("unsupported_names") or "").split(","):
                    if ":" in pair:
                        nm, _, cnt = pair.rpartition(":")
                        try:
                            unsup[nm] += int(cnt)
                        except ValueError:
                            pass
                if r.get("mismatch_samples") and len(sample_mismatches) < 100:
                    sample_mismatches.append(
                        f"[{os.path.relpath(r['path'], root)}] {r['mismatch_samples'][:600]}"
                    )
                if r.get("cycle_names") and len(sample_cycles) < 40:
                    sample_cycles.append(
                        f"[{os.path.relpath(r['path'], root)}] {r['cycle_names'][:400]}"
                    )
        overall.update(agg)
        overall_unsup.update(unsup)
        overall_files["workbooks"] += len(files)
        overall_files["failed"] += nfail
        out["per_corpus"][name] = _summary(agg, unsup, len(files), nfail)
        print(f"[{name}] {_oneline(out['per_corpus'][name])}", file=sys.stderr)

    out["overall"] = _summary(
        overall, overall_unsup, overall_files["workbooks"], overall_files["failed"]
    )
    out["failures"] = failures
    out["sample_mismatches"] = sample_mismatches
    out["sample_cycles"] = sample_cycles
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"[overall] {_oneline(out['overall'])}", file=sys.stderr)
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


def _summary(agg: Counter, unsup: Counter, workbooks: int, failed: int) -> dict:
    comparable = (
        agg["matched_exact"]
        + agg["matched_tol"]
        + agg["matched_snap"]
        + agg["error_matched"]
        + agg["mismatched"]
        + agg["error_mismatched"]
    )
    matched = agg["matched_exact"] + agg["matched_tol"] + agg["matched_snap"] + agg["error_matched"]
    d = {
        "workbooks": workbooks,
        "failed_workbooks": failed,
        **{k: agg[k] for k in INT_KEYS if k not in ("status", "load_line")},
        "budget_stopped": agg["budget_stopped"],
        "comparable": comparable,
        "matched": matched,
        "match_rate_of_comparable": round(matched / comparable * 100, 4) if comparable else None,
        "match_rate_of_all_formulas": round(matched / agg["formula_cells"] * 100, 4)
        if agg["formula_cells"]
        else None,
        "unsupported_by_function": dict(unsup.most_common()),
    }
    return d


def _oneline(s: dict) -> str:
    return (
        f"{s['workbooks']} wb ({s['failed_workbooks']} failed) "
        f"formulas={s['formula_cells']:,} exact={s['matched_exact']:,} "
        f"tol={s['matched_tol']:,} snap={s['matched_snap']:,} err_ok={s['error_matched']:,} "
        f"mm={s['mismatched'] + s['error_mismatched']:,} "
        f"unsup={s['unsupported']:,} vol={s['volatile_cells']:,} "
        f"cyc={s['cycle_cells']:,} nocache={s['no_cached']:,} "
        f"match%comparable={s['match_rate_of_comparable']}"
    )


if __name__ == "__main__":
    sys.exit(main())
