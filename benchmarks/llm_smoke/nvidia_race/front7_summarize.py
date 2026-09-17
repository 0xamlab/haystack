#!/usr/bin/env python3
"""front7_summarize.py -- the FRONT 7 result table, parsed from the stage logs.

Reads the interleaved A/B stage logs (which `run_arm` already reduces to one `== <arm><tag>`
header plus the grepped gate/cell lines) and the TRT-LLM re-serve JSON, and emits:

  * per arm per cell: median tok/s, rel-IQR, outliers, G0, G1, clocks before->after
  * the baseline BRACKET drift (first vs last `_h0` of the same sweep) -- round 2's drift armor
  * the TRT-LLM re-serve checked against round 5's stored cells, labelled SAME-SESSION or
    CROSS-SESSION at the owner's 1% threshold rather than averaged away
  * the ratio table and the RAG-4096 flip verdict
  * the zero-drift clock audit over the 1 Hz sampler window

Round 4 shipped a summarizer with the pp256/pp1024 ratio INVERTED and two WINS printed as
losses; it was caught only because 0.94x pp1024 contradicted a prior round on an axis the round
had not touched. So every ratio here is printed with its direction stated in words, and the
pp256/pp1024 columns are cross-checked against FRONT 6's published ratios (1.8089x / 1.0896x) on
axes these levers cannot touch by construction -- the f16 O twin only fires where FA2 runs a pass
of more than 1024 rows... which pp1024 does not, so a pp1024 move is a red flag, not a win.

FRONT 7's baseline `_h0` is FRONT 6's ship arm `_g2` rebuilt, so this summarizer ALSO checks the
baseline against FRONT 6's published cells (15324.50 / 12880.81 / 15464.19 tok/s). A baseline
that does not reproduce is not a baseline, and every ratio in the round moves with it.

Usage: front7_summarize.py <artifact_dir> [--trtllm json] [--clocks-json json]
"""

from __future__ import annotations

import json
import re
import sys
from collections import OrderedDict

# round 6's published ratios, used ONLY as a sanity check on axes these levers cannot move
FRONT6_RATIOS = {"pp256": 1.8089, "pp1024": 1.0896, "RAG-4096": 1.0221}
# round 6's published baseline cells in tok/s. `_h0` IS that arm rebuilt, so it must reproduce
# them; the band is round 6's own cross-prompt spread (0.044%) widened to 1% for a different
# session, because a re-serve that drifts monotonically ~1% per round also moves our side.
RAG_SHIP_ARM = "_h1"   # the arm whose RAG cells the shipped ratio comes from
FRONT6_BASELINE_TOKS = {"prefill256": 12880.81, "prefill1024": 15464.19, "prefill4096": 15324.50}
# round 6's same-session TRT-LLM 1.2.1 re-serve (server median ms). A round-7 re-serve more
# than 1% away from these is CROSS-SESSION and must be labelled, not blended.
TRTLLM_R6_MS = {"pp256": 35.950, "pp1024": 72.149, "rag": 273.186}
# the raced prompt lengths
CELL_TOKENS = {"pp256": 256, "pp1024": 1024, "prefill4096": 4096}

# The clock field carries units and a space ("clocks=1410 MHz->1410 MHz"), so `(\S+)->(\S+)`
# can never match it -- the first version of this regex parsed ZERO cells out of six stage logs
# and the summarizer exited with "no stage logs parsed" while the stage itself was fine.
HDR = re.compile(r"^== (_h\w+?)(_\S*)? rc=(\d+) wall=([\d.]+)s clocks=(.*?)->(.*?) "
                 r"power_at_start=(.*?) vram_after=(.*?)\s*$")
CELL = re.compile(r"^(prefill\d+|gen \d+)\s*: median ([\d.]+) tok/s \| IQR ([\d.]+) % \| "
                  r"outliers (\d+) \| (\w+)")
