#!/usr/bin/env python3
"""End-to-end pass@1: LLM writes a formulation, optmodel solves + judges it.

The solver-side ceiling (`harness.py`, `--mirror`) measures: given the CORRECT
formulation, how often does the plane reach the verified optimum (93.5% on the
780-instance proxy mirror). This script measures the harder, real thing MM-OptBench
itself scores: given only a NATURAL-LANGUAGE problem statement, does an LLM extract a
correct formulation, and does solving THAT formulation through the exact same
`optmodel` plane reach the same verified optimum?

Honest scope, stated plainly wherever results are reported:
  - The real MM-OptBench (arXiv:2605.12154) dataset is member-restricted/unreleased.
    This runs on the SAME proxy mirror corpus #477 built and measured the ceiling on
    (`make_mirror_instances.py`), not the withheld benchmark.
  - That corpus's instances don't carry natural-language problem text (only a one-line
    machine label). `llm_e2e_render.py` mechanically renders each SAMPLED instance's
    own flat data into a natural-language word problem, using the known generator
    convention per subcategory. This is a templated rendering of our own proxy data,
    not an independently authored word problem — a weaker test of language
    understanding than the real benchmark, stated as a caveat on every result.

Pipeline per sampled instance:
  1. render NL problem text (`llm_e2e_render.render_instance`);
  2. ask the LLM for a formulation in optmodel's flat schema (structured JSON output);
  3. validate + convert to the same instance shape `harness.py` already compiles
     (variables/objective/constraints), carrying the ORIGINAL instance's id, max_nodes
     and ground_truth (the independently-known correct answer) forward — the LLM never
     sees the ground truth;
  4. compile to the SAME wire format and run through the SAME generated Mojo runner
     (`optmodel.judge.formulation_verdict_default`) the ceiling harness uses, so a
     formulation that is a correct model of the scenario reaches the same verified
     optimum, and one that is not lands in WRONG or REFUSED — exactly the ceiling
     harness's own gate logic, reused, not reimplemented.

Cost is computed from the API's own reported token usage x the checked-live pricing
for the chosen model (recorded in `PRICING` below), never estimated or assumed.

Run:
    PYTHONPATH=. python3 benchmarks/optmodel_plane/llm_e2e.py --n-easy 26 --n-medium 6
    PYTHONPATH=. python3 benchmarks/optmodel_plane/llm_e2e.py --dry-run 2   # smoke test, 2 instances
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO / ".env", override=False)

sys.path.insert(0, str(HERE))
import harness  # noqa: E402
from llm_e2e_render import SCHEMA_BLURB, render_instance  # noqa: E402

BUILD = REPO / "build" / "optmodel_plane"
MIRROR_PATH = BUILD / "mirror_instances.json"
RESULTS_PATH = BUILD / "llm_e2e_results.json"

MODEL = "gpt-5-mini"
# Checked live 2026-08-01 at developers.openai.com/api/docs/pricing (per 1M tokens).
PRICING = {"gpt-5-mini": {"input": 0.25, "output": 2.00}}

# One easy-tier instance per subcategory (full taxonomy coverage) plus one medium-tier
# instance per family (difficulty variety), mirroring the families/subcategories the
# solver-side ceiling run (#477) already used. All indices are "_00" (deterministic,
# first generated instance of that subcategory/tier).
ALL_SUBCATS = [
    "min_cost_flow", "max_flow", "rc_shortest_path", "cap_network_design",
    "time_expanded_flow", "facility_location", "p_median_center",
    "set_cover_partition", "assignment_matching", "generalized_assignment",
    "job_shop", "parallel_machine", "rcpsp", "hybrid_flow_shop", "lot_sizing",
    "unit_commitment", "workforce_shift", "inventory_routing", "tsp", "cvrp",
    "tsptw", "hf_vrp", "multidim_knapsack", "graph_coloring", "set_packing",
    "logical_csp",
]
MEDIUM_SAMPLE = [
    "min_cost_flow", "facility_location", "job_shop", "tsp", "lot_sizing",
    "multidim_knapsack",
]

SYSTEM_PROMPT = f"""\
You are an expert operations-research analyst. You will be given a natural-language
optimization problem. Read it carefully, identify every decision variable, the
objective, and every constraint, and produce an exact mathematical formulation.

