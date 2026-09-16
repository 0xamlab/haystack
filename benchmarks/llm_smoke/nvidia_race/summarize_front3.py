#!/usr/bin/env python3
"""summarize_front3.py — assemble FRONT 3's measured tables from the arm logs.

Reads every `bench_<arm>_ra<N>.log` (the pp256/pp1024/decode sweep) and `rag<i>_<arm>.log`
(the three token-exact 4096-token prompts) the A/B harness wrote, extracts the driver's own
median-of-20 cells plus its rel-IQR/outlier verdict and the G0/G1 gate lines, and emits one
JSON with:

  * per-arm cells, so every number in the PR table traces to a named log file;
  * per-lever deltas against the _c8 baseline arm (round 2's adopted configuration, rebuilt
    from THIS branch so the baseline is not a remembered number);
  * the drift between the bracketing _c8 runs, which is the honesty check on the whole sweep —
    a lever whose "win" is smaller than the baseline's own drift is not a win;
  * the re-race ratios against a freshly re-served TensorRT-LLM 1.2.1 when `--trtllm` points at
    that race's JSON, and the flip verdict (pp1024 >= 1.0 AND RAG-4096 >= 1.0).

Nothing here re-times anything: every cell is the driver's own median, parsed verbatim. A log
that is missing a cell yields `null`, never a guess.

usage:
  summarize_front3.py --meas ~/trtllm/front3 --out ~/trtllm/front3/front3_results.json \
      [--trtllm ~/trtllm/front3/trtllm_rerace3.json] [--baseline _c8]
"""

import argparse
import json
import re
import sys
from pathlib import Path

CELL_RE = re.compile(
    r"^(prefill\d+|gen \d+)\s*: median ([\d.]+) tok/s \| IQR ([\d.]+) % \| outliers (\d+)"
    r" \| (\w+)"
)
FLAG_RE = re.compile(r"^TCFLAG (\S+)")
KV_RE = re.compile(r"([A-Za-z_0-9]+) = (\S+)")