G0 = re.compile(r"^G0 RESULT: (PASS|FAIL)[^\d]*(\d+)?")
G1 = re.compile(r"^G1 RESULT: (PASS|FAIL)\s*[^\d]*(\d+)\s*/\s*(\d+)")
FLAGLINE = re.compile(r"(pass_max = \d+|ROPEVEC = \w+|lt_shapes_tuned = \d+ of \d+"
                      r"|lt_insitu_state = \d+|o16_twin = \w+|fa_row_order = [^|]+)")
O16V = re.compile(r"^O16 VERIFY RESULT: (\w+)")
LTINS = re.compile(r"^LT INSITU: FROZEN (\d+) shapes \| state = (\d+)")


def parse_stage(paths):
    """-> OrderedDict[(arm, tag)] = dict(cells, g0, g1, clocks, rc, flags)"""
    out = OrderedDict()
    seen = {}
    cur = None
    for p in paths:
        try:
            fh = open(p, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                line = line.rstrip("\n")
                m = HDR.match(line)
                if m:
                    arm, tag, rc, wall, c0, c1, pwr, vram = m.groups()
                    cur = {"arm": arm, "tag": tag or "", "rc": int(rc), "wall": float(wall),
                           "clocks": (c0, c1), "power": pwr, "vram": vram, "cells": {}, "g0": None,
                           "g1": None, "flags": set(), "o16": None, "ltinsitu": None}
                    # The key carries an OCCURRENCE index. It did not, and the drift bracket that
                    # depends on it was therefore never computed: one stage tags every sweep cell with
                    # the same ROUND, so the baseline's first and last cells share (arm, tag) and the
                    # second silently overwrote the first in the OrderedDict. The summarizer then
                    # printed "only one _h0 cell -- no bracket, drift UNMEASURED" for pp256/pp1024
                    # while reporting a -25% "drift" for gen64/gen256 that was not drift at all: it
                    # had compared the fixture-context sweep cell against a RAG-4096 cell, where
                    # decode runs against a 4096-token KV cache and is legitimately ~25% slower.
                    seen[(arm, tag or "")] = seen.get((arm, tag or ""), -1) + 1
                    cur["occ"] = seen[(arm, tag or "")]
                    out[(arm, tag or "", cur["occ"])] = cur
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
                m = O16V.match(line)
                if m:
                    cur["o16"] = line.strip()
                m = LTINS.match(line)
                if m:
                    cur["ltinsitu"] = f"frozen {m.group(1)} shapes, state {m.group(2)}"
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
        if a in ("--clocks", "--clocks-json") and i + 1 < len(sys.argv):
            clk_path = sys.argv[i + 1]

    import glob
    import os
    paths = sorted(glob.glob(os.path.join(art, "sweep*.log"))
                   + glob.glob(os.path.join(art, "rag*.log"))
                   + glob.glob(os.path.join(art, "stage*.log")))
    runs = parse_stage(paths)
    if not runs:
        print(f"no stage logs parsed from {art}; looked at {paths}")
        return 1

    print("=" * 112)
    print("FRONT 7 -- per-cell results as measured (each cell is the driver's own median of "
          "--runs 20)")
    print("=" * 112)
    print(f"{'arm':<5} {'tag':<12} {'rc':>3} {'cell':<13} {'median tok/s':>14} {'rel-IQR%':>9} "
          f"{'out':>4} {'clocks':>16}  gates")
    for (arm, tag, _occ), r in runs.items():
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
                print(f"{arm:<5} {tag:<18} {r['rc']:>3} {cell:<13} {c['median']:>14.3f} "
                      f"{c['rel_iqr']:>9.4f} {c['outliers']:>4} {cl:>16}  {gtxt}"
                      f"{' FLAG-IQR' if c['rel_iqr'] > 1.0 else ''}{offpin}")
        if r["flags"] or r["o16"] or r["ltinsitu"]:
            extra = [x for x in (r["o16"], r["ltinsitu"]) if x]
            print(f"{'':<5} {'':<18} {'':>3} {'flags':<13} {', '.join(sorted(r['flags']))}")
            for x in extra:
                print(f"{'':<5} {'':<18} {'':>3} {'proof':<13} {x}")

    # ── baseline bracket drift ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 112)
    print("BASELINE BRACKET (drift armor): the same arm `_h0` measured first and last")
    print("=" * 112)
    g0s = [r for (a, t, _o), r in runs.items() if a == "_h0"]
    for cell in ("prefill256", "prefill1024", "prefill4096", "gen64", "gen256"):
        vals = [(f'{r["tag"]}#{r["occ"]}', r["cells"][cell]["median"])
                for r in g0s if cell in r["cells"]]
        if len(vals) >= 2 and vals[0][0].rsplit("#", 1)[0] == vals[-1][0].rsplit("#", 1)[0]:
            a, b = vals[0][1], vals[-1][1]
            d = 100.0 * (b - a) / a
            print(f"  {cell:<13} first({vals[0][0]}) {a:>12.3f}   last({vals[-1][0]}) {b:>12.3f}"
                  f"   drift {d:+.3f}%   {'OK' if abs(d) <= 1.0 else 'OVER THE 1% DRIFT BAND'}")
        elif len(vals) >= 2:
            print(f"  {cell:<13} {len(vals)} _h0 cells but from different tags "
                  f"({vals[0][0]} vs {vals[-1][0]}) -- NOT comparable, drift UNMEASURED")
        else:
            print(f"  {cell:<13} only one _h0 cell "
                  f"({vals[0][0] if vals else 'none'}) -- no bracket, drift UNMEASURED")

    # ── does the baseline reproduce FRONT 6's published cells? ───────────────────────────────
    print("\n" + "=" * 112)
    print("BASELINE REPRODUCTION: `_h0` IS FRONT 6's ship arm `_g2` rebuilt from this branch, and")
    print("its shim object is section-, symbol- and SASS-identical to a build of FRONT 6's source.")
    print("If these cells do not reproduce, the ratios below are against something else.")
    print("=" * 112)
    for cell, ref in FRONT6_BASELINE_TOKS.items():
        vals = [(f'{r["tag"]}#{r["occ"]}', r["cells"][cell]["median"])
                for r in g0s if cell in r["cells"]]
        if not vals:
            print(f"  {cell:<13} NOT MEASURED this round -- FRONT 6 published {ref:.2f} tok/s")
            continue
        for tag, v in vals:
            d = 100.0 * (v - ref) / ref
            print(f"  {cell:<13} _h0{tag:<12} {v:>12.2f} tok/s   FRONT 6 {ref:>12.2f}   "
                  f"{d:+.3f}%   {'REPRODUCES' if abs(d) <= 1.0 else 'DOES NOT REPRODUCE (>1%)'}")

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
            for kk, vv in TRTLLM_R6_MS.items():
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
                lbl = f"vs FRONT6 {base:.3f} ms = {d:+.3f}% -> {verdict}"
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
        for (arm, tag, _occ), r in runs.items():
            parts = []
            for cell, tref, nm in (("prefill256", t256, "pp256"),
                                   ("prefill1024", t1024, "pp1024"),
                                   ("prefill4096", trag, "RAG-4096")):
                if cell in r["cells"] and tref:
                    ratio = r["cells"][cell]["median"] / tref
                    mark = "WIN " if ratio >= 1.0 else "LOSS"
                    extra = ""
                    if nm in FRONT6_RATIOS:
                        extra = f" (FRONT6 {FRONT6_RATIOS[nm]:.4f}x)"
                    parts.append(f"{nm} {ratio:.4f}x {mark}{extra}")
            if "gen256" in r["cells"]:
                parts.append(f"gen256 {r['cells']['gen256']['median']:.3f} tok/s")
            if parts:
                print(f"  {arm}{tag:<18} " + " | ".join(parts))
        # the flip verdict on the best RAG arm
        best = None
        for (arm, tag, _occ), r in runs.items():
            if "prefill4096" in r["cells"] and trag:
                ratio = r["cells"]["prefill4096"]["median"] / trag
                ms = ms_from_toks("prefill4096", r["cells"]["prefill4096"]["median"])
                if best is None or ratio > best[1]:
                    best = (arm + tag, ratio, r["cells"]["prefill4096"]["median"], ms)
        # The per-prompt MEDIAN and MEAN, printed next to the max, because "the best cell" is a
        # maximum over three prompts x N arms and quoting it as the result is cherry-picking --
        # the more so when one cell's rel-IQR is 10x tighter than its siblings' and its value is
        # the outlier. The shipped claim is the median across the raced prompts.
        rag_vals = sorted(r["cells"]["prefill4096"]["median"] / trag
                          for (a, t, o), r in runs.items()
                          if "prefill4096" in r["cells"] and trag and a == RAG_SHIP_ARM)
        if rag_vals:
            mid = rag_vals[len(rag_vals) // 2] if len(rag_vals) % 2 else \
                0.5 * (rag_vals[len(rag_vals) // 2 - 1] + rag_vals[len(rag_vals) // 2])
            print(f"  {RAG_SHIP_ARM} RAG-4096 across {len(rag_vals)} prompts: "
                  f"min {rag_vals[0]:.4f}x  MEDIAN {mid:.4f}x  mean "
                  f"{sum(rag_vals)/len(rag_vals):.4f}x  max {rag_vals[-1]:.4f}x  "
                  f"<-- quote the MEDIAN; the max is one cell")
        if best:
            trg_ms = 4096.0 / trag * 1000.0
            print(f"\n  BEST RAG-4096 ARM: {best[0]}  {best[2]:.3f} tok/s = {best[3]:.3f} ms wall"
                  f"  vs TRT-LLM {trg_ms:.3f} ms ({trag:.3f} tok/s)")
            print(f"  VERDICT: {'WIN' if best[1] >= 1.0 else 'LOSS'} at {best[1]:.4f}x "
                  f"(FRONT 6 shipped 1.0221x; the round's target is a WIDER margin, and "
                  f"{best[1] - 1.0221:+.4f}x is the change)")
            print(f"  wall margin: {trg_ms - best[3]:+.3f} ms "
                  f"({'inside' if best[3] <= trg_ms else 'OUTSIDE'} their wall)")
    else:
        print("  no TRT-LLM re-serve parsed -- ratios cannot be computed")

    # ── clock/power zero-drift audit, PER CELL at 200 ms ────────────────────────────────────
    # FRONT 6 could only report a stage-wide off-pin count at 1 Hz and had to bound its breach
    # with an argument, because a 5.3 s cell holds ~5 samples at that rate. This reads
    # front7_clocks.py's JSON, which attributes off-pin samples and milliseconds to each cell
    # window and separates a power-cap throttle from a thermal one.
    if clk_path:
        try:
            cj = json.load(open(clk_path))
        except (OSError, ValueError) as ex:
            cj = None
            print(f"\nclock JSON unreadable: {ex}")
        if cj:
            print("\n" + "=" * 112)
            print(f"ZERO-DRIFT CLOCK/POWER AUDIT (200 ms sampler, {cj['n_samples']} samples, "
                  f"pin {cj['pin_mhz']:.0f} MHz, stage off-pin {cj['stage_off_pin']})")
            print("=" * 112)
            bad = [c for c in cj["cells"] if c["off_pin_pct"] > 0.5]
            print(f"{'cell':<28} {'off%':>6} {'off_ms':>7} {'minMHz':>7} {'maxW':>7} verdict")
            for c in cj["cells"]:
                print(f"{c['cell']:<28} {c['off_pin_pct']:6.2f} {c['off_pin_ms']:7.0f} "
                      f"{c['min_clock_mhz']:7.0f} {c['max_power_w']:7.1f} {c['verdict']}")
            print(f"  {len(bad)} of {len(cj['cells'])} cells carry >0.5% off-pin time -- "
                  + ("ZERO-DRIFT SATISFIED" if not bad else
                     "BREACH: every affected cell must be re-taken or bounded in the ledger"))
    print("\nSUMMARIZE_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
