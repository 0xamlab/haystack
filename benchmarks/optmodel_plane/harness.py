"""Solver-side ceiling harness: ground-truth formulations through the optmodel plane.

The measurement MM-OptBench's own oracle-reading ablation motivates: given the
machine-readable formulation (the benchmark's hidden `instance_data` side), what
fraction does the deterministic Algenta plane solve AND verify, what fraction does it
refuse WITH A TYPE, and — the number that must be zero — how often does it return a
plausible wrong answer?

Pipeline, all deterministic, zero LLM spend:

  1. load `instances/*.json` (the hand-authored seed set, see `make_seed_instances.py`)
     and, with `--mirror`, the generated 780-instance benchmark mirror (see
     `make_mirror_instances.py`, 26 subcategories x 3 difficulty tiers x 10);
  2. REFEREE every instance independently with SciPy's HiGHS (`scipy.optimize.milp`):
     a solvable instance is admitted only if HiGHS proves optimality and agrees with
     the stated ground truth; a refusal instance's model-level claim (infeasible /
     unbounded) must be reproduced. The referee is a different solver, a different
     author and a different algorithm, so agreement is evidence, not a mirror;
  3. compile the instances to a token WIRE file plus a small GENERATED Mojo runner
     that parses it at runtime (token-count + magnitude checksums per instance, so a
     framing slip is a typed PARSE_FAIL, never a silently different model) and calls
     `optmodel.judge.formulation_verdict_default` per instance;
  4. run it through the real Mojo toolchain (`pixi run mojo run`) in chunks, so one
     aborted worker loses one chunk, not the whole measurement; parse one RESULT line
     per instance;
  5. GATE: every instance must land in its EXPECTED bucket (derived from the instance
     files, the source of truth — never a hardcoded count), the WRONG bucket must be
     empty, and every VERIFIED objective must ALSO match the ground truth under the
     benchmark's published tolerance rule (default 1e-6, with the paper's 1e-3
     absolute floor for continuous-objective location instances). Exit 1 otherwise,
     naming each offender.

Instances declare `expect`:
  - "verified"/"refused": curated seeds — landing anywhere else is a gate violation;
  - "measure": mirror instances — VERIFIED counts toward the ceiling, a typed REFUSAL
    counts against it (recorded, never hidden), WRONG always fails the gate.

`--mutate-gt` perturbs every stated ground truth by 10% and must make the run FAIL
with the solved instances landing in WRONG — the wrong-number detector's own
demonstrated failure. `--corrupt-wire` flips one numeric token after checksums are
computed and must make the run FAIL with a PARSE_FAIL — the wire-fidelity detector's
demonstrated failure. `--fill-gt` stamps referee-proven optima into seed instance
files that carry none yet.

Timing is reported with the host load average beside it, because a wall-clock number
without the load that produced it is not reproducible evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
INSTANCES = HERE / "instances"
BUILD = REPO / "build" / "optmodel_plane"
RUNNER = BUILD / "runner_generated.mojo"
MIRROR_DEFAULT = BUILD / "mirror_instances.json"

SENSES = {"<=": 0, "==": 1, ">=": 2}
KINDS = {"continuous": 0, "integer": 1, "binary": 2}
GT_ABS_TOL = 1e-6
GT_REL_TOL = 1e-6
# The benchmark's published rule: default numeric tolerance 1e-6; continuous-objective
# location families (reference objectives rounded to 4 decimals) get an absolute floor
# of 1e-3. Instances carry `paper_floor` when the floor applies.
PAPER_REL_TOL = 1e-6


def load_seed_instances() -> list[dict]:
    paths = sorted(INSTANCES.glob("*.json"))
    if not paths:
        raise SystemExit(f"no instances under {INSTANCES}")
    return [json.loads(p.read_text(encoding="utf-8")) for p in paths]


def load_mirror_instances(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(
            f"no mirror at {path} — run make_mirror_instances.py first"
        )
    instances = json.loads(path.read_text(encoding="utf-8"))
    for inst in instances:
        if inst.get("expect") != "measure":
            raise SystemExit(f"{inst['id']}: mirror instances must declare "
                             f"expect=measure, got {inst.get('expect')!r}")
    return instances


def flat_form(inst: dict) -> dict:
    """Compile one instance to the plane's flat wire form."""
    names = [v["name"] for v in inst["variables"]]
    index = {n: j for j, n in enumerate(names)}
    if len(index) != len(names):
        raise SystemExit(f"{inst['id']}: duplicate variable name")
    n_vars = len(names)
    cons = inst["constraints"]
    n_cons = len(cons)

    c = [0.0] * n_vars
    for name, coef in inst["objective"]["coeffs"].items():
        c[index[name]] = float(coef)
    a = [0.0] * (n_cons * n_vars)
    senses, rhs = [], []
    for i, row in enumerate(cons):
        for name, coef in row["coeffs"].items():
            a[i * n_vars + index[name]] = float(coef)
        senses.append(SENSES[row["sense"]])
        rhs.append(float(row["rhs"]))

    kind, lower, upper, flags = [], [], [], []
    for v in inst["variables"]:
        k = KINDS[v["kind"]]
        lo = v.get("lower", 0.0)
        up = v.get("upper")
        if v["kind"] == "binary":
            lo = 0.0 if lo is None else lo
            up = 1.0 if up is None else up
        flag = 0
        if lo is not None:
            flag |= 1
        if up is not None:
            flag |= 2
        kind.append(k)
        lower.append(0.0 if lo is None else float(lo))
        upper.append(0.0 if up is None else float(up))
        flags.append(flag)

    return {
        "n_vars": n_vars, "n_cons": n_cons,
        "maximize": bool(inst["maximize"]),
        "c": c, "c0": float(inst["objective"].get("constant", 0.0)),
        "a": a, "senses": senses, "rhs": rhs,
        "kind": kind, "lower": lower, "upper": upper, "flags": flags,
        "max_nodes": int(inst.get("max_nodes", 10000)),
    }