def cell_name(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("gen"):
        return "gen" + raw.split()[1]
    return raw


def parse_log(path: Path) -> dict:
    txt = path.read_text(errors="replace")
    out = {
        "log": str(path),
        "cells": {},
        "G0": None,
        "G1": None,
        "flags": [],
        "tc_flags_banner": None,
        "fa_verdict": None,
        "max_ctx": None,
        "load_ms": None,
        "stage_ms": None,
    }
    for line in txt.splitlines():
        m = CELL_RE.match(line.strip())
        if m:
            out["cells"][cell_name(m.group(1))] = {
                "tok_s": float(m.group(2)),
                "rel_iqr_pct": float(m.group(3)),
                "outliers": int(m.group(4)),
                "verdict": m.group(5),
            }
            continue
        s = line.strip()
        if s.startswith("G0 RESULT:"):
            out["G0"] = "PASS" if "PASS" in s else "FAIL"
        elif s.startswith("G1 RESULT:"):
            mm = re.search(r"(\d+)\s*/\s*(\d+)", s)
            out["G1"] = (
                "PASS" if ("PASS" in s and mm and mm.group(1) == mm.group(2)) else "FAIL"
            ) + (f" {mm.group(1)}/{mm.group(2)}" if mm else "")
        elif s.startswith("TCFLAG "):
            out["flags"].append(FLAG_RE.match(s).group(1).split("=")[0])
        elif s.startswith("TC FLAGS:"):
            out["tc_flags_banner"] = s
            kv = dict(KV_RE.findall(s))
            out["max_ctx"] = int(kv["max_ctx"]) if "max_ctx" in kv else None
        elif "flash attention ARMED" in s or "flash attention DECLINED" in s:
            out["fa_verdict"] = s
        elif "one-time load" in s:
            mm = re.search(r"([\d.]+) ms", s)
            if mm:
                out["load_ms"] = float(mm.group(1))
        elif "dual residency STAGED" in s:
            mm = re.search(r"\|\s*([\d.]+) ms one-time", s)
            if mm:
                out["stage_ms"] = float(mm.group(1))
    return out


def tok(cell: dict, name: str):
    if not cell:
        return None
    c = cell.get("cells", {}).get(name)
    return c["tok_s"] if c else None


def ms_per(cell: dict, name: str, n_tokens: int):
    """Device-side ms for a prefill cell: n_tokens / (tok/s) * 1000. The driver reports the
    prefill cells in tok/s over the prompt it just ran, so this is the same basis the round-2
    re-race used to compare against TRT-LLM's engine-side step time."""
    t = tok(cell, name)
    return None if not t else n_tokens / t * 1000.0


def pct(new, base):
    if new is None or base in (None, 0):
        return None
    return 100.0 * (new - base) / base


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meas", default="/home/angel/trtllm/front3")
    ap.add_argument("--out", default="/home/angel/trtllm/front3/front3_results.json")
    ap.add_argument("--trtllm", default="")
    ap.add_argument("--baseline", default="_c8")
    ap.add_argument("--ship", default="_d8", help="the arm the re-race ratios are computed for")
    ap.add_argument("--round", default="ra1", dest="rnd")
    args = ap.parse_args()

    meas = Path(args.meas)
    arms = {}
    for p in sorted(meas.glob(f"bench_*_{args.rnd}.log")):
        arm = p.name[len("bench_") : -len(f"_{args.rnd}.log")]
        arms.setdefault(arm, []).append(parse_log(p))
    rags = {}
    for p in sorted(meas.glob("bench_*_rag*.log")):
        m = re.match(r"bench_(.+)_rag(\d+)\.log$", p.name)
        if not m:
            continue
        rags.setdefault(m.group(1), {})[int(m.group(2))] = parse_log(p)

    # The interleaved sweep brackets with the baseline, and both bracketing runs write the SAME
    # per-arm log path, so only the later one survives on disk. The harness's own stdout keeps
    # both in order — parse it so the drift between the two baselines (the honesty check on the
    # whole sweep) is a number in the artifact rather than a claim.
    ordered: dict = {}
    for sl in sorted(meas.glob("sweep*.log")):
        cur = None
        for line in sl.read_text(errors="replace").splitlines():
            s = line.strip()
            mh = re.match(r"^== (\S+?) rc=(\d+) wall=(\d+)s clocks=(.+)$", s)
            if mh:
                cur = {
                    "arm": mh.group(1),
                    "rc": int(mh.group(2)),
                    "wall_s": int(mh.group(3)),
                    "clocks": mh.group(4),
                    "cells": {},
                    "G0": None,
                    "G1": None,
                    "flags": [],
                    "log": str(sl),
                }
                key = re.sub(r"_(ra|rag)\d+$", "", mh.group(1))
                ordered.setdefault(key, []).append(cur)
                continue
            if cur is None:
                continue
            mc = CELL_RE.match(s)
            if mc:
                cur["cells"][cell_name(mc.group(1))] = {
                    "tok_s": float(mc.group(2)),
                    "rel_iqr_pct": float(mc.group(3)),
                    "outliers": int(mc.group(4)),
                    "verdict": mc.group(5),
                }
            elif s.startswith("G0 RESULT:"):
                cur["G0"] = "PASS" if "PASS" in s else "FAIL"
            elif s.startswith("G1 RESULT:"):
                mm = re.search(r"(\d+)\s*/\s*(\d+)", s)
                cur["G1"] = (
                    "PASS" if ("PASS" in s and mm and mm.group(1) == mm.group(2)) else "FAIL"
                ) + (f" {mm.group(1)}/{mm.group(2)}" if mm else "")

    base_runs = arms.get(args.baseline, [])
    if not base_runs:
        print(f"no baseline arm '{args.baseline}' logs in {meas}", file=sys.stderr)
        return 1
    base = base_runs[0]
    # drift armor: the sweep brackets with the baseline, so its LAST run is the drift probe.
    # Prefer the ordered harness-log parse (which still sees both brackets) over the per-arm
    # files (where the second run overwrote the first).
    cells4 = ("prefill256", "prefill1024", "gen64", "gen256")
    br = ordered.get(args.baseline, [])
    drift = None
    if len(br) > 1:
        drift = {c: pct(tok(br[-1], c), tok(br[0], c)) for c in cells4}
        drift["baseline_runs_tok_s"] = [{c: tok(r, c) for c in cells4} for r in br]
    elif len(base_runs) > 1:
        drift = {c: pct(tok(base_runs[-1], c), tok(base_runs[0], c)) for c in cells4}

    result = {
        "meta": {
            "front": "FRONT 3 — flip the pp1024 (0.925x) and RAG-4096 (0.769x) losses vs "
            "TensorRT-LLM 1.2.1 by attacking the measured #1 layer gap",
            "vm": "algenta-ent-a100 (GCP a2-highgpu-1g, 1x A100-SXM4-40GB, solo GPU)",
            "clocks": "1410 MHz pinned; read before and after every cell by the harness",
            "baseline_arm": args.baseline,
            "baseline_basis": "round 2's adopted _c8 configuration REBUILT from this branch, "
            "not a remembered number",
            "protocol": "one process per arm; each cell is the driver's own median of --runs "
            "20 with rel-IQR and outlier reporting; arms interleaved with the "
            "baseline bracketing the sweep; G0 (16/16 greedy vs the fp32 "
            "transformers oracle) and G1 (64/64 self-consistency) run inside "
            "every process",
            "arms": {
                "_c8": "round 2 baseline: ONEPASS_B1+FLASH_B1+FLASH2_B1+TC_NOSEAM+TCATTN+"
                "TC_SHIM+SM1P+F16NORM+F16MLP+CTX8192",
                "_d1": "_c8 + ALGENTA_7B_PF_FA (fused causal FlashAttention-2)",
                "_d2": "_c8 + ALGENTA_7B_PF_FASTEXP (SwiGLU on shim __expf)",
                "_d3": "_c8 + ALGENTA_7B_PF_BIASROPE (qkv bias folded into RoPE+KV-write)",
                "_d4": "_c8 + FA + FASTEXP",
                "_d8": "_c8 + FA + FASTEXP + BIASROPE (the full stack)",
            },
        },
        "baseline_drift_pct": drift,
        "sweep": {a: runs[0] for a, runs in arms.items()},
        "sweep_ordered_runs": ordered,
        "sweep_reruns": {a: runs[1:] for a, runs in arms.items() if len(runs) > 1},
        "rag4096": rags,
        "per_lever_delta_pct_vs_baseline": {},
        "cells": {},
    }

    for arm, runs in arms.items():
        r = runs[0]
        d = {}
        for c in ("prefill256", "prefill1024", "gen64", "gen256"):
            d[c] = {
                "tok_s": tok(r, c),
                "delta_pct_vs_baseline": pct(tok(r, c), tok(base, c)),
                "rel_iqr_pct": (r["cells"].get(c) or {}).get("rel_iqr_pct"),
                "verdict": (r["cells"].get(c) or {}).get("verdict"),
                "G0": r["G0"],
                "G1": r["G1"],
            }
        result["per_lever_delta_pct_vs_baseline"][arm] = d

    # the raced cells, in the round-2 re-race's own units
    result["cells"]["pp256"] = {
        a: {"algenta_tok_s": tok(r[0], "prefill256"), "algenta_ms": ms_per(r[0], "prefill256", 256)}
        for a, r in arms.items()
    }
    result["cells"]["pp1024"] = {
        a: {
            "algenta_tok_s": tok(r[0], "prefill1024"),
            "algenta_ms": ms_per(r[0], "prefill1024", 1024),
        }
        for a, r in arms.items()
    }
    result["cells"]["decode_c1_gen256"] = {
        a: {"algenta_tok_s": tok(r[0], "gen256")} for a, r in arms.items()
    }
    rag_cell = {}
    for arm, prompts in rags.items():
        rag_cell[arm] = {
            f"prompt{i}": {
                "algenta_tok_s": tok(p, "prefill4096"),
                "algenta_ms": ms_per(p, "prefill4096", 4096),
                "rel_iqr_pct": (p["cells"].get("prefill4096") or {}).get("rel_iqr_pct"),
                "G1": p["G1"],
                "log": p["log"],
            }
            for i, p in sorted(prompts.items())
        }
    result["cells"]["rag4096"] = rag_cell

    # ── the re-race against a freshly re-served TensorRT-LLM 1.2.1 ──
    # `--trtllm` is trtllm_race.py's own output: cells keyed pp256/pp1024/rag0/rag1/rag2, each
    # with `server` (executor iter-log device step time — the basis round 2 raced on) and
    # `client` (streaming SSE TTFT), plus an optional top-level `decode`.
    if args.trtllm and Path(args.trtllm).exists():
        t = json.loads(Path(args.trtllm).read_text())
        tcells = t.get("cells", {})

        def tget(name):
            c = (tcells.get(name) or {}).get("server") or {}
            return c.get("prefill_tok_s"), c.get("median_ms"), c.get("rel_iqr_pct")

        ship = args.ship if args.ship in arms else ("_d8" if "_d8" in arms else max(arms))
        race = {}
        for cell, tname, aname, ntok in (
            ("pp256", "pp256", "prefill256", 256),
            ("pp1024", "pp1024", "prefill1024", 1024),
        ):
            ours = tok(arms[ship][0], aname)
            theirs, tms, tiqr = tget(tname)
            race[cell] = {
                "algenta_tok_s": ours,
                "algenta_ms": ms_per(arms[ship][0], aname, ntok),
                "trtllm_server_tok_s": theirs,
                "trtllm_server_ms": tms,
                "trtllm_rel_iqr_pct": tiqr,
                "ratio_algenta_over_trtllm": (ours / theirs if ours and theirs else None),
                "basis": "algenta = driver-internal median of 20 device-side runs; "
                "trtllm = executor iter-log device step time, median of 7 measured "
                "(3 warmup excluded), cells interleaved round-robin",
            }
        dec = t.get("decode") or {}
        ours_dec = tok(arms[ship][0], "gen256")
        race["decode_c1_gen256"] = {
            "algenta_tok_s": ours_dec,
            "trtllm_tok_s": dec.get("tok_s_median"),
            "ratio_algenta_over_trtllm": (
                ours_dec / dec["tok_s_median"] if ours_dec and dec.get("tok_s_median") else None
            ),
            "basis": "algenta = driver median of 20 gen256 runs; trtllm = streaming "
            "inter-token rate over 3 warm decode passes",
        }
        for i in sorted(rags.get(ship, {})):
            p = rags[ship][i]
            ours = tok(p, "prefill4096")
            theirs, tms, tiqr = tget(f"rag{i}")
            race[f"rag4096_prompt{i}"] = {
                "algenta_tok_s": ours,
                "algenta_ms": ms_per(p, "prefill4096", 4096),
                "trtllm_server_tok_s": theirs,
                "trtllm_server_ms": tms,
                "trtllm_rel_iqr_pct": tiqr,
                "ratio_algenta_over_trtllm": (ours / theirs if ours and theirs else None),
                "algenta_rel_iqr_pct": (p["cells"].get("prefill4096") or {}).get("rel_iqr_pct"),
                "algenta_G1": p["G1"],
            }
        r_pp = race["pp1024"]["ratio_algenta_over_trtllm"]
        r_rag = [
            v["ratio_algenta_over_trtllm"]
            for k, v in race.items()
            if k.startswith("rag4096") and v.get("ratio_algenta_over_trtllm")
        ]
        dec_now = race["decode_c1_gen256"]["algenta_tok_s"] or 0
        result["rerace"] = {
            "ship_arm": ship,
            "trtllm_source": args.trtllm,
            "trtllm_meta": t.get("meta", {}),
            "cells": race,
            "flip_pp1024": (r_pp is not None and r_pp >= 1.0),
            "flip_rag4096": (bool(r_rag) and all(x >= 1.0 for x in r_rag)),
            "pp256_still_won": (race["pp256"]["ratio_algenta_over_trtllm"] or 0) >= 1.0,
            "decode_invariant_held": abs(dec_now - 82.8) <= 0.5,
            "decode_tok_s": dec_now,
        }
        result["rerace"]["VERDICT"] = (
            "FLIPPED"
            if result["rerace"]["flip_pp1024"] and result["rerace"]["flip_rag4096"]
            else "NOT FLIPPED"
        )
    else:
        result["rerace"] = {"note": "no --trtllm JSON supplied; re-race pending"}

    Path(args.out).write_text(json.dumps(result, indent=1))
    print(f"wrote {args.out}")

    # ── the console tables ──
    print("\n== per-arm cells (driver median of 20, tok/s) ==")
    print(
        f"{'arm':<6}{'pp256':>12}{'pp1024':>12}{'gen64':>10}{'gen256':>10}"
        f"{'G0':>6}{'G1':>10}  flags"
    )
    for a, runs in arms.items():
        r = runs[0]
        print(
            f"{a:<6}{tok(r, 'prefill256') or 0:>12.1f}{tok(r, 'prefill1024') or 0:>12.1f}"
            f"{tok(r, 'gen64') or 0:>10.2f}{tok(r, 'gen256') or 0:>10.2f}"
            f"{(r['G0'] or '-'):>6}{(r['G1'] or '-'):>10}  "
            f"{','.join(f.replace('ALGENTA_', '') for f in r['flags'])}"
        )
    print("\n== per-lever delta vs the _c8 baseline (%) ==")
    print(f"{'arm':<6}{'pp256':>10}{'pp1024':>10}{'gen64':>10}{'gen256':>10}")
    cells4 = ("prefill256", "prefill1024", "gen64", "gen256")
    for a, d in result["per_lever_delta_pct_vs_baseline"].items():
        row = "".join(f"{(d[c]['delta_pct_vs_baseline'] or 0.0):>10.2f}" for c in cells4)
        print(f"{a:<6}" + row)
    if drift:
        print("\n== baseline drift between the two bracketing _c8 runs (%) ==")
        print(
            "  "
            + "  ".join(
                f"{k}={v:+.2f}" for k, v in drift.items() if isinstance(v, float) and v is not None
            )
        )
    if rag_cell:
        print("\n== RAG-4096 (tok/s, driver median of 20) ==")
        for a, ps in rag_cell.items():
            print(
                f"  {a:<6}"
                + "  ".join(
                    f"p{k}={v['algenta_tok_s']:.1f}" for k, v in ps.items() if v["algenta_tok_s"]
                )
            )
    if "cells" in result.get("rerace", {}):
        print("\n== RE-RACE vs TensorRT-LLM 1.2.1 (freshly re-served) ==")
        print(f"{'cell':<22}{'algenta':>12}{'trtllm':>12}{'ratio':>9}")
        for k, v in result["rerace"]["cells"].items():
            theirs = v.get("trtllm_tok_s", v.get("trtllm_server_tok_s"))
            print(
                f"{k:<22}{(v['algenta_tok_s'] or 0):>12.1f}"
                f"{(theirs or 0):>12.1f}"
                f"{(v['ratio_algenta_over_trtllm'] or 0):>9.4f}"
            )
        rr = result["rerace"]
        print(
            f"\n  ship arm {rr['ship_arm']}: pp1024 flipped={rr['flip_pp1024']} "
            f"rag4096 flipped={rr['flip_rag4096']} pp256 still won={rr['pp256_still_won']} "
            f"decode invariant held={rr['decode_invariant_held']} "
            f"({rr['decode_tok_s']:.2f} tok/s) -> {rr['VERDICT']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
