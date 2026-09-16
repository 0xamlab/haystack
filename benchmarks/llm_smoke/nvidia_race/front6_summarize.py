#!/usr/bin/env python3
"""front6_summarize.py -- the FRONT 6 result table, parsed from the stage logs.

Reads the interleaved A/B stage logs (which `run_arm` already reduces to one `== <arm><tag>`
header plus the grepped gate/cell lines) and the TRT-LLM re-serve JSON, and emits:

  * per arm per cell: median tok/s, rel-IQR, outliers, G0, G1, clocks before->after
  * the baseline BRACKET drift (first vs last `_g0` of the same sweep) -- round 2's drift armor
  * the TRT-LLM re-serve checked against round 5's stored cells, labelled SAME-SESSION or
    CROSS-SESSION at the owner's 1% threshold rather than averaged away
  * the ratio table and the RAG-4096 flip verdict
  * the zero-drift clock audit over the 1 Hz sampler window

Round 4 shipped a summarizer with the pp256/pp1024 ratio INVERTED and two WINS printed as
losses; it was caught only because 0.94x pp1024 contradicted a prior round on an axis the round
had not touched. So every ratio here is printed with its direction stated in words, and the
pp256/pp1024 columns are cross-checked against FRONT 5's published ratios (1.788x / 1.085x) on
axes these levers cannot touch by construction.

Usage: front6_summarize.py <artifact_dir> [--trtllm json] [--clocks csv]
"""

from __future__ import annotations

import json
import re
import sys
from collections import OrderedDict

# round 5's published ratios, used ONLY as a sanity check on axes these levers cannot move
FRONT5_RATIOS = {"pp256": 1.788, "pp1024": 1.085, "decode": 1.043}
# round 5's same-session TRT-LLM 1.2.1 re-serve (server median ms). A round-6 re-serve more
# than 1% away from these is CROSS-SESSION and must be labelled, not blended.
TRTLLM_R5_MS = {"pp256": 35.491329193115234, "pp1024": 71.93449401855469,
                "rag": 272.16607666015625}
# the raced prompt lengths
CELL_TOKENS = {"pp256": 256, "pp1024": 1024, "prefill4096": 4096}

# The clock field carries units and a space ("clocks=1410 MHz->1410 MHz"), so `(\S+)->(\S+)`
# can never match it -- the first version of this regex parsed ZERO cells out of six stage logs
# and the summarizer exited with "no stage logs parsed" while the stage itself was fine.
HDR = re.compile(r"^== (_g\d)(\S*) rc=(\d+) wall=(\d+)s clocks=(.*?)->(.*?) vram_after=(.*?)\s*$")
CELL = re.compile(r"^(prefill\d+|gen \d+)\s*: median ([\d.]+) tok/s \| IQR ([\d.]+) % \| "
                  r"outliers (\d+) \| (\w+)")
G0 = re.compile(r"^G0 RESULT: (PASS|FAIL)[^\d]*(\d+)?")
G1 = re.compile(r"^G1 RESULT: (PASS|FAIL)\s*[^\d]*(\d+)\s*/\s*(\d+)")
FLAGLINE = re.compile(r"(pass_max = \d+|ROPEVEC = \w+|lt_shapes_tuned = \d+)")


