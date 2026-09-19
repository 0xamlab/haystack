#!/usr/bin/env python3
"""summarize_gemma3_round6.py -- ROUND-6 A/B table for the gemma-3-27b-it H200 prefill seam.

Arms are built from ~/g3r6 (the feat/gemma-fa2-port worktree) against the STOCK
unmodified driver ~/adj/build/driver_ctx8192.mojo, so nothing about the harness contributes
to any number here. The tc_shim object is compiled from that same tree's tc_shim.cu.

  R6_base  PR #998's ship candidate (= round 5's R5_all2): the full five-lever stack
           FA + F16ATTN + F16NORM + F16MLP + ROPE2, rebuilt from the round-6 branch
  R6_fa2   R6_base + -D ALGENTA_G3_PF_FA2       the raw-mma v2 window kernel (in-register P,
           direct epilogue, cp.async double buffer on the f16 K/V route)

Method (the owner's protocol, and the reason this script exists rather than a one-liner):
  * 3 warmup + 7 measured per cell, arms INTERLEAVED run-by-run within each prompt group;
  * arm A is re-run twice at the END of each group, so the group is A..B..A and the
    bracketing drift is MEASURED, not assumed away. A lever delta that does not exceed that
    drift is reported as NOT RESOLVED rather than as a win;
  * clocks are read before and after every cell and a 1 Hz sampler runs during it; any cell
    with an off-pin sample is listed by name;
  * rel-IQR is reported per cell with the outliers listed, not hidden behind the median.

TRT-LLM 1.2.1 comparator: the same-session re-serve in ~/lever6/runs/trtllm_*.json when it
exists; otherwise the stored H200 column, explicitly labelled CROSS-SESSION.

prefill tok/s = raw token-exact prompt id count / TTFT, on both sides.
"""
import json
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

L6 = Path(os.environ.get("MEAS", "/home/angel/lever6"))
RUNS = L6 / "runs"
RR = Path(os.environ.get("RERACE", "/home/angel/trtllm/gemma_rerace"))
CELLS = {"pp256": 256, "pp1024": 1024, "rag4096": 4096}
# the reference TRT-LLM column: round 5's SAME-SESSION re-serve (2026-09-16 ~17:09Z,
# lv3_trtllm.sh, the numbers the 1.2931/1.1038/1.0135 ratios were computed against). This
# round's own re-serve must reproduce it within 1% or the ratio is labelled CROSS-SESSION.
STORED_TRT = {"pp256": 41.520, "pp1024": 110.782, "rag4096": 426.766}
ARMS = sys.argv[1:] or ["R6_base", "R6_fa2"]
ARM_A = ARMS[0]


def q(xs, p):
    xs = sorted(xs)
    return xs[max(0, min(len(xs) - 1, int(round((p / 100.0) * (len(xs) - 1)))))]


def stats(xs):
    if not xs:
        return None
    med = statistics.median(xs)
    iqr = q(xs, 75) - q(xs, 25)
    return {"n": len(xs), "median": round(med, 3),
            "q1": round(q(xs, 25), 3), "q3": round(q(xs, 75), 3),
            "iqr": round(iqr, 3),
            "rel_iqr_pct": round(iqr / med * 100, 3) if med else None,
            "rel_iqr_le_1pct": bool(med and iqr / med * 100 <= 1.0),
            "min": round(min(xs), 3), "max": round(max(xs), 3),
            "spread_pct": round((max(xs) - min(xs)) / med * 100, 3) if med else None,
            "outliers_gt5pct": [round(x, 3) for x in xs if med and abs(x - med) / med > 0.05],
            "runs": [round(x, 3) for x in xs]}


def dj(path):
    if not path.exists():
        return {}
    for line in reversed(path.read_text(errors="replace").splitlines()):
        line = line.strip()
        if line.startswith("{") and '"generated"' in line:
            try:
                return json.loads(line)
            except Exception:
                pass
    return {}


