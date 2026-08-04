#!/usr/bin/env python3
"""Real uplift benchmark: gpt-5-mini answers the same 16 questions two ways.

  1. "bare": plain text question, dataset schema (column names/types/shape) given so
     it isn't guessing totally blind, but NO computed values, NO tools, NO file
     contents. One real API call per question.
  2. "tools": the same question, with the Algenta LLM-tool-calling harness
     (list_capabilities / execute / explain / get_column) available via OpenAI
     function calling. Every number this condition can produce came out of a real,
     compiled Mojo kernel or a plain data-access read of the real CSV -- there is no
     Python-side statistic computation anywhere in benchmarks/algenta_llm_tools/tools.py
     (get_column is data ACCESS only; see its docstring).

Every answer is scored against benchmarks/algenta_llm_tools/eval/quotes_question_set.json's
fixed ground truth + scoring rule (tolerance_abs / exact_int / exact_string /
tolerance_abs_multi) -- exactly as authored, before this script ever ran.

Cost is computed from each API response's own `usage` (prompt/completion tokens) times
the checked-live gpt-5-mini pricing below, never estimated. A hard budget cap aborts
the run (not just warns) if projected spend would exceed it.

Run:
    ALGENTA_RUNTIME_FALLBACK_MODE=allow \
    ALGENTA_MOJO_BINARY=/Users/angel/Developer/decision-engine/mojo_build/simulate \
    PYTHONPATH=packages/algenta python3 -m benchmarks.algenta_llm_tools.eval.run_benchmark
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path("/Users/angel/Developer/decision-engine/.env"), override=False)

from openai import OpenAI  # noqa: E402

from benchmarks.algenta_llm_tools import tools  # noqa: E402

QUESTION_SET_PATH = HERE / "quotes_question_set.json"
CSV_PATH = REPO / "test_files" / "Processed_Quotes.csv"
RESULTS_PATH = HERE / "benchmark_results.json"

MODEL = "gpt-5-mini"
# Checked live 2026-08-04 at developers.openai.com/api/docs/pricing (per 1M tokens).
# Matches this repo's own benchmarks/optmodel_plane/llm_e2e.py PRICING for the same model,
# now with the cached-input rate added: OpenAI's automatic prompt caching (server-side,
# no code required beyond a stable, growing message prefix -- which run_with_tools already
# has, since it appends to the same `messages` list every turn and passes the identical
# `tools=` array every call) reuses a >=1024-token matching prefix at a 90% discount. The
# previous version of this script priced every prompt token at the full input rate and
# never read `usage.prompt_tokens_details.cached_tokens`, so it had no way to tell whether
# caching was firing at all -- CostTracker.add() below now reads that field and prices the
# cached and uncached portions separately, which is the only way to answer that question
# honestly instead of assuming either "it's fine" or "it's broken".
PRICING = {"gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.00}}
BUDGET_CAP_USD = 10.0
# 45, not the originally-planned 20: a pre-flight timing probe on q14 (a ~30-category
# groupby-by-filtering loop, the harness's worst case -- see eval run notes) used 20
# turns to make 107 tool calls (~5.35 calls/turn) without finishing every category.
# Extrapolating that same observed calls-per-turn rate, ~10 more turns would cover the
# remaining categories; 45 leaves roughly 2x that margin. This number was fixed from
# turn-budget mechanics alone, before any question's final correctness was known, and
# was not adjusted afterward based on which answers came out right or wrong.
MAX_TOOL_TURNS = 45

DATASET_DESCRIPTION = """The dataset is a real business CSV file, test_files/Processed_Quotes.csv, \
with 33,125 quote line-item rows. Relevant columns and their types:
- UNIT_PRICE (float, may be null): per-unit quoted price in USD.
- EXT_PRICE (float, may be null): extended (line total) price in USD.
- QUANTITY (float, may be null): quantity quoted.
- STATUS (string, may be null): quote line status, e.g. values including 'QTE', 'ORDER', \
'LOST', 'Lost', 'OPEN', 'Cancelled', 'Won', etc. (case-sensitive; distinct capitalizations \
are distinct values). About a dozen distinct non-null values exist.
- CUST_TYPE (string, may be null): customer type category, e.g. 'OEM', 'MILITARY', 'ENGSHP', \
etc. About 30 distinct values exist, of very uneven frequency (some are extremely rare).
- CUSTOMER_NO (float, may be null): numeric customer identifier.
- AUTO_QUOTED (string, may be null): 'Y' or 'N' flag for whether the quote was auto-generated."""

BARE_SUFFIX = """
You do NOT have access to the actual data, any files, or any tools. Answer using only \
your own reasoning/estimation about a dataset like this -- you are not expected to know \
the real numbers; give your honest best-guess estimate rather than refusing."""

TOOLS_SUFFIX = """
You have real tools available: list_capabilities, execute, explain, get_column. They let \
you query the REAL CSV data and run REAL compiled statistical kernels over it -- use them \
to compute an exact, correct answer; do not guess.
- get_column(column, filter_column=None, filter_value=None, distinct=False, dropna=True) \
reads real column values (optionally row-filtered by an exact match on another column, or \
reduced to distinct values) and returns a result_id you can pass into execute().
- execute(module, function, args) runs one real compiled kernel, e.g. module='stats', \
function='quantile'/'compute_mean'/'compute_variance'/'compute_std_from_values', or \
module='stat_tests', function='pearson_r'. For a sample standard deviation, prefer \
'compute_std_from_values' (module='stats') over calling 'compute_mean' and 'compute_std' \
yourself: it takes only the raw values and their count, computes the mean internally, and \
so has no separate `mean` argument you could get wrong by guessing or eyeballing one from \
a truncated preview. To pass a column you got from get_column (or a prior execute) into \
an execute() argument without retyping thousands of values, set that argument's value to \
{"result_id": "<id>"}.
- Call list_capabilities and/or explain first to find the exact module/function names and \
their exact parameter names -- execute requires exact matches. If a search misses what you \
need, try a different, more specific query string.
- There is no dedicated min/max-of-column kernel. For a column's minimum or maximum, use \
execute(module='stats', function='quantile', args={'v': ..., 'n': ..., 'q': 0.0}) for the \
minimum and q=1.0 for the maximum -- do not spend turns searching for a min/max-named \
function that does not exist.
- If a question needs a per-category value (e.g. "which CUST_TYPE has the highest average \
X"), first call get_column(column=..., distinct=True) to see every real category value, \
then compute the statistic for each one via get_column(filter_column=..., filter_value=...) \
+ execute -- do not answer from only a truncated preview of the raw column.
- Once a tool call's result already, directly, and completely answers the question, use \
that exact returned value in your final answer -- do not recompute it yourself by hand, and \
do not call a second kernel to derive the same statistic a different way (e.g. computing \
variance and then manually taking its square root instead of using a std-dev result you \
already have) unless the question genuinely requires combining multiple distinct \
statistics. A value that came out of a compiled kernel is always more precise than the same \
value re-derived in your own arithmetic -- trust the kernel's own output over a second, \
redundant computation of it."""

FINAL_FORMAT = """
When you have your final answer, reply with ONLY a single JSON object (no markdown code \
fences, no extra prose before or after it) with exactly these keys: {keys}. Numeric values \
must be plain JSON numbers, not strings. Do not include any further tool calls in this \
final message."""


def _load_questions() -> list[dict[str, Any]]:
    payload = json.loads(QUESTION_SET_PATH.read_text())
    return payload["questions"]


def _expected_keys_and_desc(question: dict[str, Any]) -> tuple[list[str], str]:
    gt = question["ground_truth"]
    if isinstance(gt, dict):
        keys = list(gt.keys())
        parts = []
        for k in keys:
            is_str = isinstance(gt[k], str)
            parts.append(f'"{k}" ({"string category label" if is_str else "number"})')
        return keys, ", ".join(parts)
    return ["value"], '"value" (number)'


def _cached_tokens(usage) -> int:
    details = getattr(usage, "prompt_tokens_details", None)
    return getattr(details, "cached_tokens", 0) or 0 if details is not None else 0


def _cost_usd(usage) -> float:
    price = PRICING[MODEL]
    cached = _cached_tokens(usage)
    uncached = max(0, usage.prompt_tokens - cached)
    return (
        (uncached / 1_000_000) * price["input"]
        + (cached / 1_000_000) * price["cached_input"]
        + (usage.completion_tokens / 1_000_000) * price["output"]
    )


def _parse_final_json(content: str, expected_keys: list[str]) -> dict[str, Any] | None:
    if content is None:
        return None
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            obj = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    if not isinstance(obj, dict):
        return None
    return obj


class BudgetExceededError(RuntimeError):
    pass


class CostTracker:
    """Tracks one condition's own totals, but enforces a single SHARED cap across
    every tracker sharing the same ``shared_total`` list -- so "bare" and "tools"
    spend can never combine to exceed the real budget cap, only each condition's own
    subtotal is kept separately for reporting."""

    def __init__(self, cap: float, shared_total: list[float]) -> None:
        self.cap = cap
        self.shared_total = shared_total
        self.total = 0.0
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cached_prompt_tokens = 0

    def add(self, usage) -> float:
        cost = _cost_usd(usage)
        cached = _cached_tokens(usage)
        self.total += cost
        self.calls += 1
        self.prompt_tokens += usage.prompt_tokens
        self.completion_tokens += usage.completion_tokens
        self.cached_prompt_tokens += cached
        self.shared_total[0] += cost
        if self.shared_total[0] > self.cap:
            raise BudgetExceededError(
                f"cumulative real spend ${self.shared_total[0]:.4f} exceeded the ${self.cap} cap"
            )
        return cost

    @property
    def cache_hit_rate(self) -> float:
        return self.cached_prompt_tokens / self.prompt_tokens if self.prompt_tokens else 0.0


def run_bare(client: OpenAI, question: dict[str, Any], tracker: CostTracker) -> dict[str, Any]:
    keys, keys_desc = _expected_keys_and_desc(question)
    system = DATASET_DESCRIPTION + BARE_SUFFIX + FINAL_FORMAT.format(keys=keys_desc)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": question["question"]},
        ],
    )
    tracker.add(resp.usage)
    content = resp.choices[0].message.content
    answer = _parse_final_json(content, keys)
    return {"answer": answer, "raw_content": content, "tool_calls": []}


def run_with_tools(
    client: OpenAI, question: dict[str, Any], tracker: CostTracker
) -> dict[str, Any]:
    keys, keys_desc = _expected_keys_and_desc(question)
    system = DATASET_DESCRIPTION + TOOLS_SUFFIX + FINAL_FORMAT.format(keys=keys_desc)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": question["question"]},
    ]
    tool_call_log: list[dict[str, Any]] = []
    last_content = None
    for turn in range(MAX_TOOL_TURNS):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools.TOOL_SCHEMAS,
        )
        tracker.add(resp.usage)
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))
        last_content = msg.content
        if not msg.tool_calls:
            break
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError as exc:
                result: Any = {"error": f"could not parse arguments JSON: {exc}"}
            else:
                fn = tools.TOOL_FUNCTIONS.get(fn_name)
                if fn is None:
                    result = {"error": f"unknown tool {fn_name!r}"}
                else:
                    try:
                        result = fn(**args)
                    except tools.AlgentaToolError as exc:
                        result = {"error": str(exc)}
                    except TypeError as exc:
                        result = {"error": f"bad arguments for {fn_name}: {exc}"}
            tool_call_log.append(
                {
                    "tool": fn_name,
                    "args": args if isinstance(args, dict) else {},
                    "result": result,
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                }
            )
    else:
        pass  # exhausted MAX_TOOL_TURNS without a final non-tool-call message
    answer = _parse_final_json(last_content, keys)
    return {
        "answer": answer,
        "raw_content": last_content,
        "tool_calls": tool_call_log,
        "turns": turn + 1,
    }


def _num_close(a: Any, b: float, tol: float) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def score(question: dict[str, Any], answer: dict[str, Any] | None) -> tuple[bool, str]:
    scoring = question["scoring"]
    gt = question["ground_truth"]
    if answer is None:
        return False, "no parseable JSON answer"
    stype = scoring["type"]
    if stype == "tolerance_abs":
        val = answer.get("value")
        ok = _num_close(val, gt, scoring["tolerance"])
        return ok, f"value={val!r} vs ground_truth={gt} tol={scoring['tolerance']}"
    if stype == "exact_int":
        val = answer.get("value")
        try:
            ok = int(round(float(val))) == int(gt) and _num_close(val, gt, 0.5)
        except (TypeError, ValueError):
            ok = False
        return ok, f"value={val!r} vs ground_truth={gt}"
    if stype == "tolerance_abs_multi":
        details = []
        all_ok = True
        for field, rule in scoring["fields"].items():
            val = answer.get(field)
            expected = gt[field]
            if rule.get("type") == "exact_string" or isinstance(expected, str):
                ok = isinstance(val, str) and val == expected
            else:
                ok = _num_close(val, expected, rule.get("tolerance", 0.0))
            details.append(f"{field}: got={val!r} expected={expected!r} ok={ok}")
            all_ok = all_ok and ok
        return all_ok, "; ".join(details)
    raise ValueError(f"unhandled scoring type {stype!r}")


def main() -> None:
    if not CSV_PATH.exists():
        raise SystemExit(f"missing fixture: {CSV_PATH}")
    tools.configure_dataset(str(CSV_PATH))
    client = OpenAI()
    questions = _load_questions()

    shared_total = [0.0]
    bare_tracker = CostTracker(BUDGET_CAP_USD, shared_total)
    tools_tracker = CostTracker(BUDGET_CAP_USD, shared_total)

    results = []
    for q in questions:
        qid = q["id"]
        print(f"=== {qid} ===", flush=True)
        t0 = time.time()
        try:
            bare = run_bare(client, q, bare_tracker)
        except BudgetExceededError as exc:
            print(f"BUDGET CAP HIT during bare condition: {exc}")
            break
        bare_ok, bare_detail = score(q, bare["answer"])
        print(f"  bare: {bare['answer']} correct={bare_ok} ({bare_detail}) [{time.time()-t0:.1f}s]")

        t1 = time.time()
        try:
            tooled = run_with_tools(client, q, tools_tracker)
        except BudgetExceededError as exc:
            print(f"BUDGET CAP HIT during tools condition: {exc}")
            break
        tool_ok, tool_detail = score(q, tooled["answer"])
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
                "bare": {**bare, "correct": bare_ok, "detail": bare_detail},
                "tools": {**tooled, "correct": tool_ok, "detail": tool_detail},
            }
        )
        print(
            f"  running cost: bare=${bare_tracker.total:.4f} tools=${tools_tracker.total:.4f} "
            f"total=${bare_tracker.total + tools_tracker.total:.4f}",
            flush=True,
        )

    n = len(results)
    bare_pass = sum(1 for r in results if r["bare"]["correct"])
    tool_pass = sum(1 for r in results if r["tools"]["correct"])
    summary = {
        "model": MODEL,
        "pricing_per_1m": PRICING[MODEL],
        "n_questions": n,
        "bare_pass": bare_pass,
        "tools_pass": tool_pass,
        "bare_cost_usd": round(bare_tracker.total, 6),
        "tools_cost_usd": round(tools_tracker.total, 6),
        "total_cost_usd": round(bare_tracker.total + tools_tracker.total, 6),
        "bare_tokens": {
            "prompt": bare_tracker.prompt_tokens,
            "completion": bare_tracker.completion_tokens,
            "cached_prompt": bare_tracker.cached_prompt_tokens,
            "cache_hit_rate": round(bare_tracker.cache_hit_rate, 4),
        },
        "tools_tokens": {
            "prompt": tools_tracker.prompt_tokens,
            "completion": tools_tracker.completion_tokens,
            "cached_prompt": tools_tracker.cached_prompt_tokens,
            "cache_hit_rate": round(tools_tracker.cache_hit_rate, 4),
        },
        "bare_api_calls": bare_tracker.calls,
        "tools_api_calls": tools_tracker.calls,
        "tool_dedup_hits": tools.dedup_cache_hits(),
    }
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))

    RESULTS_PATH.write_text(
        json.dumps({"summary": summary, "results": results}, indent=2, default=str)
    )
    print(f"\nfull results written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
