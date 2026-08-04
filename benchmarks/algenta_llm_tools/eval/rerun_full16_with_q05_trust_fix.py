#!/usr/bin/env python3
"""Full 16-question regression check for the q05 "trust the kernel result" fix.

The fix itself lives directly in ``run_benchmark.py``'s ``TOOLS_SUFFIX`` (one added
system-prompt sentence: don't recompute a value you already got from a kernel) and in
``tools.py``'s scoped, ``stats.compute_std``-only note in ``explain()``/``execute()``.
Both apply unconditionally inside ``run_benchmark.py`` itself -- there is nothing else
for this script to change. Its only job is to run the SAME full 16-question,
bare-and-tools benchmark ``run_benchmark.main()`` already runs, but write the result to
its own file instead of overwriting the original ``benchmark_results.json`` (the
pre-fix, pre-``compute_std``/``get_columns`` historical baseline: 14/16 tools-condition
passes), so both real runs stay on disk side by side -- see the README's "Closed gaps"
section for the full before/after history this preserves.

Live result actually observed (2026-08-04, gpt-5-mini, real API calls): 16/16
tools-condition correct (bare unaffected: 1/16, same as the original run -- this
question set's bare/no-tools condition never depended on any tool-facing text), no
regression on any of the other 15 questions. Full transcript in
``full16_with_q05_trust_fix_rerun_results.json``.

Run:
    ALGENTA_RUNTIME_FALLBACK_MODE=allow \
    ALGENTA_MOJO_BINARY=/Users/angel/Developer/decision-engine/mojo_build/simulate \
    PYTHONPATH=packages/algenta python3 -m \
        benchmarks.algenta_llm_tools.eval.rerun_full16_with_q05_trust_fix
"""

from __future__ import annotations

from benchmarks.algenta_llm_tools.eval import run_benchmark as rb

rb.RESULTS_PATH = rb.HERE / "full16_with_q05_trust_fix_rerun_results.json"

if __name__ == "__main__":
    rb.main()