def referee(inst: dict) -> tuple[str, float | None]:
    """Independent HiGHS re-solve. Returns (status, optimum-or-None)."""
    f = flat_form(inst)
    n = f["n_vars"]
    sign = -1.0 if f["maximize"] else 1.0
    c = sign * np.asarray(f["c"], dtype=float)

    lb = np.full(f["n_cons"], -np.inf)
    ub = np.full(f["n_cons"], np.inf)
    for i, s in enumerate(f["senses"]):
        if s == 0:
            ub[i] = f["rhs"][i]
        elif s == 2:
            lb[i] = f["rhs"][i]
        else:
            lb[i] = ub[i] = f["rhs"][i]
    a = np.asarray(f["a"], dtype=float).reshape(f["n_cons"], n)

    var_lb = np.full(n, -np.inf)
    var_ub = np.full(n, np.inf)
    for j, (flag, lo, up) in enumerate(zip(f["flags"], f["lower"], f["upper"])):
        if flag & 1:
            var_lb[j] = lo
        if flag & 2:
            var_ub[j] = up
    integrality = np.asarray([1 if k != 0 else 0 for k in f["kind"]])

    constraints = [LinearConstraint(a, lb, ub)] if f["n_cons"] else []
    res = milp(c=c, constraints=constraints, integrality=integrality,
               bounds=Bounds(var_lb, var_ub))
    if res.status == 0:
        return "optimal", sign * float(res.fun) + f["c0"]
    if res.status == 2:
        return "infeasible", None
    if res.status == 3:
        return "unbounded", None
    return f"referee_status_{res.status}", None


def _referee_one(inst: dict) -> tuple[str, str, float | None]:
    status, optimum = referee(inst)
    return inst["id"], status, optimum


def run_referee(instances: list[dict], workers: int) -> dict[str, tuple[str, float | None]]:
    if workers <= 1 or len(instances) < 8:
        return {i["id"]: referee(i) for i in instances}
    out: dict[str, tuple[str, float | None]] = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for iid, status, optimum in pool.map(_referee_one, instances, chunksize=8):
            out[iid] = (status, optimum)
    return out


