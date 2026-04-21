#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import anyio
from dotenv import load_dotenv
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env", override=False)
MCP_URL = os.environ.get("BENCH_MCP_URL", "http://127.0.0.1:8002/sse")


SYSTEM_PROMPT = """
You generate benchmark questions for a data query engine.
Return ONLY valid JSON.

Goal:
- Create exactly 20 natural-language analytics questions.
- Use ONLY the provided dataset summary.
- Questions must be answerable by ONE call to the `query_data` tool.
- Every question must require exactly one metric and at most one grouping dimension.
- Mix scalar, grouped, top-N, average, count, cross-source, and multi-hop join questions.
- Include some harder but realistic questions that require choosing the right source.
- Prefer questions about totals, averages, counts, top categories, and simple time windows.
    - Avoid unsupported requests such as correlation, percent-of-total, distinct counts,
      nested comparisons,
  top-N within top-N, multi-metric outputs, boolean filters, and free-form date arithmetic.
- Do not mention SQL, schemas, or internal implementation.

Output schema:
{
  "questions": [
    {"id": "Q1", "question": "..."}
  ]
}
""".strip()


ARG_PROMPT = """
You convert a user analytics question into structured arguments for the MCP tool `query_data`.
Return ONLY valid JSON.

Rules:
- Use the provided dataset summary only.
- Prefer the smallest relevant subset of sources.
- Use `metric.role` from: derived_measure, base_measure, unit_measure, ratio, metric.
- Put a short semantic phrase in `metric.hint`, not the whole question.
- Put dimension words only in `group_by`.
- Use `aggregation` from: sum, avg, count, max, min.
- Use `limit=5` only for ranking/top questions.
- If the question is scalar, omit `group_by`.
- Do not invent filters the tool cannot express except allowed `time_filter` values.
- Keep output to the exact tool argument shape only.

Output schema:
{
  "sources": [{"name": "..."}],
  "metric": {"role": "metric", "hint": "..."},
  "aggregation": "sum",
  "group_by": ["..."],
  "filter": {"time_filter": "last_quarter"},
  "limit": 5,
  "order": "desc"
}
""".strip()


def _canonical_source_name(value: str) -> str | None:
    norm = value.strip().lower()
    if not norm:
        return None
    if "backlog" in norm:
        return "Backlog"
    if (
        norm == "opo"
        or "purchase order" in norm
        or "vendor" in norm
        or "buyer" in norm
        or "division" in norm
    ):
        return "OPO"
    if norm == "pos" or "recent pos" in norm or "oem" in norm:
        return "POS"
    if "quote" in norm:
        return "Quotes"
    return None


def _infer_sources(question: str, draft_sources: list[dict] | None) -> list[str]:
    picks: list[str] = []
    for src in draft_sources or []:
        name = _canonical_source_name(str(src.get("name", "")))
        if name and name not in picks:
            picks.append(name)

    q = question.lower()
    rules = [
        (
            "Backlog",
            ["backlog", "projected ship", "ship date", "ordered on", "status", "project id"],
        ),
        (
            "OPO",
            ["opo", "vendor", "buyer", "division", "profit center", "purchase order", "order type"],
        ),
        ("POS", ["recent pos", " pos ", "oem", "unit cost"]),
        ("Quotes", ["quote", "quotes", "recent quote", "unit price"]),
    ]
    for source_name, keywords in rules:
        if any(token in q for token in keywords) and source_name not in picks:
            picks.append(source_name)

    if "same part number" in q or "matching part number" in q or "for the same part" in q:
        if "Quotes" not in picks:
            picks.append("Quotes")
        if "POS" not in picks and "cost" in q:
            picks.append("POS")
        if "Backlog" not in picks and "backlog" in q:
            picks.append("Backlog")

    if not picks:
        picks.append("Backlog")
    return picks


def _infer_aggregation(question: str, draft_agg: str | None) -> str:
    q = question.lower()
    if any(token in q for token in ["how many", "count", "number of"]):
        return "count"
    if any(token in q for token in ["average", "avg", "mean"]):
        return "avg"
    if draft_agg in {"sum", "avg", "count", "max", "min"}:
        return draft_agg
    return "sum"


def _infer_metric(question: str, aggregation: str, draft_metric: dict | None) -> dict:
    q = question.lower()
    if "extended price" in q or "ext price" in q or "backlog value" in q or "total value" in q:
        return {"role": "derived_measure", "hint": "extended price"}
    if "unit price" in q:
        return {"role": "unit_measure", "hint": "unit price"}
    if "unit cost" in q:
        return {"role": "unit_measure", "hint": "unit cost"}
    if "quantity" in q:
        return {"role": "base_measure", "hint": "quantity"}
    if aggregation == "count":
        return {"role": "base_measure", "hint": "quantity"}
    if draft_metric and draft_metric.get("role") in {
        "derived_measure",
        "base_measure",
        "unit_measure",
        "ratio",
        "metric",
    }:
        hint = str(draft_metric.get("hint", "") or "").strip()
        return {"role": str(draft_metric["role"]), "hint": hint or "value"}
    return {"role": "metric", "hint": "value"}