def parse_stage(paths):
    """-> OrderedDict[(arm, tag)] = dict(cells, g0, g1, clocks, rc, flags)"""
    out = OrderedDict()
    cur = None
    for p in paths:
        try:
            fh = open(p, encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in fh:
            line = line.rstrip("\n")
            m = HDR.match(line)
            if m:
                arm, tag, rc, wall, c0, c1, vram = m.groups()
                cur = {"arm": arm, "tag": tag, "rc": int(rc), "wall": int(wall),
                       "clocks": (c0, c1), "vram": vram, "cells": {}, "g0": None,
                       "g1": None, "flags": set()}
                out[(arm, tag)] = cur
                continue
            if cur is None:
                continue
            m = CELL.match(line)
            if m:
                name, med, iqr, outl, verdict = m.groups()
                key = "gen64" if name == "gen 64" else ("gen256" if name == "gen 256" else name)
                cur["cells"][key] = {"median": float(med), "rel_iqr": float(iqr),
                                     "outliers": int(outl), "verdict": verdict}
            m = G0.match(line)
            if m:
                cur["g0"] = line.strip()
            m = G1.match(line)
            if m:
                cur["g1"] = f"{m.group(1)} {m.group(2)}/{m.group(3)}"
            for f in FLAGLINE.findall(line):
                cur["flags"].add(f.strip())
        fh.close()
    return out


def ms_from_toks(cell, tok_s):
    n = CELL_TOKENS.get(cell)
    return (n / tok_s * 1000.0) if n else None


def main():
    art = sys.argv[1]
    trt_path = None
    clk_path = None
    for i, a in enumerate(sys.argv):
        if a == "--trtllm" and i + 1 < len(sys.argv):
            trt_path = sys.argv[i + 1]
        if a == "--clocks" and i + 1 < len(sys.argv):
            clk_path = sys.argv[i + 1]

    import glob
    import os
    paths = sorted(glob.glob(os.path.join(art, "sweep*.log"))
                   + glob.glob(os.path.join(art, "rag*.log")))
    runs = parse_stage(paths)
    if not runs:
        print(f"no stage logs parsed from {art}; looked at {paths}")
        return 1

    print("=" * 112)
    print("FRONT 6 -- per-cell results as measured (each cell is the driver's own median of "
          "--runs 20)")
    print("=" * 112)
    print(f"{'arm':<5} {'tag':<12} {'rc':>3} {'cell':<13} {'median tok/s':>14} {'rel-IQR%':>9} "
          f"{'out':>4} {'clocks':>16}  gates")
    for (arm, tag), r in runs.items():
        cl = f"{r['clocks'][0]}->{r['clocks'][1]}"
        gates = []
        if r["g0"]:
            gates.append("G0 " + ("PASS" if "PASS" in r["g0"] else "FAIL"))
        if r["g1"]:
            gates.append("G1 " + r["g1"])
        gtxt = " | ".join(gates) if gates else "(none)"
        offpin = ("" if r["clocks"][0].startswith("1410") and r["clocks"][1].startswith("1410")
                  else "  <-- OFF-PIN")
        for cell in ("prefill256", "prefill1024", "prefill4096", "gen64", "gen256"):
            if cell in r["cells"]:
                c = r["cells"][cell]
                print(f"{arm:<5} {tag:<12} {r['rc']:>3} {cell:<13} {c['median']:>14.3f} "
                      f"{c['rel_iqr']:>9.4f} {c['outliers']:>4} {cl:>16}  {gtxt}"
                      f"{' FLAG-IQR' if c['rel_iqr'] > 1.0 else ''}{offpin}")
        if r["flags"]:
            print(f"{'':<5} {'':<12} {'':>3} {'flags':<13} {', '.join(sorted(r['flags']))}")

    # ── baseline bracket drift ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 112)
    print("BASELINE BRACKET (drift armor): the same arm `_g0` measured first and last")
    print("=" * 112)
    g0s = [r for (a, t), r in runs.items() if a == "_g0"]
    for cell in ("prefill256", "prefill1024", "prefill4096", "gen64", "gen256"):
        vals = [(r["tag"], r["cells"][cell]["median"]) for r in g0s if cell in r["cells"]]
        if len(vals) >= 2:
            a, b = vals[0][1], vals[-1][1]
            d = 100.0 * (b - a) / a
            print(f"  {cell:<13} first({vals[0][0]}) {a:>12.3f}   last({vals[-1][0]}) {b:>12.3f}"
                  f"   drift {d:+.3f}%   {'OK' if abs(d) <= 1.0 else 'OVER THE 1% DRIFT BAND'}")
        elif len(vals) == 1:
            print(f"  {cell:<13} only one _g0 cell ({vals[0][0]}) -- no bracket, drift UNMEASURED")

    # ── TRT-LLM re-serve ────────────────────────────────────────────────────────────────────
    trt = None
    if trt_path:
        try:
            trt = json.load(open(trt_path))
        except (OSError, ValueError) as ex:
            print(f"\nTRT-LLM re-serve unreadable: {ex}")
    if trt:
        print("\n" + "=" * 112)
        print("TENSORRT-LLM 1.2.1 FRESH SAME-SESSION RE-SERVE (server median, executor iter-log "
              "device step time)")
        print("=" * 112)
        cells = trt.get("cells", trt)
        for k in sorted(cells):
            v = cells[k]
            if not isinstance(v, dict) or "server" not in v:
                continue
            srv = v["server"]
            med = srv.get("median_ms")
            if med is None:
                continue
            base = None
            for kk, vv in TRTLLM_R5_MS.items():
                if k.startswith(kk) or kk.startswith(k.split("_")[0]):
                    base = vv
                    break
            lbl = ""
            if base:
                d = 100.0 * (med - base) / base
                # spelled without a multi-line f-string expression on purpose: PEP 701 allows
                # one, but the VM's python3 predates 3.12 and dies with "unterminated string
                # literal" -- which is how this summarizer first failed in the post stage.
                verdict = ("SAME-SESSION" if abs(d) <= 1.0
                           else "CROSS-SESSION (label, do not blend)")
                lbl = f"vs FRONT5 {base:.3f} ms = {d:+.3f}% -> {verdict}"
            riqr = srv.get("rel_iqr_pct", 0)
            print(f"  {k:<10} server median {med:10.3f} ms  rel_iqr {riqr:.3f}%"
                  f"  n={srv.get('n')}  {lbl}")

    # ── ratios ──────────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 112)
    print("RATIOS (algenta tok/s DIVIDED BY TensorRT-LLM tok/s; > 1.0 is an ALGENTA WIN)")
    print("=" * 112)
    if trt:
        cells = trt.get("cells", trt)

        def trt_toks(key, ntok):
            v = cells.get(key)
            if not isinstance(v, dict):
                return None
            med = v.get("server", {}).get("median_ms")
            return (ntok / med * 1000.0) if med else None

        t256 = trt_toks("pp256", 256)
        t1024 = trt_toks("pp1024", 1024)
        trag = trt_toks("rag0", 4096) or trt_toks("rag", 4096)
        print(f"  TRT-LLM basis: pp256 {t256 and round(t256,1)} tok/s | pp1024 "
              f"{t1024 and round(t1024,1)} | rag4096 {trag and round(trag,1)}")
        for (arm, tag), r in runs.items():
            parts = []
            for cell, tref, nm in (("prefill256", t256, "pp256"),
                                   ("prefill1024", t1024, "pp1024"),
                                   ("prefill4096", trag, "RAG-4096")):
                if cell in r["cells"] and tref:
                    ratio = r["cells"][cell]["median"] / tref
                    mark = "WIN " if ratio >= 1.0 else "LOSS"
                    extra = ""
                    if nm in FRONT5_RATIOS and cell != "prefill4096":
                        extra = f" (FRONT5 {FRONT5_RATIOS[nm]:.3f}x)"
                    parts.append(f"{nm} {ratio:.4f}x {mark}{extra}")
            if "gen256" in r["cells"]:
                parts.append(f"gen256 {r['cells']['gen256']['median']:.3f} tok/s")
            if parts:
                print(f"  {arm}{tag:<12} " + " | ".join(parts))
        # the flip verdict on the best RAG arm
        best = None
        for (arm, tag), r in runs.items():
            if "prefill4096" in r["cells"] and trag:
                ratio = r["cells"]["prefill4096"]["median"] / trag
                ms = ms_from_toks("prefill4096", r["cells"]["prefill4096"]["median"])
                if best is None or ratio > best[1]:
                    best = (arm + tag, ratio, r["cells"]["prefill4096"]["median"], ms)
        if best:
            trg_ms = 4096.0 / trag * 1000.0
            print(f"\n  BEST RAG-4096 ARM: {best[0]}  {best[2]:.3f} tok/s = {best[3]:.3f} ms wall"
                  f"  vs TRT-LLM {trg_ms:.3f} ms ({trag:.3f} tok/s)")
            print(f"  VERDICT: {'FLIPPED TO A WIN' if best[1] >= 1.0 else 'STILL A LOSS'} "
                  f"at {best[1]:.4f}x  (FRONT 5 shipped 0.9556x)")
            print(f"  wall margin: {trg_ms - best[3]:+.3f} ms "
                  f"({'inside' if best[3] <= trg_ms else 'OUTSIDE'} their wall)")
    else:
        print("  no TRT-LLM re-serve parsed -- ratios cannot be computed")

    # ── clock zero-drift audit ──────────────────────────────────────────────────────────────
    if clk_path:
        try:
            with open(clk_path, encoding="utf-8", errors="replace") as fh:
                rows = [ln.strip() for ln in fh if ln.strip()]
        except OSError:
            rows = []
        if rows:
            off = [r for r in rows if not r.split(",")[1].strip().startswith("1410")]
            print("\n" + "=" * 112)
            print("ZERO-DRIFT CLOCK AUDIT (1 Hz sampler over the whole stage)")
            print("=" * 112)
            verdict = ("ZERO-DRIFT SATISFIED" if not off else
                       "DRIFT -- re-take any cell whose timed window contains one of these")
            print(f"  samples {len(rows)}   off-pin {len(off)}   {verdict}")
            for r in off[:12]:
                print(f"    OFF-PIN {r}")
    print("\nSUMMARIZE_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