# ── wire format ────────────────────────────────────────────────────────────────
# Whitespace tokens. Header: OPTMWIRE1 <n_instances>. Per instance:
#   INST <id> <n_vars> <n_cons> <maximize> <c0> <gt> <max_nodes> <nnz> <ntok> <sumabs>
# then c (n_vars), senses (n_cons), rhs (n_cons), kind/lower/upper/flags (n_vars each),
# and nnz sparse triplets (row col value) for the constraint matrix. `ntok` is the
# exact numeric token count of the body and `sumabs` the |value| sum in emission
# order; the runner recomputes both, so a dropped, duplicated, or altered token is a
# typed PARSE_FAIL rather than a silently different model.

def _fmt(x: float) -> str:
    return repr(float(x))


def wire_instance(inst: dict) -> str:
    f = flat_form(inst)
    gt = float(inst.get("ground_truth", {}).get("objective", 0.0))
    body: list[str] = []
    body += [_fmt(v) for v in f["c"]]
    body += [str(int(s)) for s in f["senses"]]
    body += [_fmt(v) for v in f["rhs"]]
    body += [str(int(k)) for k in f["kind"]]
    body += [_fmt(v) for v in f["lower"]]
    body += [_fmt(v) for v in f["upper"]]
    body += [str(int(x)) for x in f["flags"]]
    triplets = []
    n = f["n_vars"]
    for i in range(f["n_cons"]):
        for j in range(n):
            v = f["a"][i * n + j]
            if v != 0.0:
                triplets += [str(i), str(j), _fmt(v)]
    body += triplets
    sumabs = 0.0
    for tok in body:
        sumabs += abs(float(tok))
    header = (
        f"INST {inst['id']} {f['n_vars']} {f['n_cons']} "
        f"{1 if f['maximize'] else 0} {_fmt(f['c0'])} {_fmt(gt)} "
        f"{f['max_nodes']} {len(triplets) // 3} {len(body)} {_fmt(sumabs)}"
    )
    return header + "\n" + "\n".join(" ".join(body[k:k + 12])
                                     for k in range(0, len(body), 12))


def emit_wires(instances: list[dict], chunk_size: int) -> list[tuple[Path, list[str]]]:
    BUILD.mkdir(parents=True, exist_ok=True)
    chunks: list[tuple[Path, list[str]]] = []
    for start in range(0, len(instances), chunk_size):
        part = instances[start:start + chunk_size]
        path = BUILD / f"wire_{len(chunks):03d}.txt"
        text = f"OPTMWIRE1 {len(part)}\n" + "\n".join(wire_instance(i) for i in part)
        path.write_text(text + "\n", encoding="utf-8")
        chunks.append((path, [i["id"] for i in part]))
    return chunks


