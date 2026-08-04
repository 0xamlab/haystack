#!/usr/bin/env python3
"""Re-run the TOOLS condition only, for the 4 questions that missed in the original
uplift benchmark run, against the now-improved tool harness (pearson_r_strict/
spearman_r_strict + group_by_aggregate). Bare-LLM answers are NOT re-run -- they
don't depend on the tool harness and are already recorded in benchmark_results.json.

Same model, same live-checked pricing, same scoring rules, same system prompt
structure as the original run.py -- this file imports run_benchmark's own
functions/constants directly rather than re-implementing them, so there is no
chance of a re-run using different scoring/prompt logic than the original by
accident.

Run:
    ALGENTA_RUNTIME_FALLBACK_MODE=allow \
    ALGENTA_MOJO_BINARY=/tmp/uplift-gap-fixes/mojo_build/simulate \
    PYTHONPATH=packages/algenta python3 -m benchmarks.algenta_llm_tools.eval.rerun_gap_questions
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

GAP_QIDS = {
    "q05_std_unit_price",
    "q14_top_cust_type_by_avg_unit_price",
    "q15_top_status_by_avg_ext_price",
    "q16_corr_unit_price_quantity",
}

RESULTS_PATH = HERE / "gap_rerun_results.json"
BUDGET_CAP_USD = 5.0


def main() -> None:
    if not rb.CSV_PATH.exists():
        raise SystemExit(f"missing fixture: {rb.CSV_PATH}")
    tools.configure_dataset(str(rb.CSV_PATH))
    client = OpenAI()

    all_questions = rb._load_questions()
    questions = [q for q in all_questions if q["id"] in GAP_QIDS]
    if len(questions) != len(GAP_QIDS):
        found = {q["id"] for q in questions}
        raise SystemExit(f"missing question ids: {GAP_QIDS - found}")

    shared_total = [0.0]
    tools_tracker = rb.CostTracker(BUDGET_CAP_USD, shared_total)

    results = []
    for q in questions:
        qid = q["id"]
        print(f"=== {qid} ===", flush=True)
        t1 = time.time()
        try:
            tooled = rb.run_with_tools(client, q, tools_tracker)
        except rb.BudgetExceededError as exc:
            print(f"BUDGET CAP HIT during tools condition: {exc}")
            break
        tool_ok, tool_detail = rb.score(q, tooled["answer"])
        print(
            f"  tools ({tooled.get('turns')} turns, "
            f"{len(tooled['tool_calls'])} tool calls): {tooled['answer']} correct={tool_ok} "
            f"({tool_detail}) [{time.time()-t1:.1f}s]"
        )
        results.append(
            {
                "id": qid,
                "question": q["question"],
                "ground_truth": q["ground_truth"],
                "scoring": q["scoring"],
                "tools": {**tooled, "correct": tool_ok, "detail": tool_detail},
            }
        )
        print(f"  running cost: tools=${tools_tracker.total:.4f}", flush=True)

    n = len(results)
    tool_pass = sum(1 for r in results if r["tools"]["correct"])
    summary = {
        "model": rb.MODEL,
        "pricing_per_1m": rb.PRICING[rb.MODEL],
        "n_questions": n,
        "tools_pass": tool_pass,
        "tools_cost_usd": round(tools_tracker.total, 6),
        "tools_tokens": {
            "prompt": tools_tracker.prompt_tokens,
            "completion": tools_tracker.completion_tokens,
        },
        "tools_api_calls": tools_tracker.calls,
    }
    print("\n=== SUMMARY (gap re-run, tools-only) ===")
    print(json.dumps(summary, indent=2))

    RESULTS_PATH.write_text(
        json.dumps({"summary": summary, "results": results}, indent=2, default=str)
    )
    print(f"\nfull results written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
