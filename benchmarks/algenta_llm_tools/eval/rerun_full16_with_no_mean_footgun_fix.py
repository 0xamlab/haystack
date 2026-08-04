#!/usr/bin/env python3
"""Full 16-question regression check for the "no `mean` parameter to guess" q05 fix.

The fix itself lives in three places: the real `stats.compute_std_from_values(v, n)`
kernel (mojo/engine/stats.mojo, computes its own mean internally so there is no `mean`
argument for a caller to guess), a new/extended `_FINAL_ANSWER_NOTES` entry in
`tools.py` (steering a caller without a real, kernel-computed mean toward it), and one
extended sentence in `run_benchmark.py`'s `TOOLS_SUFFIX` naming `compute_std_from_values`
as a visible module='stats' option alongside `compute_mean`/`compute_variance`. All three
apply unconditionally inside this same checkout -- there is nothing else for this script
to change. Its only job is to run the SAME full 16-question, bare-and-tools benchmark
`run_benchmark.main()` already runs, but write the result to its own file instead of
overwriting `benchmark_results.json` or `full16_with_q05_trust_fix_rerun_results.json`
(the prior fix's own full-16 rerun), so all three real runs stay on disk side by side.

Run:
    ALGENTA_RUNTIME_FALLBACK_MODE=allow \
    ALGENTA_MOJO_BINARY=/tmp/uplift-std-no-mean-kernel/mojo_build/simulate \
    PYTHONPATH=packages/algenta python3 -m \
        benchmarks.algenta_llm_tools.eval.rerun_full16_with_no_mean_footgun_fix
"""

from __future__ import annotations

from benchmarks.algenta_llm_tools.eval import run_benchmark as rb

rb.RESULTS_PATH = rb.HERE / "full16_with_no_mean_footgun_fix_rerun_results.json"

if __name__ == "__main__":
    rb.main()
