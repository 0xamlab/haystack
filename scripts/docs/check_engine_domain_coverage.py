#!/usr/bin/env python3
"""A6 (scoped): narrative engine-domain documentation ⇄ real runtime module reconciliation.

WHAT THIS IS NOT. `check_docs_coverage.py`'s existing `runtime_library_modules` category already
asserts every one of the 643 real modules appears SOMEWHERE in the gitbook corpus -- but that
check is trivially satisfied by `gitbook/engine/runtime-library-catalog.md` alone, since that page
is machine-generated FROM the same contract and by construction lists every module's name next to
its function count. It proves a module has an INDEX ROW. It says nothing about whether anyone
explains what the module is for, and measured directly: as of the A6 batch-2 pass (2026-08-29,
16 family pages covering 68 modules across ml classical algorithms, tensorx, text processing,
vector ranking, compression, forecasting ensembling, llmk, metaldispatch, mlpk, accel, esrnn,
gemm, normk, optmodel, progexec, and the sheet formula plane), 162 of 643 real modules (25%) were
referenced by a genuine NARRATIVE page (a page someone wrote prose on, as opposed to the
auto-generated catalog/index pages) -- 481 modules still existed in the runtime with zero
narrative documentation beyond that one generated table row (down from 549 immediately before
that batch). The A6 batch-3 pass (2026-08-29, a table-formatting cleanup, not new content) then
closed the table-row gap for 37 modules that were already discussed in prose on their page but
had never been given a formal "Module" table row -- across 20 pages spanning hmm, tensor2d, pls,
svm_solver, feature_hashing, imbalance, linear_models, model_selection, mixture_models, conformal,
gaussian_process, explainability, ensembles, voting, arima, timeseries_stats, automl, eigen_full,
gbdt, model_compare, seq_nn, seq_training, serialization_io, option_greeks_batch, option_pricing,
pipelines, propensity, vector_search, forecast_metrics, ml_metrics_extended, degradation_state,
contest_strategy, evolutionary_search, genetic, game_theory, quantization, and quantization_stack
-- bringing the count to 199 of 643 real modules (31%), with 444 modules still undocumented by
narrative beyond their generated table row.

WHY THIS SCRIPT DOES NOT GATE ON THE 481 GAP. That gap is a documentation-writing backlog, not a
regression -- something a CI check can flag but cannot itself close, and gating hard on it would
either block every unrelated PR immediately or get disabled at the first annoyance (the same trap
`scripts/reliability_guards`' `baselined=True` ratchet exists to avoid for code guards). This
script instead:
  1. Verifies every module a narrative page CLAIMS to document is a REAL module in
     runtime_library_contract.json -- a hard, zero-tolerance check. A page referencing a
     renamed/removed module is a stale-docs regression, not a backlog item, and is caught
     immediately.
  2. Reports the narrative-documented module count against a floor -- so the documented set
     cannot silently SHRINK (a narrative page's module table quietly losing rows) even though
     growing it is out of this script's scope.
  3. Prints the honest gap (444 modules, as of writing) rather than hiding it inside a passing
     check -- `--json` includes it explicitly under "undocumented_by_narrative".

WHY THE MATCHING RULE IS "first cell of a table headed exactly 'Module', not any backtick token
anywhere". The convention every multi-module family page in this corpus actually uses (verified
across 15 tables in 14 pages) is a markdown table whose header row's first column is literally
"Module" and whose data rows carry the module's exact name, backticked, as that first cell, e.g.:

    | Module | What it does |
    | --- | --- |
    | `optimization.linear` | linear programs — optimum, duals, reduced costs, ... |

Both restrictions are load-bearing, not stylistic:
  - "table headed 'Module'" excludes every OTHER real table shape this corpus also uses --
    `| Entry point | Use when | Cost |` (coarse-execution.md), `| Status | Name | What it means |`
    (evaluation-calibration.md, survival-analysis.md, strategy-simulation.md, geospatial.md,
    forecasting.md), `| Verb | What it answers |` / `| Backend | ... |` (retrieval.md) -- all of
    which legitimately backtick-quote lowercase, underscore/dot-shaped tokens (error-code names,
    entry-point names, verbs) that are NOT module claims and would otherwise misfire as "stale
    references" the moment they share a page with one real module-table hit.
  - "first cell only" excludes a description column backtick-quoting a related, non-module
    identifier -- e.g. `crypto.crc32`'s own description column names `crc32_combine`, a function
    in that module, not a second module -- which a whole-row scan would wrongly count as a claim.

KNOWN UNDERCOUNT, NOT OVERCOUNT. Many single-module pages (the `ml-*.md` family, among others)
name their one subject module in backticks in the page's opening prose instead of a "Module"
table -- a real, valid convention this script does not yet parse, so those modules are NOT
credited toward `narrative_documented_count` even though the page genuinely documents them. That
is a deliberate scope cut, not an oversight: a prose-position heuristic ("the first backtick span
after the H1") was tried against several such pages and does not hold uniformly -- some open with
a function signature (`coarse-execution.md`: `` execute(module, function, args) ``, not a bare
module name) or with no backtick at all (`streaming-windows.md`, `retrieval.md`), and at least one
counter-example (`ml-hmm.md`) backtick-quotes a DIFFERENT real module in its own opening
comparison sentence before naming its actual subject -- a naive "first backtick token" rule would
have credited the wrong module. Undercounting is the safe direction for a floor-based ratchet (it
can only make `narrative_documented_count` an understatement of the true total, never an
overstatement that hides a real regression), so this is left as a follow-up rather than shipping
a fragile heuristic under time pressure.

Usage:  python3 scripts/docs/check_engine_domain_coverage.py [--json]
Exit 0 = no stale references and documented count at or above the floor; 1 = otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GITBOOK_ENGINE = ROOT / "gitbook" / "engine"
CONTRACT = ROOT / "packages" / "algenta" / "algenta" / "runtime_library_contract.json"

# Auto-generated or pure-index pages: by construction they reference some/all real modules without
# any of it being narrative documentation. Excluding them is what makes "narrative" mean something.
NON_NARRATIVE_PAGES = frozenset(
    {
        "runtime-library-catalog.md",  # generated 1:1 from the contract by gen_runtime_library_reference.py
        "kernel-inventory.md",  # generated inventory, same shape
        "catalog.md",  # hand-written but an index-of-pages, not a domain explanation
        "runtime-libraries.md",  # overview/index of the runtime-libraries surface itself
        "capabilities.md",  # "declared capabilities" meta page
        "bundled-runtime.md",  # how to verify the bundled engine — infra, not a domain
        "health.md",  # engine health check — infra
        "gpu-support.md",  # GPU support matrix — infra/reference, not a kernel domain
        "model-support-matrix.md",  # LLM model support reference, not a kernel domain
    }
)

# Below this, something broke the extraction itself (a page lost its module table, or the contract
# shrank unexpectedly) rather than the backlog merely staying constant. Not a target to defend --
# raise it when a new page's table lands; a real regression is not the way to close the gap to it.
# Set from the actual measured count under the precise "Module table, first cell only" rule (199,
# see the module docstring's KNOWN UNDERCOUNT note) with a small margin, after the A6 batch-3 pass
# closed the table-row gap for 37 already-prose-documented modules (a formatting fix, not new
# content) on top of the prior floor of 160.
DOCUMENTED_FLOOR = 197


def real_modules() -> set[str]:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    return {module["name"] for module in payload["modules"]}


def narrative_pages() -> list[Path]:
    return sorted(p for p in GITBOOK_ENGINE.glob("*.md") if p.name not in NON_NARRATIVE_PAGES)


# A module identifier is lowercase, optionally dotted (`optimization.linear`, `column_rank`).
# Matches the real naming convention in runtime_library_contract.json's `name` field.
_MODULE_LIKE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")

_MODULE_TABLE_HEADER = re.compile(r"^\|\s*module\s*\|", re.IGNORECASE)
_TABLE_SEPARATOR_ROW = re.compile(r"^\|[\s:|-]+\|?$", re.IGNORECASE)


def _module_table_first_cells(text: str) -> set[str]:
    """Backtick-quoted module names claimed by a "Module | ..." table's data rows.

    See the module docstring for why this is restricted to (a) tables headed exactly "Module"
    and (b) each row's first cell only.
    """
    tokens: set[str] = set()
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if _MODULE_TABLE_HEADER.match(lines[i].strip()) and i + 1 < len(lines) and _TABLE_SEPARATOR_ROW.match(
            lines[i + 1].strip()
        ):
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                cells = lines[j].split("|")
                if len(cells) > 1:
                    match = re.search(r"`([^`]+)`", cells[1])
                    if match and _MODULE_LIKE.match(match.group(1)):
                        tokens.add(match.group(1))
                j += 1
            i = j
            continue
        i += 1
    return tokens


def check() -> dict[str, object]:
    real = real_modules()
    stale_by_page: dict[str, list[str]] = {}
    documented: set[str] = set()

    for page in narrative_pages():
        tokens = _module_table_first_cells(page.read_text(encoding="utf-8"))
        # Only tokens shaped like a module AND actually claimed against a real one are informative;
        # a page's table can legitimately reference other things (error codes, function names) that
        # also happen to be lowercase-dotted-shaped, so "stale" here means "shaped like a module,
        # not a real one, AND at least one other real module appears on the same page" -- a page
        # with zero real-module hits at all is simply not a module-reference table, not evidence of
        # staleness on its own.
        page_real_hits = tokens & real
        if not page_real_hits:
            continue
        documented |= page_real_hits
        stale = sorted(tokens - real)
        if stale:
            stale_by_page[str(page.relative_to(ROOT))] = stale

    undocumented = sorted(real - documented)
    result = {
        "real_module_count": len(real),
        "narrative_documented_count": len(documented),
        "documented_floor": DOCUMENTED_FLOOR,
        "undocumented_by_narrative": undocumented,
        "stale_references": stale_by_page,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="dump the full result as JSON")
    args = parser.parse_args()

    result = check()
    ok = not result["stale_references"] and result["narrative_documented_count"] >= DOCUMENTED_FLOOR

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"engine domain coverage: {result['narrative_documented_count']}/"
            f"{result['real_module_count']} real modules have narrative documentation "
            f"(floor {DOCUMENTED_FLOOR})"
        )
        if result["stale_references"]:
            print("STALE MODULE REFERENCES (page claims a module that no longer exists):")
            for page, names in sorted(result["stale_references"].items()):
                print(f"  {page}: {', '.join(names)}")
        if not ok and not result["stale_references"]:
            print(
                f"::error::narrative-documented module count {result['narrative_documented_count']} "
                f"fell below the floor of {DOCUMENTED_FLOOR}"
            )
        undoc = len(result["undocumented_by_narrative"])
        print(
            f"({undoc} real modules have no narrative page -- a documentation backlog, "
            "not a regression; not gated on here)"
        )

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