RUNNER_SOURCE = '''\
"""GENERATED by benchmarks/optmodel_plane/harness.py — do not edit.

Parses an OPTMWIRE1 file (path = argv[1]) and pushes every instance through
`optmodel.judge.formulation_verdict_default`, printing one RESULT line each.
"""
from sys import argv
from time import perf_counter_ns

from optmodel.judge import formulation_verdict_default
from optmodel.formulation import optm_status_name, optm_verdict_name


fn fail(msg: String):
    print("PARSE_FAIL " + msg)


fn main() raises:
    var args = argv()
    if len(args) < 2:
        fail("no wire path")
        return
    var f = open(String(args[1]), "r")
    var content = f.read()
    f.close()
    var toks = content.split()
    if len(toks) < 2 or String(toks[0]) != "OPTMWIRE1":
        fail("bad magic")
        return
    var n_instances = atol(toks[1])
    var pos = 2
    for _ in range(n_instances):
        if pos + 11 > len(toks) or String(toks[pos]) != "INST":
            fail("bad frame at token " + String(pos))
            return
        var id = String(toks[pos + 1])
        var n_vars = atol(toks[pos + 2])
        var n_cons = atol(toks[pos + 3])
        var maximize = atol(toks[pos + 4]) == 1
        var c0 = atof(toks[pos + 5])
        var gt = atof(toks[pos + 6])
        var max_nodes = atol(toks[pos + 7])
        var nnz = atol(toks[pos + 8])
        var ntok = atol(toks[pos + 9])
        var sumabs_stated = atof(toks[pos + 10])
        pos += 11
        var expected = 5 * n_vars + 2 * n_cons + 3 * nnz
        if ntok != expected or pos + ntok > len(toks):
            fail(id + " token count " + String(ntok) + " vs " + String(expected))
            return
        var sumabs = 0.0
        var c = List[Float64]()
        for k in range(n_vars):
            c.append(atof(toks[pos + k]))
            sumabs += abs(c[k])
        pos += n_vars
        var senses = List[Int]()
        for k in range(n_cons):
            senses.append(atol(toks[pos + k]))
            sumabs += abs(Float64(senses[k]))
        pos += n_cons
        var rhs = List[Float64]()
        for k in range(n_cons):
            rhs.append(atof(toks[pos + k]))
            sumabs += abs(rhs[k])
        pos += n_cons
        var kind = List[Int]()
        for k in range(n_vars):
            kind.append(atol(toks[pos + k]))
            sumabs += abs(Float64(kind[k]))
        pos += n_vars
        var lower = List[Float64]()
        for k in range(n_vars):
            lower.append(atof(toks[pos + k]))
            sumabs += abs(lower[k])
        pos += n_vars
        var upper = List[Float64]()
        for k in range(n_vars):
            upper.append(atof(toks[pos + k]))
            sumabs += abs(upper[k])
        pos += n_vars
        var flags = List[Int]()
        for k in range(n_vars):
            flags.append(atol(toks[pos + k]))
            sumabs += abs(Float64(flags[k]))
        pos += n_vars
        var a = List[Float64]()
        for _ in range(n_cons * n_vars):
            a.append(0.0)
        for _ in range(nnz):
            var i = atol(toks[pos])
            var j = atol(toks[pos + 1])
            var v = atof(toks[pos + 2])
            sumabs += abs(Float64(i)) + abs(Float64(j)) + abs(v)
            if i < 0 or i >= n_cons or j < 0 or j >= n_vars:
                fail(id + " triplet out of range")
                return
            a[i * n_vars + j] = v
            pos += 3
        var scale = abs(sumabs_stated)
        if scale < 1.0:
            scale = 1.0
        if abs(sumabs - sumabs_stated) > 1e-9 * scale:
            fail(id + " checksum " + String(sumabs) + " vs " + String(sumabs_stated))
            return
        var t0 = perf_counter_ns()
        var v = formulation_verdict_default(
            n_vars, n_cons, maximize, c, c0, a, senses, rhs, kind,
            lower, upper, flags, gt, max_nodes,
        )
        var ms = Float64(perf_counter_ns() - t0) / 1e6
        var objective = String("NA")
        if v.has_objective:
            objective = String(v.objective)
        print(
            "RESULT id=" + id
            + " strict=" + optm_verdict_name(v.verdict_strict)
            + " lineage=" + optm_verdict_name(v.verdict_lineage)
            + " status=" + v.message
            + " under=" + optm_status_name(v.underlying_status)
            + " objective=" + objective
            + " nodes=" + String(v.nodes_explored)
            + " iters=" + String(v.lp_iterations)
            + " ms=" + String(ms)
        )
    print("OPTMODEL_PLANE done")
'''


def emit_runner() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    RUNNER.write_text(RUNNER_SOURCE, encoding="utf-8")


def parse_runner_output(stdout: str) -> tuple[dict[str, dict], list[str], bool]:
    results: dict[str, dict] = {}
    parse_failures: list[str] = []
    for line in stdout.splitlines():
        if line.startswith("PARSE_FAIL "):
            parse_failures.append(line[len("PARSE_FAIL "):])
        if not line.startswith("RESULT "):
            continue
        fields = dict(part.split("=", 1) for part in line[len("RESULT "):].split(" "))
        results[fields["id"]] = fields
    completed = "OPTMODEL_PLANE done" in stdout
    return results, parse_failures, completed