def ttft(label):
    d = dj(RUNS / f"{label}.out")
    if d.get("stalled"):
        return None, "STALLED"
    t = d.get("ttft_ms")
    if t is None:
        return None, "NO-JSON"
    return float(t), None


def clocks(label):
    f = L6 / "clocks" / f"clocks_{label}.csv"
    if not f.exists():
        return None
    cl, off = [], 0
    for line in f.read_text(errors="replace").splitlines():
        if " " not in line:
            continue
        try:
            c = float(line.split(None, 1)[1].split(",")[0].split()[0])
        except Exception:
            continue
        cl.append(c)
        if c != 1410.0:
            off += 1
    if not cl:
        return None
    return {"n_samples": len(cl), "min": min(cl), "max": max(cl), "off_pin": off,
            "all_pinned_1410": off == 0}


def trt_column():
    """Same-session re-serve if it exists, else the stored column labelled CROSS-SESSION.

    `tl_prefill_client.py` writes {"label", "config", "ttft_ms": {"n","median","runs",...},
    "e2e_ms": {...}, ...}; the TTFT median is the raced quantity on both sides."""
    out, src, detail = {}, None, {}
    for name in ("pp256", "pp1024", "rag4096"):
        cands = sorted(RUNS.glob(f"trtllm_{name}.json"))
        for c in cands:
            try:
                d = json.loads(c.read_text(errors="replace"))
            except Exception:
                continue
            blk = d.get("ttft_ms") or {}
            med = blk.get("median")
            if med is None and isinstance(blk.get("runs"), list) and blk["runs"]:
                med = statistics.median([float(x) for x in blk["runs"]])
            if med is not None:
                out[name] = round(float(med), 3)
                mt = datetime.fromtimestamp(c.stat().st_mtime, timezone.utc)
                detail[name] = {"file": str(c), "n": blk.get("n"),
                                "runs": blk.get("runs"),
                                "label": d.get("label"),
                                "file_mtime_utc": mt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "config": {k: d.get("config", {}).get(k) for k in
                                           ("model", "max_tokens", "warmup", "measured",
                                            "prompt_raw_id_count", "ignore_eos")}}
                break
    if out:
        # The mtime is IN the label on purpose. "Same-session" is a claim about when the server
        # ran relative to the algenta cells, and a stale trtllm_*.json left in the runs directory
        # by an earlier chain satisfies the glob just as happily as this chain's own re-serve.
        # Printing the timestamp makes a mismatched comparator visible instead of asserted --
        # which matters here because this round's cells straddle an instance stop/start.
        spans = sorted(v["file_mtime_utc"] for v in detail.values())
        src = (f"re-serve in {RUNS}/trtllm_*.json, file mtime {spans[0]}"
               + (f" .. {spans[-1]}" if len(spans) > 1 else "")
               + " -- verify this is the same session as the algenta cells being compared")
    else:
        out = dict(STORED_TRT)
        src = ("CROSS-SESSION stored column (round 5's same-session re-serve, "
               "2026-09-16T17:09Z) -- NOT re-served this session")
    return out, src, detail