def _infer_group_by(question: str) -> list[str]:
    q = question.lower()
    if not any(token in q for token in [" by ", "which ", "top ", "highest", "lowest"]):
        return []
    rules = [
        ("status", ["status"]),
        ("customer", ["customer"]),
        ("part number", ["part number", "part numbers"]),
        ("project id", ["project id", "project"]),
        ("vendor", ["vendor"]),
        ("buyer", ["buyer"]),
        ("division", ["division"]),
        ("oem", ["oem"]),
        ("date", ["invoice date", "ordered on", "date", "day", "month"]),
        ("state", ["state"]),
    ]
    for dim, keywords in rules:
        if any(token in q for token in keywords):
            return [dim]
    return []


def _build_exact_spec_if_possible(
    source_names: list[str],
    metric: dict,
    aggregation: str,
    group_by: list[str],
) -> dict | None:
    if (
        source_names == ["POS"]
        and metric.get("hint") == "unit cost"
        and aggregation == "avg"
        and not group_by
    ):
        return {
            "source_name": "POS",
            "metric_column": "UNIT_COST",
            "aggregation": "avg",
            "order": "desc",
        }
    return None


def _postprocess_tool_args(question: str, draft: dict) -> dict:
    aggregation = _infer_aggregation(question, draft.get("aggregation"))
    metric = _infer_metric(question, aggregation, draft.get("metric"))
    group_by = _infer_group_by(question)
    source_names = _infer_sources(question, draft.get("sources"))
    q = question.lower()

    args: dict = {
        "sources": [{"name": name} for name in source_names],
        "metric": metric,
        "aggregation": aggregation,
        "order": (
            "asc" if any(token in q for token in ["lowest", "smallest", "least"]) else "desc"
        ),
    }
    if group_by:
        args["group_by"] = group_by
    if any(token in q for token in ["top", "highest", "lowest", "which"]):
        args["limit"] = 5
    if "last quarter" in q:
        args["filter"] = {"time_filter": "last_quarter"}
    elif "this quarter" in q:
        args["filter"] = {"time_filter": "this_quarter"}
    elif "last month" in q:
        args["filter"] = {"time_filter": "last_month"}
    elif "this month" in q:
        args["filter"] = {"time_filter": "this_month"}
    exact = _build_exact_spec_if_possible(source_names, metric, aggregation, group_by)
    if exact:
        exact["sources"] = args["sources"]
        return exact
    return args


DATASET_CONTEXT = """
Real CSV assets available under test_files:

1. Backlog.csv
- 1,535 rows, 39 columns
- Key fields include: ORDERED_ON, CUSTOMER_MASKED, PART_NUMBER, ALT_PART_NUMBER,
  QUANTITY, UNIT_PRICE, EXT_PRICE, STATUS, PROJECTED_SHIP, PROJECT_ID, SHIP_TO_STATE

2. OPO.csv
- 1,139 rows, 41 columns
- Key fields include: Profit Center, Division, Vendor No, Vendor Name, Buyer No,
  Buyer First, Buyer Last, Customer PO, Order Type, Order Number

3. Unique_POS_Recent_Stats.csv
- 1,677 rows, 6 columns
- Key fields include: PART_NUMBER, ALTERNATE_PN, DESC, UNIT_COST, OEM, INVOICE_DATE

4. Unique_Quotes_Recent_Stats.csv
- 1,676 rows, 144 columns
- Key fields include: INVOICE_DATE, CUSTOMER, PART_NUMBER, QUANTITY, UNIT_COST,
  UNIT_PRICE, EXT_COST, EXT_PRICE, ORDERED_ON, STATUS, ORDER_NUMBER, PROJECT_ID

Likely common join anchors across sources:
- PART_NUMBER
- PROJECT_ID / ORDER_NUMBER in some flows

Prefer business-natural analytics questions such as totals, averages, counts,
top categories, trends, margin/cost/value comparisons, and questions that may
require combining quote/backlog/POS style sources.
""".strip()


def _extract_text(result) -> str:
    parts: list[str] = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _sanitize_tool_args(arguments: dict) -> dict:
    clean = json.loads(json.dumps(arguments))
    sources = []
    for src in clean.get("sources", []) or []:
        sources.append({k: v for k, v in src.items() if k != "csv"})
    if sources:
        clean["sources"] = sources
    return clean


