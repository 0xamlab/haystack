#!/usr/bin/env python3
"""summarize_front5.py — assemble the FRONT-5 A/B tables from the driver's own bench logs.

Round 4's `summarize_front4.py` is 596 lines and carries a per-cell schema that crashed on the
RAG pass (`KeyError: 'prefill256'`, phase2.log STAGE 3). This summarizer is deliberately small
and reads exactly one thing: the lines the driver already prints, which are the measurement of
record. It does not re-derive, smooth or interpolate anything.

Inputs (all under --meas):
    bench_<arm>_ra<N>.log     the interleaved pp256/pp1024/decode sweep, one process per arm
    bench_<arm>_rag<i>.log    the RAG-4096 cells, one process per (arm, prompt)
    trtllm_rerace5.json       the freshly re-served TensorRT-LLM 1.2.1 cells

What it reports:
  * per-arm cells with the driver's own rel-IQR and outlier count, and the 1.0% target verdict
  * baseline drift = the LAST bracketing baseline run against the FIRST (drift armor); every
    lever delta must exceed it to count
  * lever deltas for each non-baseline arm against the bracketing baseline
  * RAG-4096 ms + tok/s per prompt per arm, the ratio against the re-served TRT-LLM cell, and
    the re-serve's own reproduction against round 4's stored cell (1% -> SAME-SESSION, else
    CROSS-SESSION, labelled not averaged away)
  * the TC FLAGS banner and the G0/G1 gate line per run, so no cell can be quoted without its
    gate attached
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CELLS = ["prefill256", "prefill1024", "gen64", "gen256"]
IQR_TARGET = 1.0
# round 4's RE-SERVED TRT-LLM 1.2.1 cells, in ms — the reproduction reference
STORED_TRTLLM_MS = {"pp256": 34.9442253112793, "pp1024": 71.40003204345703,
                    "rag4096": 270.2759094238281}

RE_CELL = re.compile(
    r"^(prefill256|prefill1024|gen 64|gen 256|prefill4096):\s*median ([\d.]+) tok/s"
    r"\s*\|\s*IQR ([\d.]+) %\s*\|\s*outliers (\d+)\s*\|\s*(\w+)")
RE_G0 = re.compile(r"G0 RESULT:\s*(.*)")
RE_G1 = re.compile(r"G1 RESULT:\s*(.*)")
RE_FLAGS = re.compile(r"TC FLAGS:\s*(.*)")
RE_PREFILL_MS = re.compile(r"^prefill4096:\s*median ([\d.]+) tok/s")

NAME_MAP = {"gen 64": "gen64", "gen 256": "gen256", "prefill4096": "prefill4096"}


def parse_bench(path: Path) -> dict:
    out = {"cells": {}, "G0": None, "G1": None, "flags": None, "log": str(path)}
    if not path.exists():
        return out
    for line in path.read_text(errors="replace").splitlines():
        m = RE_CELL.match(line.strip())
        if m:
            key = NAME_MAP.get(m.group(1), m.group(1))
            out["cells"][key] = {
                "tok_s": float(m.group(2)), "rel_iqr_pct": float(m.group(3)),
                "outliers": int(m.group(4)), "verdict": m.group(5),
                "iqr_over_target": float(m.group(3)) > IQR_TARGET,
            }
            continue
        for key, pat in (("G0", RE_G0), ("G1", RE_G1), ("flags", RE_FLAGS)):
            m2 = pat.search(line)
            if m2 and out[key] is None:
                out[key] = m2.group(1).strip()
    return out


def rag_ms(tok_s: float, n_tokens: int = 4096) -> float:
    return n_tokens / tok_s * 1000.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meas", required=True, help="artifact dir (e.g. ~/trtllm/front5)")
    ap.add_argument("--baseline", default="_e3")
    ap.add_argument("--arms", nargs="*", default=["_f1"])
    ap.add_argument("--rerace", default=None)
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()
    meas = Path(a.meas).expanduser()

    result: dict = {"baseline_arm": a.baseline, "iqr_target_pct": IQR_TARGET, "sweep": {}}

    # ── the sweep: every baseline run (drift armor) plus each lever arm ──
    base_runs = []
    for p in sorted(meas.glob(f"bench_{a.baseline}_ra*.log")):
        base_runs.append((p.stem.replace("bench_", ""), parse_bench(p)))
    if not base_runs:
        print(f"NO BASELINE RUNS under {meas}", file=sys.stderr)
        return 2
    first, last = base_runs[0][1], base_runs[-1][1]
    drift = {}
    for c in CELLS:
        if c in first["cells"] and c in last["cells"]:
            f, l = first["cells"][c]["tok_s"], last["cells"][c]["tok_s"]
            drift[c] = (l - f) / f * 100.0
    result["baseline_drift_pct"] = drift
    result["baseline_runs"] = [
        {"tag": t, "cells": {c: r["cells"][c]["tok_s"] for c in CELLS if c in r["cells"]},
         "G0": r["G0"], "G1": r["G1"]} for t, r in base_runs]

    print(f"== baseline {a.baseline}: {len(base_runs)} bracketing run(s), drift armor ==")
    for t, r in base_runs:
        cs = " ".join(f"{c}={r['cells'][c]['tok_s']:.1f}" for c in CELLS if c in r["cells"])
        print(f"  {t:14s} {cs}")
        print(f"                 G0={r['G0']} | G1={r['G1']}")
    print("  drift (last vs first), %: " +
          " ".join(f"{c}={drift[c]:+.4f}" for c in CELLS if c in drift))

    base = last  # the bracketing baseline the deltas are taken against
    for c in CELLS:
        if c in base["cells"] and base["cells"][c]["iqr_over_target"]:
            print(f"  NOTE: baseline {c} rel-IQR {base['cells'][c]['rel_iqr_pct']:.3f}% "
                  f"exceeds the {IQR_TARGET}% target — reported, not discarded")

    deltas = {}
    for arm in a.arms:
        runs = sorted(meas.glob(f"bench_{arm}_ra*.log"))
        if not runs:
            print(f"\n== {arm}: no sweep runs found ==")
            continue
        r = parse_bench(runs[-1])
        result["sweep"][arm] = r
        print(f"\n== lever arm {arm} ({runs[-1].name}) ==")
        print(f"  flags: {r['flags']}")
        print(f"  G0={r['G0']} | G1={r['G1']}")
        deltas[arm] = {}
        for c in CELLS:
            if c not in r["cells"] or c not in base["cells"]:
                continue
            t, b = r["cells"][c]["tok_s"], base["cells"][c]["tok_s"]
            d = (t - b) / b * 100.0
            exceeds = c in drift and abs(d) > abs(drift[c])
            deltas[arm][c] = {"tok_s": t, "base_tok_s": b, "delta_pct": d,
                              "rel_iqr_pct": r["cells"][c]["rel_iqr_pct"],
                              "outliers": r["cells"][c]["outliers"],
                              "exceeds_baseline_drift": exceeds}
            flag = "" if exceeds else "  (within baseline drift — NOT a win)"
            over = ("  IQR>1%" if r["cells"][c]["iqr_over_target"] else "")
            print(f"  {c:12s} {t:10.1f} vs {b:10.1f}  {d:+7.3f}%{flag}{over}")
    result["lever_deltas"] = deltas

    # ── RAG-4096 ──
    rag = {}
    for arm in [a.baseline] + list(a.arms):
        per = {}
        for p in sorted(meas.glob(f"bench_{arm}_rag*.log")):
            i = p.stem.rsplit("rag", 1)[-1]
            r = parse_bench(p)
            if "prefill4096" in r["cells"]:
                ts = r["cells"]["prefill4096"]["tok_s"]
                per[i] = {"tok_s": ts, "ms": rag_ms(ts),
                          "rel_iqr_pct": r["cells"]["prefill4096"]["rel_iqr_pct"],
                          "G1": r["G1"], "log": str(p)}
        if per:
            rag[arm] = per
    result["rag4096"] = rag
    if rag:
        print("\n== RAG-4096 (4096-token prefill, per prompt) ==")
        for arm, per in rag.items():
            for i, v in sorted(per.items()):
                over = "  IQR>1%" if v["rel_iqr_pct"] > IQR_TARGET else ""
                print(f"  {arm:6s} prompt {i}: {v['ms']:8.3f} ms  {v['tok_s']:9.1f} tok/s  "
                      f"rel-IQR {v['rel_iqr_pct']:.3f}%{over}  {v['G1']}")
        if a.baseline in rag:
            for arm in a.arms:
                if arm not in rag:
                    continue
                ds = []
                for i, v in rag[arm].items():
                    if i in rag[a.baseline]:
                        b = rag[a.baseline][i]
                        ds.append((v["tok_s"] - b["tok_s"]) / b["tok_s"] * 100.0)
                        print(f"  delta {arm} vs {a.baseline} prompt {i}: {ds[-1]:+.3f}%  "
                              f"({b['ms']:.3f} -> {v['ms']:.3f} ms)")
                if ds:
                    result.setdefault("rag4096_deltas", {})[arm] = {
                        "per_prompt_pct": ds, "mean_pct": sum(ds) / len(ds)}
                    print(f"  delta {arm} MEAN: {sum(ds)/len(ds):+.3f}%")

    # ── the re-race against a freshly re-served TensorRT-LLM ──
    rr_path = Path(a.rerace).expanduser() if a.rerace else meas / "trtllm_rerace5.json"
    if rr_path.exists():
        rr = json.loads(rr_path.read_text())
        result["rerace"] = {"source": str(rr_path)}
        cells = rr.get("cells", {})
        print(f"\n== RE-RACE vs freshly re-served TensorRT-LLM 1.2.1 ({rr_path.name}) ==")
        out_cells = {}
        for name, key_arm in (("pp256", "prefill256"), ("pp1024", "prefill1024")):
            if name not in cells:
                continue
            c = cells[name]
            arm = a.arms[0] if a.arms and a.arms[0] in result.get("sweep", {}) else a.baseline
            src = result["sweep"].get(arm, base)
            if key_arm not in src["cells"]:
                continue
            ours = src["cells"][key_arm]["tok_s"]
            ratio = ours / c["trtllm_tok_s"] if c.get("trtllm_tok_s") else None
            stored = STORED_TRTLLM_MS.get(name)
            rep = ((c["trtllm_ms"] - stored) / stored * 100.0) if stored else None
            basis = ("SAME-SESSION" if rep is not None and abs(rep) <= 1.0 else "CROSS-SESSION")
            out_cells[name] = {"algenta_arm": arm, "algenta_tok_s": ours,
                               "algenta_ms": c.get("algenta_ms"),
                               "trtllm_ms": c["trtllm_ms"], "ratio_tok_s": ratio,
                               "verdict": "WIN" if ratio and ratio >= 1.0 else "LOSS",
                               "resere_vs_stored_pct": rep, "basis": basis}
            print(f"  {name:8s} arm={arm} ours={ours:.1f} tok/s  theirs={c['trtllm_ms']:.3f} ms"
                  f"  ratio={ratio:.4f}x  {out_cells[name]['verdict']}"
                  f"  re-serve vs round-4 stored {rep:+.3f}% -> {basis}")
        if "rag4096" in cells:
            c = cells["rag4096"]
            per = c.get("per_prompt") or []
            arm = a.arms[0] if a.arms and a.arms[0] in rag else a.baseline
            rows = []
            for row in per:
                i = str(row.get("prompt"))
                if arm in rag and i in rag[arm]:
                    ours_ms = rag[arm][i]["ms"]
                    ours_ts = rag[arm][i]["tok_s"]
                else:
                    ours_ms, ours_ts = row.get("algenta_ms"), row.get("algenta_tok_s")
                ratio = (ours_ts / row["trtllm_tok_s"]) if (ours_ts and row.get("trtllm_tok_s")) else None
                rows.append({"prompt": i, "algenta_ms": ours_ms, "algenta_tok_s": ours_ts,
                             "trtllm_ms": row.get("trtllm_ms"), "ratio_tok_s": ratio,
                             "verdict": "WIN" if ratio and ratio >= 1.0 else "LOSS"})
                print(f"  rag4096 #{i} ours={ours_ms:.3f} ms ({ours_ts:.1f} tok/s)  "
                      f"theirs={row.get('trtllm_ms'):.3f} ms  ratio={ratio:.4f}x  "
                      f"{rows[-1]['verdict']}")
            stored = STORED_TRTLLM_MS["rag4096"]
            tms = per[0].get("trtllm_ms") if per else None
            rep = ((tms - stored) / stored * 100.0) if tms else None
            basis = ("SAME-SESSION" if rep is not None and abs(rep) <= 1.0 else "CROSS-SESSION")
            out_cells["rag4096"] = {"algenta_arm": arm, "per_prompt": rows,
                                    "resere_vs_stored_pct": rep, "basis": basis}
            if rep is not None:
                print(f"  rag4096 re-serve vs round-4 stored 270.276 ms: {rep:+.3f}% -> {basis}")
        result["rerace"]["cells"] = out_cells
    else:
        print(f"\n(no re-race JSON at {rr_path} — ratios NOT computed; a ratio without a "
              f"same-session re-serve is not a ratio)")

    if a.json_out:
        Path(a.json_out).write_text(json.dumps(result, indent=1))
        print(f"\nwrote {a.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