def main():
    trt, trt_src, trt_detail = trt_column()
    # protocol: a same-session re-serve must REPRODUCE the stored column within 1%, else the
    # ratio is labelled cross-session rather than quietly compared against a drifted server.
    # The check is only meaningful when a re-serve actually exists -- comparing the stored
    # column against itself would print "+0.000% reproduces within 1%" for a session in which
    # TRT-LLM was never served, which is precisely the kind of line that makes a cross-session
    # ratio look same-session.
    repro = {}
    if trt_detail:
        for k, v in trt.items():
            s = STORED_TRT.get(k)
            if s:
                repro[k] = {"re_served_ms": v, "stored_ms": s,
                            "delta_pct": round((v - s) / s * 100, 3),
                            "within_1pct": abs((v - s) / s * 100) <= 1.0}
    res = {"title": "round-6 gemma-3-27b-it H200 prefill A/B -- raw-mma v2 of the fused "
                    "windowed TC flash attention on top of #998's five-lever stack",
           "arms": ARMS, "arm_a_bracket": ARM_A,
           "driver": "~/adj/build/driver_ctx8192.mojo (STOCK, unmodified)",
           "source_tree": "~/g3r6 (feat/gemma-fa2-port, based on feat/gemma-fused-tc-attn)",
           "trtllm": {"version": "1.2.1", "source": trt_src, "ttft_ms": trt,
                      "reproduction_vs_stored": repro, "detail": trt_detail},
           "cells": {}, "off_pin_cells": [], "stalled_or_missing": []}

    # the gate verdicts and the strings-based flag audit travel WITH the numbers: a cell is only
    # a measurement if the arm that produced it was token-exact and provably carried the flags.
    #
    # HASH-BINDING, added in round 14 after a real trap: the gate file is named
    # `oracle_gate_<ARM>.json`, so the verdict is keyed by ARM NAME and an arm that was REBUILT IN
    # PLACE silently inherits the previous binary's ALL_PASS line. Round 14 printed
    # `R9_both ALL_PASS=True` for a binary whose hash had just changed from the certified
    # ca66b41a2ee34cde to 3c70880f9fe95910 — the gate belonged to the older one. So capture
    # whatever hash the gate JSON records and, at print time, compare it against the flag audit's
    # sha256_16 for the same arm; a mismatch or a missing hash is reported next to the verdict
    # rather than being allowed to imply a certification the timed binary never earned.
    gates = {}
    for arm in ARMS:
        p = L6 / f"oracle_gate_{arm}.json"
        if p.exists():
            try:
                g = json.loads(p.read_text())
            except Exception:
                continue
            gh = None
            for k in ("sha256_16", "sha256", "arm_sha256_16", "binary_sha256_16", "hash"):
                if g.get(k):
                    gh = str(g[k])[:16]
                    break
            gates[arm] = {"all_pass": g.get("all_pass"),
                          "gate_sha256_16": gh,
                          "verdicts": {k: {kk: vv.get("verdict")
                                           for kk, vv in v.items() if isinstance(vv, dict)}
                                       for k, v in (g.get("cells") or {}).items()}}
    res["oracle_gates"] = gates
    fa = L6 / "flag_audit.json"
    if fa.exists():
        try:
            res["flag_audit"] = json.loads(fa.read_text())
        except Exception:
            pass

    # LABEL DISCOVERY, NOT ENUMERATION. Round 14 found three silent-exclusion defects in the
    # hard-coded lists that used to be here, all from the same root cause:
    #   * the tag list was ("", "b", "c"), so a window run with a NEW CELLTAG (r6e_) reported
    #     "no measured runs" for a bracket that had in fact completed 22 cells, and emitted ~80
    #     bogus `r6e_*:NO-JSON` STALLED/MISSING entries that sent the reader hunting for cells
    #     that all existed;
    #   * the measured range was hard-coded r1..r7, so any bracket shape beyond it was truncated;
    #   * warm and close were enumerated the same way, so the CLOSING cells were never found and
    #     `bracket_drift_pct` was silently absent — a median printed with NO drift armor behind it
    #     and nothing saying so. That is the defect that made round 14's pp256/pp1024 rows
    #     unpublishable despite a complete, clean bracket.
    # Discovering from the filesystem cannot go stale when a round invents a tag or a bracket shape.
    def discover(arm, name, kind):
        found = set()
        for ext in ("out", "json"):
            for p in RUNS.glob(f"r6*_{arm}_{name}_{kind}*.{ext}"):
                found.add(p.name.rsplit(".", 1)[0])
        return sorted(found)

    for name, ntok in CELLS.items():
        cell = {"prompt_tokens": ntok, "arms": {}}
        base_med = None
        for arm in ARMS:
            labels = discover(arm, name, "r")
            xs, bad = [], []
            for lb in labels:
                t, why = ttft(lb)
                if t is None:
                    bad.append(f"{lb}:{why}")
                else:
                    xs.append(t)
                c = clocks(lb)
                if c and not c["all_pinned_1410"]:
                    res["off_pin_cells"].append({"label": lb, **c})
            warm = [ttft(lb)[0] for lb in discover(arm, name, "warm")]
            close = [ttft(lb)[0] for lb in discover(arm, name, "close")]
            warm = [w for w in warm if w is not None]
            close = [c for c in close if c is not None]
            st = stats(xs)
            if st is None:
                res["stalled_or_missing"].append({"arm": arm, "prompt": name, "why": bad})
                continue
            entry = dict(st)
            entry["warmup_n"] = len(warm)
            entry["warmup_median"] = round(statistics.median(warm), 3) if warm else None
            entry["closing_bracket_n"] = len(close)
            entry["closing_bracket_median"] = round(statistics.median(close), 3) if close else None
            if close and xs:
                entry["bracket_drift_pct"] = round(
                    (statistics.median(close) - st["median"]) / st["median"] * 100, 3)
            entry["ttft_ms"] = st["median"]
            entry["prefill_tok_s"] = round(ntok / (st["median"] / 1000.0), 2)
            if trt.get(name):
                entry["trtllm_ttft_ms"] = trt[name]
                entry["ratio_trt_over_ours"] = round(trt[name] / st["median"], 4)
                entry["verdict"] = "WIN" if trt[name] / st["median"] >= 1.0 else "LOSS"
                entry["gap_ms"] = round(st["median"] - trt[name], 3)
            cell["arms"][arm] = entry
            if arm == ARM_A:
                base_med = st["median"]
        if base_med:
            drift = abs(cell["arms"][ARM_A].get("bracket_drift_pct", 0.0)) / 100.0 * base_med
            # record the drift on the bracketing arm itself too, so the table can print the
            # armor it is comparing every delta against (not only the ratio to it)
            cell["arms"][ARM_A]["bracket_drift_ms"] = round(drift, 3)
            for arm in ARMS:
                if arm == ARM_A or arm not in cell["arms"]:
                    continue
                e = cell["arms"][arm]
                d = e["median"] - base_med
                e["delta_vs_bracket_ms"] = round(d, 3)
                e["delta_vs_bracket_pct"] = round(d / base_med * 100, 3)
                e["bracket_drift_ms"] = round(drift, 3)
                e["exceeds_bracket_drift"] = bool(abs(d) > drift)
                e["resolved"] = ("YES" if abs(d) > drift and drift > 0
                                 else ("NO-DRIFT-MEASURED" if drift == 0 else "NOT-RESOLVED"))
        res["cells"][name] = cell

    (L6 / "lever6_results.json").write_text(json.dumps(res, indent=2))

    # ── the human table ──
    print("\n=== ROUND-6 gemma-3-27b-it H200 PREFILL A/B (clocks pinned 1410 MHz) ===")
    print(f"TRT-LLM 1.2.1 comparator: {trt_src}")
    for k in ("pp256", "pp1024", "rag4096"):
        r = repro.get(k)
        if r:
            print(f"  {k:<9} re-served {r['re_served_ms']:>9.3f} ms vs stored "
                  f"{r['stored_ms']:>9.3f} ms = {r['delta_pct']:+.3f}% "
                  f"{'(reproduces within 1%)' if r['within_1pct'] else '(>1% -- CROSS-SESSION)'}")
    hdr = f"{'prompt':<9}{'arm':<10}{'n':>3} {'median ms':>10} {'rel-IQR%':>9} {'tok/s':>9} " \
          f"{'vs TRT':>8} {'verdict':>8} {'d vs A ms':>10} {'resolved':>10}"
    print(hdr)
    print("-" * len(hdr))
    for name in CELLS:
        c = res["cells"].get(name, {})
        for arm in ARMS:
            e = c.get("arms", {}).get(arm)
            if not e:
                print(f"{name:<9}{arm:<10}  -- no measured runs --")
                continue
            print(f"{name:<9}{arm:<10}{e['n']:>3} {e['median']:>10.3f} "
                  f"{(e['rel_iqr_pct'] or 0):>9.3f} {e['prefill_tok_s']:>9.1f} "
                  f"{e.get('ratio_trt_over_ours', 0):>8.4f} {e.get('verdict', '-'):>8} "
                  f"{e.get('delta_vs_bracket_ms', 0):>10.3f} {e.get('resolved', '-'):>10}")
        t = c.get("arms", {}).get(ARM_A, {})
        if t.get("bracket_drift_pct") is not None:
            print(f"{name:<9}{'':<10}    bracket drift on {ARM_A}: "
                  f"{t['bracket_drift_pct']:+.3f}% "
                  f"({t.get('bracket_drift_ms', 0):.3f} ms) "
                  f"[open {t['median']:.3f} -> close {t['closing_bracket_median']:.3f}]")
        print()
    if res["off_pin_cells"]:
        print("OFF-PIN CLOCKS (reported honestly, not dropped):")
        for c in res["off_pin_cells"]:
            print(f"  {c['label']}: {c['off_pin']}/{c['n_samples']} samples off 1410 MHz "
                  f"(min {c['min']} max {c['max']})")
    else:
        print("CLOCKS: every measured cell 1410 MHz on every 1 Hz sample (zero drift).")
    if res["stalled_or_missing"]:
        print("STALLED / MISSING CELLS:")
        for s in res["stalled_or_missing"]:
            print(f"  {s['arm']} {s['prompt']}: {s['why']}")
    if res.get("oracle_gates"):
        # sha256_16 of the binary the flag audit actually saw this window, per arm name
        audited = {a.get("arm"): a.get("sha256_16")
                   for a in (res.get("flag_audit") or {}).get("arms", [])}
        print("\nORACLE GATES (cache-free fp32 transformers oracle; must pass BEFORE any speed claim):")
        for arm, g in res["oracle_gates"].items():
            vs = []
            for p, cells in (g.get("verdicts") or {}).items():
                for k, v in cells.items():
                    if v:
                        vs.append(f"{p}/{k}: {v}")
            print(f"  {arm:<9} ALL_PASS={g['all_pass']}  " + " | ".join(vs))
            # The verdict above is keyed by ARM NAME. Say out loud which BINARY it belongs to, so a
            # rebuild-in-place cannot quietly borrow the previous binary's certification.
            gh, ah = g.get("gate_sha256_16"), audited.get(arm)
            if gh and ah:
                print(f"            gate hash {gh} vs audited binary {ah}: "
                      + ("MATCH — the certification is the timed binary's"
                         if gh == ah else
                         "MISMATCH — THIS GATE BELONGS TO A DIFFERENT BINARY than the one "
                         "audited/timed; do not cite it for these numbers"))
            elif ah:
                print(f"            gate JSON records NO hash; audited binary is {ah} — the "
                      f"certification is NOT hash-bound to it, verify separately before citing")
            else:
                print("            gate JSON records NO hash and this arm was not in the flag "
                      "audit — the certification is NOT bound to any binary in this window")
    if res.get("flag_audit"):
        print("\nFLAG AUDIT (strings on the shipped binary; positive control per family):")
        for a in res["flag_audit"].get("arms", []):
            print(f"  {a['arm']:<9} {a.get('family')} sha256_16={a.get('sha256_16')} "
                  f"[{', '.join(f.replace('ALGENTA_', '') for f in a.get('flags_in_binary', []))}]")
            if a.get("fa_verdict"):
                print(f"            {a['fa_verdict']}")
            if a.get("fa2_verdict"):
                print(f"            {a['fa2_verdict']}")
    print(f"\nWROTE {L6 / 'lever6_results.json'}")


if __name__ == "__main__":
    main()