def _write_summary(out: dict) -> None:
    lines = [
        "# Claude MCP 20Q Summary",
        "",
        f"- MCP URL: `{out['mcp_url']}`",
        f"- Passed: **{out['passed']}/{out['question_count']}**",
        f"- Average latency: **{out['avg_elapsed_ms']} ms**",
        "",
        "| ID | OK | Source | Column | Type | Rows | ms | Question |",
        "|---|---|---|---|---|---:|---:|---|",
    ]
    for row in out["results"]:
        lines.append(
            "| {id} | {ok} | {src} | {col} | {rtype} | {rows} | {ms} | {q} |".format(
                id=row.get("id", ""),
                ok="✅" if row.get("ok") else "❌",
                src=row.get("resolved_source") or "",
                col=row.get("resolved_column") or "",
                rtype=row.get("result_type") or "",
                rows=row.get("row_count") or 0,
                ms=row.get("elapsed_ms") or 0,
                q=str(row.get("question", "")).replace("|", "\\|"),
            )
        )
    (ROOT / "benchmarks" / "claude_mcp_20q_summary.md").write_text("\n".join(lines) + "\n")


async def _call_mcp_tool(session: ClientSession, name: str, arguments: dict) -> dict:
    started = time.perf_counter()
    result = await session.call_tool(name, arguments)
    elapsed_ms = (time.perf_counter() - started) * 1000
    text = _extract_text(result)
    try:
        payload = json.loads(text)
    except Exception:
        payload = {"raw": text}
    return {"payload": payload, "elapsed_ms": elapsed_ms, "raw": text}


async def _generate_questions() -> list[dict[str, str]]:
    from apps.api_server.services.auto_planner import _llm_client

    client = _llm_client()
    if client is None:
        raise RuntimeError("Anthropic client unavailable")

    prompt = f"{SYSTEM_PROMPT}\n\nDataset summary:\n{DATASET_CONTEXT}"
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1400,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
    data = json.loads(raw)
    questions = data.get("questions", [])
    if len(questions) != 20:
        raise RuntimeError(f"Expected 20 questions, got {len(questions)}")
    return questions


async def _generate_tool_args(question: str) -> dict:
    from apps.api_server.services.auto_planner import _llm_client

    client = _llm_client()
    if client is None:
        raise RuntimeError("Anthropic client unavailable")

    prompt = (
        f"{ARG_PROMPT}\n\n"
        f"Dataset summary:\n{DATASET_CONTEXT}\n\n"
        f"Question: {question}"
    )
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=700,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
    data = json.loads(raw)
    return _postprocess_tool_args(question, data)


async def main() -> None:
    questions = await _generate_questions()

    headers = {"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"}
    results: list[dict] = []
    csv_by_name = {
        "Backlog": (ROOT / "test_files" / "Backlog.csv").read_text(
            encoding="utf-8-sig",
            errors="replace",
        ),
        "OPO": (ROOT / "test_files" / "OPO.csv").read_text(encoding="utf-8-sig", errors="replace"),
        "POS": (ROOT / "test_files" / "Unique_POS_Recent_Stats.csv").read_text(
            encoding="utf-8-sig",
            errors="replace",
        ),
        "Quotes": (ROOT / "test_files" / "Unique_Quotes_Recent_Stats.csv").read_text(
            encoding="utf-8-sig",
            errors="replace",
        ),
    }

    async with sse_client(MCP_URL, headers=headers) as streams:
        read_stream, write_stream = streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            for item in questions:
                qid = item["id"]
                question = item["question"]
                args = await _generate_tool_args(question)
                resolved_sources = []
                for src in args.get("sources", []):
                    src_name = src.get("name")
                    if src_name in csv_by_name:
                        resolved_sources.append(
                            {"name": src_name, "csv": csv_by_name[src_name]}
                        )
                args["sources"] = resolved_sources
                outcome = await _call_mcp_tool(session, "query_data", args)
                payload = outcome["payload"]
                results.append({
                    "id": qid,
                    "question": question,
                    "tool_args": _sanitize_tool_args(args),
                    "elapsed_ms": round(outcome["elapsed_ms"], 1),
                    "confidence": payload.get("confidence"),
                    "resolved_source": payload.get("resolved_source"),
                    "resolved_column": payload.get("resolved_column"),
                    "row_count": payload.get("row_count"),
                    "result_type": payload.get("result_type"),
                    "ok": payload.get("result") is not None,
                    "note": payload.get("note", ""),
                })

    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mcp_url": MCP_URL,
        "question_count": len(questions),
        "results": results,
        "avg_elapsed_ms": round(
            sum(r["elapsed_ms"] for r in results) / max(len(results), 1),
            1,
        ),
        "passed": sum(1 for r in results if r["ok"]),
    }
    out_path = ROOT / "benchmarks" / "claude_mcp_20q_results.json"
    out_path.write_text(json.dumps(out, indent=2))
    _write_summary(out)

    print(json.dumps(out, indent=2))
    print(f"\nresults_file={out_path}")


if __name__ == "__main__":
    anyio.run(main)