{SCHEMA_BLURB}

Think step by step about entities, indices and units before you commit to the JSON,
but your response must contain ONLY the structured formulation object — no prose
commentary outside the schema.\
"""


@dataclass
class SampleResult:
    id: str
    family: str
    subcategory: str
    difficulty: str
    status: str  # ok | api_error | malformed
    reason: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    llm_formulation: dict | None = None
    verdict_strict: str = ""
    verdict_lineage: str = ""
    plane_status: str = ""
    objective: str = ""
    ground_truth: float = 0.0
    paper_floor: float = 0.0
    paper_rule_pass: bool = False
    nodes: str = ""
    latency_s: float = 0.0


def load_mirror() -> list[dict]:
    if not MIRROR_PATH.exists():
        raise SystemExit(f"no mirror at {MIRROR_PATH} — run make_mirror_instances.py first")
    return json.loads(MIRROR_PATH.read_text(encoding="utf-8"))


def select_sample(n_easy: int, n_medium: int) -> list[dict]:
    instances = load_mirror()
    by_key = {(i["subcategory"], i["difficulty"]): i for i in instances if i["id"].endswith("_00")}
    sample = []
    for sub in ALL_SUBCATS[:n_easy]:
        sample.append(by_key[(sub, "easy")])
    for sub in MEDIUM_SAMPLE[:n_medium]:
        sample.append(by_key[(sub, "medium")])
    return sample


# ── JSON schema for the structured LLM response ─────────────────────────────────

VAR_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "kind": {"type": "string", "enum": ["continuous", "integer", "binary"]},
        "lower": {"type": ["number", "null"]},
        "upper": {"type": ["number", "null"]},
    },
    "required": ["name", "kind", "lower", "upper"],
    "additionalProperties": False,
}
TERM_SCHEMA = {
    "type": "object",
    "properties": {"var": {"type": "string"}, "coeff": {"type": "number"}},
    "required": ["var", "coeff"],
    "additionalProperties": False,
}
CONSTRAINT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "terms": {"type": "array", "items": TERM_SCHEMA},
        "sense": {"type": "string", "enum": ["<=", "==", ">="]},
        "rhs": {"type": "number"},
    },
    "required": ["name", "terms", "sense", "rhs"],
    "additionalProperties": False,
}
FORMULATION_SCHEMA = {
    "type": "object",
    "properties": {
        "maximize": {"type": "boolean"},
        "variables": {"type": "array", "items": VAR_SCHEMA},
        "objective": {
            "type": "object",
            "properties": {
                "terms": {"type": "array", "items": TERM_SCHEMA},
                "constant": {"type": "number"},
            },
            "required": ["terms", "constant"],
            "additionalProperties": False,
        },
        "constraints": {"type": "array", "items": CONSTRAINT_SCHEMA},
    },
    "required": ["maximize", "variables", "objective", "constraints"],
    "additionalProperties": False,
}
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {"formulation": FORMULATION_SCHEMA},
    "required": ["formulation"],
    "additionalProperties": False,
}


def call_llm(client, problem_text: str) -> tuple[dict, int, int]:
    """One structured-output call. Returns (formulation_dict, prompt_tokens, completion_tokens)."""
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": problem_text},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "optmodel_formulation",
                "schema": RESPONSE_SCHEMA,
                "strict": True,
            },
        },
    )
    content = resp.choices[0].message.content
    payload = json.loads(content)
    usage = resp.usage
    return payload["formulation"], usage.prompt_tokens, usage.completion_tokens


# ── validation + conversion to the harness's instance shape ────────────────────

def llm_formulation_to_instance(original: dict, formulation: dict) -> dict:
    var_names = set()
    variables = []
    for v in formulation["variables"]:
        name = v["name"]
        if name in var_names:
            raise ValueError(f"duplicate variable name {name!r}")
        var_names.add(name)
        entry = {"name": name, "kind": v["kind"]}
        if v.get("lower") is not None:
            entry["lower"] = float(v["lower"])
        else:
            entry["lower"] = None
        if v.get("upper") is not None:
            entry["upper"] = float(v["upper"])
        variables.append(entry)
    if not variables:
        raise ValueError("no variables declared")

    def _terms_to_coeffs(terms: list[dict], where: str) -> dict:
        coeffs: dict[str, float] = {}
        for t in terms:
            name = t["var"]
            if name not in var_names:
                raise ValueError(f"{where}: references undeclared variable {name!r}")
            coeffs[name] = coeffs.get(name, 0.0) + float(t["coeff"])
        return coeffs

    objective = {
        "coeffs": _terms_to_coeffs(formulation["objective"]["terms"], "objective"),
        "constant": float(formulation["objective"].get("constant", 0.0)),
    }
    constraints = []
    seen_names = set()
    for i, c in enumerate(formulation["constraints"]):
        name = c.get("name") or f"c{i}"
        if name in seen_names:
            name = f"{name}_{i}"
        seen_names.add(name)
        coeffs = _terms_to_coeffs(c["terms"], f"constraint {name}")
        if c["sense"] not in ("<=", "==", ">="):
            raise ValueError(f"constraint {name}: bad sense {c['sense']!r}")
        constraints.append({
            "name": name, "coeffs": coeffs, "sense": c["sense"], "rhs": float(c["rhs"]),
        })

    return {
        "id": original["id"],
        "family": original["family"],
        "subcategory": original["subcategory"],
        "difficulty": original["difficulty"],
        "description": original["description"],
        "maximize": bool(formulation["maximize"]),
        "objective": objective,
        "variables": variables,
        "constraints": constraints,
        "expect": "measure",
        "max_nodes": original["max_nodes"],
        "ground_truth": original["ground_truth"],
        "paper_floor": original.get("paper_floor", 0.0),
    }


# ── run the plane on the LLM formulations, reusing harness.py verbatim ─────────

def run_plane(llm_instances: list[dict], chunk_timeout: int) -> dict[str, dict]:
    harness.emit_runner()
    wire_path = BUILD / "wire_llm_e2e.txt"
    text = f"OPTMWIRE1 {len(llm_instances)}\n" + "\n".join(
        harness.wire_instance(i) for i in llm_instances)
    wire_path.write_text(text + "\n", encoding="utf-8")
    results, parse_failures, completed = harness.run_mojo_chunk(wire_path, chunk_timeout)
    if parse_failures:
        raise SystemExit(f"PARSE_FAIL in LLM-formulation wire: {parse_failures}")
    if not completed:
        raise SystemExit("mojo runner did not complete on the LLM-formulation wire")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-easy", type=int, default=26)
    parser.add_argument("--n-medium", type=int, default=6)
    parser.add_argument("--dry-run", type=int, default=0,
                        help="only send the first N sampled instances (smoke test)")
    parser.add_argument("--chunk-timeout", type=int, default=1800)
    parser.add_argument("--redo-ids", default=None,
                        help="comma-separated instance ids to re-run; merges into the "
                             "existing --results-in file instead of a fresh sample "
                             "(fixes a bug affecting only those instances without "
                             "re-spending on an already-good result)")
    parser.add_argument("--results-in", default=str(RESULTS_PATH),
                        help="existing results.json to merge --redo-ids into")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY not set (checked process env, loaded from .env)")

    import openai
    # A stuck call must fail fast (typed api_error, retried on the next run) rather
    # than hang the whole batch indefinitely — a reasoning-heavy formulation can
    # legitimately take 1-2 minutes, so the cap is generous, not tight.
    client = openai.OpenAI(api_key=api_key, timeout=240.0, max_retries=1)

    if args.redo_ids:
        redo_ids = set(args.redo_ids.split(","))
        mirror = {i["id"]: i for i in load_mirror()}
        sample = [mirror[i] for i in redo_ids]
        prior = json.loads(Path(args.results_in).read_text(encoding="utf-8"))
    else:
        redo_ids = None
        prior = None
        sample = select_sample(args.n_easy, args.n_medium)
    if args.dry_run:
        sample = sample[: args.dry_run]
    print(f"sample: {len(sample)} instances "
          f"({len({i['subcategory'] for i in sample})} subcategories, "
          f"{len({i['family'] for i in sample})} families)")

    results: list[SampleResult] = []
    llm_instances: list[dict] = []
    total_prompt_tok = 0
    total_completion_tok = 0

    for inst in sample:
        r = SampleResult(
            id=inst["id"], family=inst["family"], subcategory=inst["subcategory"],
            difficulty=inst["difficulty"], status="ok",
            ground_truth=float(inst["ground_truth"]["objective"]),
            paper_floor=float(inst.get("paper_floor", 0.0)),
        )
        try:
            problem_text = render_instance(inst)
        except Exception as e:  # pragma: no cover - render bug, not LLM's fault
            r.status, r.reason = "render_error", repr(e)
            results.append(r)
            continue

        print(f"  {inst['id']}: calling {MODEL}...", flush=True)
        t0 = time.monotonic()
        try:
            formulation, ptok, ctok = call_llm(client, problem_text)
        except Exception as e:
            r.latency_s = time.monotonic() - t0
            r.status, r.reason = "api_error", repr(e)
            results.append(r)
            print(f"  {inst['id']}: api_error after {r.latency_s:.1f}s: {e!r}", flush=True)
            continue
        r.latency_s = time.monotonic() - t0
        r.prompt_tokens, r.completion_tokens = ptok, ctok
        total_prompt_tok += ptok
        total_completion_tok += ctok
        r.llm_formulation = formulation

        try:
            llm_inst = llm_formulation_to_instance(inst, formulation)
        except Exception as e:
            r.status, r.reason = "malformed", str(e)
            results.append(r)
            print(f"  {inst['id']}: malformed formulation: {e}", flush=True)
            continue

        llm_instances.append(llm_inst)
        results.append(r)
        print(f"  {inst['id']}: got formulation "
              f"({len(formulation['variables'])} vars, {len(formulation['constraints'])} cons), "
              f"{ptok}+{ctok} tok, {r.latency_s:.1f}s", flush=True)

    cost = (total_prompt_tok * PRICING[MODEL]["input"]
            + total_completion_tok * PRICING[MODEL]["output"]) / 1_000_000
    print(f"\nLLM calls done: {len(llm_instances)}/{len(sample)} produced a well-formed "
          f"formulation; {total_prompt_tok} prompt + {total_completion_tok} completion "
          f"tokens; cost ${cost:.4f} at {MODEL} pricing "
          f"(${PRICING[MODEL]['input']}/${PRICING[MODEL]['output']} per 1M in/out)")

    if llm_instances:
        print(f"\nrunning {len(llm_instances)} LLM formulations through optmodel "
              "(solve.mojo + judge.mojo, same pipeline as the ground-truth ceiling)...")
        t0 = time.monotonic()
        plane_results = run_plane(llm_instances, args.chunk_timeout)
        print(f"mojo run: {time.monotonic() - t0:.1f}s")
    else:
        plane_results = {}

    by_id = {r.id: r for r in results}
    for inst in llm_instances:
        r = by_id[inst["id"]]
        pr = plane_results.get(inst["id"])
        if pr is None:
            r.status, r.reason = "no_result", "no RESULT line from the runner"
            continue
        r.verdict_strict = pr["strict"]
        r.verdict_lineage = pr["lineage"]
        r.plane_status = pr["status"]
        r.objective = pr["objective"]
        r.nodes = pr["nodes"]
        if pr["strict"] == "verified":
            try:
                r.paper_rule_pass = harness.paper_rule_matches(
                    float(pr["objective"]), r.ground_truth, r.paper_floor)
            except ValueError:
                r.paper_rule_pass = False

    # ── merge with a prior results file when redoing specific ids ────────────────
    new_result_dicts = [
        {
            "id": r.id, "family": r.family, "subcategory": r.subcategory,
            "difficulty": r.difficulty, "status": r.status, "reason": r.reason,
            "prompt_tokens": r.prompt_tokens, "completion_tokens": r.completion_tokens,
            "verdict_strict": r.verdict_strict, "verdict_lineage": r.verdict_lineage,
            "plane_status": r.plane_status, "objective": r.objective,
            "ground_truth": r.ground_truth, "paper_rule_pass": r.paper_rule_pass,
            "nodes": r.nodes, "latency_s": r.latency_s,
            "llm_formulation": r.llm_formulation,
        }
        for r in results
    ]
    if prior is not None:
        merged_by_id = {rd["id"]: rd for rd in prior["results"]}
        replaced = [rd["id"] for rd in new_result_dicts if rd["id"] in merged_by_id]
        merged_by_id.update({rd["id"]: rd for rd in new_result_dicts})
        all_results = list(merged_by_id.values())
        combined_cost = prior["cost_usd"] + cost
        combined_prompt_tok = prior["total_prompt_tokens"] + total_prompt_tok
        combined_completion_tok = prior["total_completion_tokens"] + total_completion_tok
        print(f"\nmerged {len(new_result_dicts)} redone id(s) into {len(prior['results'])} "
              f"prior results (replaced: {replaced}); this redo spent an ADDITIONAL "
              f"${cost:.4f} on top of the prior ${prior['cost_usd']:.4f} "
              f"(total spend across both attempts: ${combined_cost:.4f})")
    else:
        all_results = new_result_dicts
        combined_cost = cost
        combined_prompt_tok = total_prompt_tok
        combined_completion_tok = total_completion_tok

    # ── report (recomputed from the full merged result set) ─────────────────────
    print()
    fam_table: dict[str, dict[str, int]] = {}
    for rd in all_results:
        row = fam_table.setdefault(rd["family"], {"n": 0, "pass": 0})
        row["n"] += 1
        if rd["status"] == "ok" and rd["verdict_strict"] == "verified" and rd["paper_rule_pass"]:
            row["pass"] += 1
    print(f"{'family':<26}{'n':>5}{'pass':>7}{'pass@1':>9}")
    total_n = total_pass = 0
    for fam in sorted(fam_table):
        row = fam_table[fam]
        rate = row["pass"] / row["n"] if row["n"] else 0.0
        print(f"{fam:<26}{row['n']:>5}{row['pass']:>7}{rate:>9.1%}")
        total_n += row["n"]
        total_pass += row["pass"]
    print(f"{'TOTAL':<26}{total_n:>5}{total_pass:>7}{(total_pass / total_n if total_n else 0):>9.1%}")

    print()
    print(f"{'id':<28}{'status':<10}{'strict':<10}{'lineage':<10}{'paper_rule':<11}{'note':<30}")
    for rd in sorted(all_results, key=lambda r: r["id"]):
        note = rd["reason"] if rd["status"] != "ok" else rd["plane_status"]
        print(f"{rd['id']:<28}{rd['status']:<10}{rd['verdict_strict']:<10}{rd['verdict_lineage']:<10}"
              f"{str(rd['paper_rule_pass']):<11}{(note or '')[:30]:<30}")

    out = {
        "model": MODEL,
        "n_sample": len(all_results),
        "n_well_formed": sum(1 for rd in all_results if rd["status"] == "ok"),
        "total_prompt_tokens": combined_prompt_tok,
        "total_completion_tokens": combined_completion_tok,
        "cost_usd": combined_cost,
        "pass_at_1_overall": total_pass / total_n if total_n else 0.0,
        "family_table": fam_table,
        "results": all_results,
    }
    RESULTS_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
