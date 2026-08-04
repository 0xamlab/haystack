#!/usr/bin/env python3
"""Live re-verification of the q05-only "trust the kernel result" intervention.

A prior diagnosis pass could not find any real transcript (in benchmark_results.json,
final_two_gaps_rerun_results.json, or any sibling uplift-fix branch's copies of them)
showing the specific failure mode this was meant to close -- a run that calls
``stats.compute_std``, gets the exact right answer, and then *overrides* it by also
calling ``compute_variance`` and taking the square root itself. The one real post-fix
q05 transcript that exists used ``compute_std`` alone and passed. So this script exists
to test the intervention against real sampling variance directly, not to reproduce a
transcript that was never observed: does adding (1) an explicit "trust the tool result,
don't re-derive it" sentence to the tools system prompt and (2) a scoped, compute_std-only
"this IS the final answer" note in ``explain()``/``execute()`` change anything real,
across N independent fresh-conversation reps of q05 alone?

Every rep is a brand-new ``messages`` list (a fresh conversation) with the SAME
now-changed system prompt (imported from run_benchmark.py -- this file adds no prompt
text on its own; the actual wording lives there so run_benchmark.py's full 16-question
run and this q05-only rerun can never drift apart). TOOLS condition only; q05's bare-LLM
answer is unaffected by this change and already exists in benchmark_results.json.

Run:
    ALGENTA_RUNTIME_FALLBACK_MODE=allow \
    ALGENTA_MOJO_BINARY=/tmp/uplift-q05-fix/mojo_build/simulate \
    PYTHONPATH=packages/algenta python3 -m \
        benchmarks.algenta_llm_tools.eval.rerun_q05_prompt_trust_fix
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
N_REPS = 5
RESULTS_PATH = HERE / "q05_prompt_trust_fix_rerun_results.json"
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
        calls_compute_variance = any(
            tc["tool"] == "execute"
            and isinstance(tc.get("args"), dict)
            and tc["args"].get("function") == "compute_variance"
            for tc in tooled["tool_calls"]
        )
        calls_compute_std = any(
            tc["tool"] == "execute"
            and isinstance(tc.get("args"), dict)
            and tc["args"].get("function") == "compute_std"
            for tc in tooled["tool_calls"]
        )
        print(
            f"  rep {rep}: correct={ok} ({detail}) "
            f"compute_std_called={calls_compute_std} "
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
                "compute_std_called": calls_compute_std,
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
    print("\n=== SUMMARY (q05 prompt-trust-fix rerun, 5 reps, tools-only) ===")
    print(json.dumps(summary, indent=2))

    RESULTS_PATH.write_text(json.dumps({"summary": summary, "reps": reps}, indent=2, default=str))
    print(f"\nfull results written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