def run_mojo_chunk(wire: Path, timeout: int) -> tuple[dict[str, dict], list[str], bool]:
    """Run one wire chunk. Returns (results, parse_failures, completed).

    The runner's stdout streams to `<wire>.log` so a long chunk can be tailed live
    and a post-mortem always has the per-instance trace.
    """
    mojo_env = Path(os.environ.get("MOJO_ENV_DIR", REPO / "mojo_env"))
    engine = REPO / "mojo" / "engine"
    log_path = wire.with_suffix(".log")
    with open(log_path, "w", encoding="utf-8") as log:
        subprocess.run(
            ["pixi", "run", "mojo", "run", "-I", str(engine), str(RUNNER), str(wire)],
            cwd=mojo_env, stdout=log, stderr=subprocess.STDOUT, text=True,
            timeout=timeout,
        )
    results, parse_failures, completed = parse_runner_output(
        log_path.read_text(encoding="utf-8"))
    if not completed and not parse_failures:
        sys.stderr.write(log_path.read_text(encoding="utf-8")[-2000:])
    return results, parse_failures, completed


def paper_rule_matches(objective: float, gt: float, floor: float) -> bool:
    tol = max(PAPER_REL_TOL * max(1.0, abs(gt)), floor)
    return abs(objective - gt) <= tol


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fill-gt", action="store_true",
                        help="stamp referee optima into seed instances missing ground truth")
    parser.add_argument("--mutate-gt", action="store_true",
                        help="perturb every ground truth by 10%% — the gate must FAIL")
    parser.add_argument("--corrupt-wire", action="store_true",
                        help="flip one wire token after checksumming — the gate must FAIL")
    parser.add_argument("--mirror", nargs="?", const=str(MIRROR_DEFAULT), default=None,
                        help="also load the generated benchmark mirror (default path "
                             "build/optmodel_plane/mirror_instances.json)")
    parser.add_argument("--seeds-only", action="store_true",
                        help="run only the curated seed instances")
    parser.add_argument("--filter", default=None,
                        help="run only instances whose id contains this substring")
    parser.add_argument("--chunk-size", type=int, default=130)
    parser.add_argument("--chunk-timeout", type=int, default=5400)
    parser.add_argument("--referee-workers", type=int, default=4)
    parser.add_argument("--parallel-chunks", type=int, default=1,
                        help="concurrent mojo chunk runs (each is single-threaded)")
    parser.add_argument("--resume", action="store_true",
                        help="reuse complete chunk logs from an interrupted run "
                             "(identical instance set and chunking required)")
    args = parser.parse_args()

    instances = load_seed_instances()
    if args.mirror and not args.seeds_only:
        instances = instances + load_mirror_instances(Path(args.mirror))
    if args.filter:
        instances = [i for i in instances if args.filter in i["id"]]
        if not instances:
            raise SystemExit(f"--filter {args.filter!r} matched nothing")
    failures: list[str] = []

    # ── referee: admit instances only on independent proof ────────────────────
    started_ref = time.monotonic()
    verdicts = run_referee(instances, args.referee_workers)
    ref_elapsed = time.monotonic() - started_ref
    for inst in instances:
        status, optimum = verdicts[inst["id"]]
        expectation = inst.get("referee_expectation", "optimal")
        if status != expectation:
            failures.append(
                f"{inst['id']}: referee says {status}, instance claims {expectation}"
            )
            continue
        if expectation != "optimal":
            continue
        stated = inst.get("ground_truth", {}).get("objective")
        if stated is None:
            if args.fill_gt and inst["expect"] == "verified":
                inst["ground_truth"] = {
                    "objective": round(optimum, 9),
                    "source": "referee:scipy-highs",
                }
                path = INSTANCES / f"{inst['id']}.json"
                path.write_text(json.dumps(inst, indent=2) + "\n", encoding="utf-8")
                print(f"stamped {inst['id']}: {inst['ground_truth']['objective']}")
            elif inst["expect"] in ("verified", "measure"):
                failures.append(f"{inst['id']}: no ground truth (run --fill-gt)")
        else:
            gap = abs(optimum - stated)
            if gap > GT_ABS_TOL + GT_REL_TOL * max(1.0, abs(stated)):
                failures.append(
                    f"{inst['id']}: stated truth {stated} but referee proves {optimum}"
                )
    load = ", ".join(f"{x:.2f}" for x in os.getloadavg())
    print(f"referee: {len(instances)} instances re-proved in {ref_elapsed:.1f}s "
          f"(HiGHS, workers={args.referee_workers}), loadavg [{load}]")
    if args.fill_gt:
        print("fill-gt complete" if not failures else "fill-gt found problems:")
        for f in failures:
            print(f"  ❌ {f}")
        raise SystemExit(1 if failures else 0)
    if failures:
        for f in failures:
            print(f"  ❌ {f}")
        raise SystemExit("referee refused the instance set; nothing was run")

    # ── the gate's own demonstrated failure modes ──────────────────────────────
    if args.mutate_gt:
        for inst in instances:
            gt = inst.get("ground_truth", {}).get("objective")
            if gt is not None:
                inst["ground_truth"]["objective"] = gt * 1.1 + 1.0
        print("MUTATION: every ground truth perturbed — this run must FAIL")

    # ── run the plane ──────────────────────────────────────────────────────────
    emit_runner()
    # Deterministic interleave: chunking the authored order would give one chunk
    # all the deep-search instances of a family; hashing spreads them evenly.
    run_order = sorted(
        instances,
        key=lambda i: hashlib.sha1(i["id"].encode("utf-8")).hexdigest())
    chunks = emit_wires(run_order, args.chunk_size)
    if args.corrupt_wire:
        path, _ = chunks[0]
        toks = path.read_text(encoding="utf-8").split()
        # Flip the first numeric body token (position 13: right after the first
        # 11-token INST header and the 2-token magic).
        toks[13] = repr(float(toks[13]) + 7.0)
        path.write_text(" ".join(toks) + "\n", encoding="utf-8")
        print("CORRUPTION: one wire token flipped after checksumming — "
              "this run must FAIL with a PARSE_FAIL")

    results: dict[str, dict] = {}
    gate: list[str] = []
    started = time.monotonic()

    def _one_chunk(k_wire_ids):
        k, (wire, ids) = k_wire_ids
        t0 = time.monotonic()
        if args.resume:
            # An interrupted measurement leaves complete chunk logs behind; the
            # wire emission is deterministic, so a log that answers every id of
            # its chunk and reached the done marker is this same measurement.
            log = wire.with_suffix(".log")
            if log.exists():
                results, pf, completed = parse_runner_output(
                    log.read_text(encoding="utf-8"))
                if completed and not pf and all(i in results for i in ids):
                    return k, ids, results, pf, completed, 0.0
        chunk_results, parse_failures, completed = run_mojo_chunk(
            wire, args.chunk_timeout)
        return k, ids, chunk_results, parse_failures, completed, \
            time.monotonic() - t0

    with ThreadPoolExecutor(max_workers=max(1, args.parallel_chunks)) as pool:
        for k, ids, chunk_results, parse_failures, completed, dt in pool.map(
                _one_chunk, enumerate(chunks)):
            results.update(chunk_results)
            for msg in parse_failures:
                gate.append(f"chunk {k}: PARSE_FAIL {msg}")
            if not completed and not parse_failures:
                gate.append(f"chunk {k}: mojo runner did not complete")
            print(f"chunk {k}: {len(chunk_results)}/{len(ids)} results in {dt:.1f}s")
    elapsed = time.monotonic() - started
    load = ", ".join(f"{x:.2f}" for x in os.getloadavg())
    print(f"mojo run: {elapsed:.1f}s wall over {len(chunks)} chunk(s) "
          f"(compile + solve), loadavg [{load}]")

    # ── classify and gate ──────────────────────────────────────────────────────
    fam_table: dict[str, dict[str, int]] = {}
    sub_table: dict[tuple[str, str, str], dict[str, int]] = {}
    refusal_reasons: dict[str, int] = {}
    for inst in instances:
        r = results.get(inst["id"])
        expect = inst["expect"]
        family = inst["family"]
        subcategory = inst.get("subcategory", family)
        difficulty = inst.get("difficulty", "seed")
        row = fam_table.setdefault(
            family, {"verified": 0, "refused": 0, "wrong": 0, "n": 0})
        srow = sub_table.setdefault(
            (family, subcategory, difficulty),
            {"verified": 0, "refused": 0, "wrong": 0, "n": 0})
        row["n"] += 1
        srow["n"] += 1
        if r is None:
            gate.append(f"{inst['id']}: no RESULT line from the runner")
            row["wrong"] += 1
            srow["wrong"] += 1
            continue
        bucket = r["strict"]
        row[bucket] = row.get(bucket, 0) + 1
        srow[bucket] = srow.get(bucket, 0) + 1
        if bucket == "wrong":
            gate.append(
                f"{inst['id']}: WRONG — plane says {r['objective']}, "
                f"truth {inst.get('ground_truth', {}).get('objective')} ({r['status']})"
            )
        elif expect in ("verified", "refused") and bucket != expect:
            gate.append(
                f"{inst['id']}: expected {expect}, got {bucket} ({r['status']})"
            )
        if bucket == "refused":
            refusal_reasons[r["status"]] = refusal_reasons.get(r["status"], 0) + 1
        if bucket == "verified" and not args.mutate_gt:
            gt = float(inst["ground_truth"]["objective"])
            floor = float(inst.get("paper_floor", 0.0))
            if not paper_rule_matches(float(r["objective"]), gt, floor):
                gate.append(
                    f"{inst['id']}: verified at strict tolerance but MISSES the "
                    f"benchmark rule (plane {r['objective']}, truth {gt}, "
                    f"floor {floor})"
                )

    print()
    print(f"{'family':<26}{'n':>5}{'verified':>10}{'refused':>9}{'wrong':>7}")
    totals = {"n": 0, "verified": 0, "refused": 0, "wrong": 0}
    for family in sorted(fam_table):
        row = fam_table[family]
        print(f"{family:<26}{row['n']:>5}{row['verified']:>10}"
              f"{row['refused']:>9}{row['wrong']:>7}")
        for k in totals:
            totals[k] += row.get(k, 0)
    print(f"{'TOTAL':<26}{totals['n']:>5}{totals['verified']:>10}"
          f"{totals['refused']:>9}{totals['wrong']:>7}")

    if any(key[2] != "seed" for key in sub_table):
        print()
        print(f"{'subcategory':<26}{'tier':>7}{'n':>4}{'verified':>10}"
              f"{'refused':>9}{'wrong':>7}")
        for key in sorted(sub_table):
            family, subcategory, difficulty = key
            if difficulty == "seed":
                continue
            srow = sub_table[key]
            print(f"{subcategory:<26}{difficulty:>7}{srow['n']:>4}"
                  f"{srow['verified']:>10}{srow['refused']:>9}{srow['wrong']:>7}")

    solvable = sum(1 for i in instances if i["expect"] in ("verified", "measure"))
    print(f"\nsolver-side ceiling: {totals['verified']}/{solvable} "
          f"ground-truth formulations solved AND verified (strict 1e-4 relative "
          f"+ benchmark tolerance rule); wrong-number count: {totals['wrong']}")
    if refusal_reasons:
        reasons = ", ".join(f"{k} x{v}" for k, v in sorted(refusal_reasons.items()))
        print(f"typed refusals: {reasons}")
    coverage_gaps = [i["id"] for i in instances if "coverage_gap" in i]
    if coverage_gaps:
        print(f"counted coverage gaps (refused by design): {', '.join(coverage_gaps)}")

    if gate:
        print(f"\nOPTMODEL_PLANE_GATE FAIL ({len(gate)} violations)")
        for g in gate[:60]:
            print(f"  ❌ {g}")
        if len(gate) > 60:
            print(f"  … and {len(gate) - 60} more")
        raise SystemExit(1)
    print("\nOPTMODEL_PLANE_GATE PASS")


if __name__ == "__main__":
    main()
