#!/usr/bin/env python3
"""Live re-verification of the "no `mean` parameter to guess" fix for q05.

Root cause (see WIRE-AND-BUILD report on branch fix/uplift-std-no-mean-footgun and
mojo/engine/stats.mojo's compute_std_from_values docstring): in the TOOLS condition, a
model asked for UNIT_PRICE's sample std dev called get_column('UNIT_PRICE', dropna=True)
(which previews only 20 of 29,204 values, per the earlier preview-size fix), then --
WITHOUT ever calling execute(stats.compute_mean, ...) -- estimated a mean by eye from that
20-value preview and fed the wrong guess straight into execute(stats.compute_std, {'mean':
<guess>, ...}). The kernel computed exactly what it was asked, correctly, on a wrong input,
so the final answer was confidently wrong even though `compute_std` itself is correct and
was "trusted" per the earlier q05 fix (see rerun_q05_prompt_trust_fix.py / README.md's
"q05 follow-up" section) -- this is a DIFFERENT failure mode from that one, not a repeat of
it: the model isn't discarding a correct tool result, it's feeding a correct kernel a wrong
input.

Fix under test here: (1) a new kernel, `stats.compute_std_from_values(v, n)`, that computes
the mean internally so there is no `mean` slot for a guess to occupy, (2) a
`_FINAL_ANSWER_NOTES` entry for it (and an added sentence on `compute_std`'s existing note)
steering a caller without a real, kernel-computed mean in hand toward it, and (3) a
`TOOLS_SUFFIX` system-prompt sentence naming `compute_std_from_values` explicitly as a
sample module='stats' function alongside `compute_mean`/`compute_variance`, so the model's
own system prompt surfaces this simpler path as a visible option.

Every rep is a brand-new ``messages`` list (a fresh conversation) with the SAME
now-changed system prompt (imported from run_benchmark.py -- this file adds no prompt text
of its own; the actual wording lives there so run_benchmark.py's full 16-question run and
this q05-only rerun can never drift apart). TOOLS condition only; q05's bare-LLM answer is
unaffected by this change and already exists in benchmark_results.json.

Run:
    ALGENTA_RUNTIME_FALLBACK_MODE=allow \
    ALGENTA_MOJO_BINARY=/tmp/uplift-std-no-mean-kernel/mojo_build/simulate \
    PYTHONPATH=packages/algenta python3 -m \
        benchmarks.algenta_llm_tools.eval.rerun_q05_no_mean_footgun
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path("/Users/angel/Developer/decision-engine/.env"), override=False)

from openai import OpenAI  # noqa: E402

from benchmarks.algenta_llm_tools import tools  # noqa: E402
from benchmarks.algenta_llm_tools.eval import run_benchmark as rb  # noqa: E402

Q05_ID = "q05_std_unit_price"
N_REPS = 8
RESULTS_PATH = HERE / "q05_no_mean_footgun_rerun_results.json"
BUDGET_CAP_USD = 2.0


def main() -> None:
    if not rb.CSV_PATH.exists():
        raise SystemExit(f"missing fixture: {rb.CSV_PATH}")
    tools.configure_dataset(str(rb.CSV_PATH))
    client = OpenAI()

    all_questions = rb._load_questions()
    matches = [q for q in all_questions if q["id"] == Q05_ID]
    if len(matches) != 1:
        raise SystemExit(f"expected exactly one question with id {Q05_ID!r}, got {len(matches)}")
    q05 = matches[0]

    shared_total = [0.0]
    tracker = rb.CostTracker(BUDGET_CAP_USD, shared_total)

    reps = []
    for rep in range(1, N_REPS + 1):
        print(f"=== rep {rep}/{N_REPS} ===", flush=True)
        t0 = time.time()
        try:
            tooled = rb.run_with_tools(client, q05, tracker)
        except rb.BudgetExceededError as exc:
            print(f"BUDGET CAP HIT on rep {rep}: {exc}")
            break
        ok, detail = rb.score(q05, tooled["answer"])

        def _called(function_name: str) -> bool:
            return any(
                tc["tool"] == "execute"
                and isinstance(tc.get("args"), dict)
                and tc["args"].get("function") == function_name
                for tc in tooled["tool_calls"]
            )

        calls_compute_mean = _called("compute_mean")
        calls_compute_variance = _called("compute_variance")
        calls_compute_std = _called("compute_std")
        calls_compute_std_from_values = _called("compute_std_from_values")
        print(
            f"  rep {rep}: correct={ok} ({detail}) "
            f"compute_std_from_values_called={calls_compute_std_from_values} "
            f"compute_std_called={calls_compute_std} "
            f"compute_mean_called={calls_compute_mean} "
            f"compute_variance_called={calls_compute_variance} "
            f"turns={tooled.get('turns')} tool_calls={len(tooled['tool_calls'])} "
            f"[{time.time() - t0:.1f}s]"
        )
        for tc in tooled["tool_calls"]:
            print(f"    call: {tc['tool']}({tc.get('args')})")
        reps.append(
            {
                "rep": rep,
                "correct": ok,
                "detail": detail,
                "compute_std_from_values_called": calls_compute_std_from_values,
                "compute_std_called": calls_compute_std,
                "compute_mean_called": calls_compute_mean,
                "compute_variance_called": calls_compute_variance,
                "tools": tooled,
            }
        )
        print(f"  running cost: ${tracker.total:.4f}", flush=True)

    n = len(reps)
    n_pass = sum(1 for r in reps if r["correct"])
    summary = {
        "model": rb.MODEL,
        "question_id": Q05_ID,
        "n_reps": n,
        "n_pass": n_pass,
        "cost_usd": round(tracker.total, 6),
        "prompt_tokens": tracker.prompt_tokens,
        "completion_tokens": tracker.completion_tokens,
        "api_calls": tracker.calls,
    }
    print(f"\n=== SUMMARY (q05 no-mean-footgun rerun, {N_REPS} reps, tools-only) ===")
    print(json.dumps(summary, indent=2))

    RESULTS_PATH.write_text(json.dumps({"summary": summary, "reps": reps}, indent=2, default=str))
    print(f"\nfull results written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
