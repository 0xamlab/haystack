#!/usr/bin/env python3
"""Real, live re-verification of the LAST TWO open uplift-eval gaps -- q05 (sample
std dev) and q16 (Pearson correlation) -- against the now-fixed tool harness (new
``stats.compute_std`` kernel + new ``get_columns`` joint-alignment tool), both just
added alongside the existing tool set with NO extra hand-holding: the system prompt
below is UNCHANGED from the original run's ``TOOLS_SUFFIX``/``DATASET_DESCRIPTION``
(imported directly from run_benchmark, not reworded), so the model sees
``list_capabilities``/``execute``/``explain``/``get_column``/``get_columns``/
``group_by_aggregate`` side by side and must choose for itself which to reach for.

TOOLS condition only -- q05/q16's bare-LLM answers already exist in
benchmark_results.json and don't depend on the tool harness, so they are not
re-run (this matches the phase-2 rerun_gap_questions.py precedent).

Same model, same live-checked pricing, same scoring rules, same system-prompt
construction as run_benchmark.py -- this file imports run_benchmark's own
functions/constants directly rather than re-implementing them, so there is no
chance of a re-run using different scoring/prompt logic than the original by
accident.

Run:
    ALGENTA_RUNTIME_FALLBACK_MODE=allow \
    ALGENTA_MOJO_BINARY=/tmp/uplift-final-two-gaps/mojo_build/simulate \
    PYTHONPATH=packages/algenta python3 -m \
        benchmarks.algenta_llm_tools.eval.rerun_final_two_gaps
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
    "q16_corr_unit_price_quantity",
}

RESULTS_PATH = HERE / "final_two_gaps_rerun_results.json"
BUDGET_CAP_USD = 3.0


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
        used_new_tool = any(
            tc["tool"] == "get_columns"
            or (
                tc["tool"] == "execute"
                and isinstance(tc.get("args"), dict)
                and tc["args"].get("function") == "compute_std"
            )
            for tc in tooled["tool_calls"]
        )
        print(
            f"  tools ({tooled.get('turns')} turns, "
            f"{len(tooled['tool_calls'])} tool calls, new-tool-used={used_new_tool}): "
            f"{tooled['answer']} correct={tool_ok} ({tool_detail}) [{time.time() - t1:.1f}s]"
        )
        for tc in tooled["tool_calls"]:
            print(f"    call: {tc['tool']}({tc.get('args')})")
        results.append(
            {
                "id": qid,
                "question": q["question"],
                "ground_truth": q["ground_truth"],
                "scoring": q["scoring"],
                "used_new_tool_or_kernel": used_new_tool,
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
    print("\n=== SUMMARY (final-two-gaps rerun, tools-only) ===")
    print(json.dumps(summary, indent=2))

    RESULTS_PATH.write_text(
        json.dumps({"summary": summary, "results": results}, indent=2, default=str)
    )
    print(f"\nfull results written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
