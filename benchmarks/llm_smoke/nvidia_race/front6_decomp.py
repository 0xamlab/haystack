#!/usr/bin/env python3
"""front6_decomp.py -- the RAG-4096 host/launch-gap dissection (FRONT 6).

Round 5 ranked a ~6-10 ms HOST/LAUNCH GAP at RAG-4096 (wall 284.805 ms against "~276 ms" of GPU
busy) as the round's best expected-value attack, and round 3 had REFUTED prefill CUDA graphs on
the strength of a 98.3%-busy measurement. Those two claims cannot both be right, and the whole
round's lever ranking hangs on which one is. This script settles it in ONE basis: the wall and
the busy both come from the same nsys capture, so the gap is a measurement, not a cross-basis
subtraction.

It also decides WHICH KIND of gap it is, because the two kinds have different fixes:
  * MANY SMALL gaps, one per launch -> the host cannot stay ahead of the device. Fix = fewer
    host operations (CUDA-graph the per-chunk sequence).
  * FEW LARGE gaps at the chunk seams -> a drain. Fix = remove the sync/upload that causes it.

MARKERS (chosen from the captured kernel table, not guessed -- Mojo kernel names are mangled):
  * the per-chunk embedding gather `residentk_kernels_prefill_f32..._6fbdda6b` (4/prefill)
  * the fused flash attention                 `_fa2_causal_kernel<32,1,1>`          (112/prefill)
  * the prefill lm_head                       `..._lmh..._9f8e6b01`                  (1/prefill)
  * the argmax that closes it                 `..._argmax_redu...`
A prefill window is [first embed of a 4-embed group, end of the argmax after that prefill's
lm_head]. Every window in the capture is analysed and reported, so the timed one is not
special-cased by assumption.

Usage: front6_decomp.py <gputrace.csv> [apitrace.csv]
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict

NS = 1e6  # ns -> ms

EMBED_RX = re.compile(r"prefill_f32.*6fbdda6b|embed", re.I)
FA2_RX = re.compile(r"_fa2_causal_kernel")
LMH_RX = re.compile(r"_lmh.*9f8e6b01")
ARGMAX_RX = re.compile(r"argmax")

FAMILIES = [
    ("fa2_flash", re.compile(r"_fa2_causal_kernel")),
    ("fa_flash", re.compile(r"_fa_causal_kernel")),
    ("cublas_gemm", re.compile(r"nvjet|ampere_.*gemm|cutlass|s16816gemm|xmma", re.I)),
    ("kv_stage_v8", re.compile(r"_f32_to_f16_v8")),
    ("A_convert_scalar", re.compile(r"_f32_to_f16_kernel")),
    ("convert_other", re.compile(r"f32_to_f16|f16_to_f32")),
    ("swiglu", re.compile(r"swiglu|silu")),
    ("rmsnorm", re.compile(r"prefill_gemma.*edb887a5|norm")),
    ("biasrope", re.compile(r"prefill_gemma.*7c2de7d7|biasrope|rope|qkv_bias")),
    ("lm_head", re.compile(r"_lmh")),
    ("argmax", ARGMAX_RX),
    ("embed", EMBED_RX),
    ("memset", re.compile(r"memset", re.I)),
    ("memcpy", re.compile(r"memcpy", re.I)),
    ("packed3", re.compile(r"packed3|_pac")),
]


def family(name):
    for fam, rx in FAMILIES:
        if rx.search(name or ""):
            return fam
    return "other"


def read_csv(path):
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


def col(row, *cands):
    for c in cands:
        for k in row:
            if k and k.strip().lower().startswith(c.lower()):
                return row[k]
    return None


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def union_busy(intervals):
    if not intervals:
        return 0.0, 0.0
    iv = sorted(intervals)
    naive = sum(e - s for s, e in iv)
    union, cs, ce = 0.0, iv[0][0], iv[0][1]
    for s, e in iv[1:]:
        if s > ce:
            union += ce - cs
            cs, ce = s, e
        else:
            ce = max(ce, e)
    union += ce - cs
    return union, naive


def main():
    gpu_path = sys.argv[1]
    api_path = sys.argv[2] if len(sys.argv) > 2 else None
    rows = read_csv(gpu_path)
    if not rows:
        print("EMPTY gpu trace")
        return 1

    ks = []
    for r in rows:
        s = fnum(col(r, "Start"))
        d = fnum(col(r, "Duration"))
        e = fnum(col(r, "End"))
        if s is None:
            continue
        if e is None:
            e = s + (d or 0.0)
        nm = (col(r, "Name") or "").strip()
        ks.append({"s": s, "e": e, "name": nm, "fam": family(nm),
                   "gx": fnum(col(r, "GrdX")) or 0,
                   "strm": col(r, "Strm")})
    ks.sort(key=lambda k: k["s"])
    t0 = ks[0]["s"]
    print(f"# device ops: {len(ks)}   capture span: {(ks[-1]['e']-t0)/NS:.1f} ms")

    embeds = [k for k in ks if EMBED_RX.search(k["name"])]
    fa2 = [k for k in ks if FA2_RX.search(k["name"])]
    lmh = [k for k in ks if LMH_RX.search(k["name"])]
    argm = [k for k in ks if ARGMAX_RX.search(k["name"])]
    print(f"# markers: embed={len(embeds)} (4/prefill)  fa2={len(fa2)} (112/prefill)  "
          f"prefill_lm_head={len(lmh)} (1/prefill)  argmax={len(argm)}")
    if not lmh:
        print("NO PREFILL lm_head MARKER -- cannot window")
        return 2

    # A prefill is bracketed by its own lm_head: the 4 embeds immediately preceding lm_head i
    # are that prefill's chunk starts. (Grouping embeds by idle gap does NOT work -- one chunk
    # is ~70 ms, far longer than any 20 ms threshold, so that splits every prefill into 4.)
    windows = []
    prev_end = None
    for hi_, h in enumerate(lmh):
        # Every embed between the PREVIOUS prefill's lm_head and this one belongs to this
        # prefill -- one embed per pass, so 4 of them under the shipped 1024-row cap and exactly
        # 1 under ALGENTA_PF_PASS4096. Taking "the last 4 embeds" instead is wrong the moment the
        # cap moves: it silently builds a window spanning four prefills and all their decode
        # tails, and reports a 3100 ms "prefill" with 30212 device ops. The chunk count is
        # derived from the trace, never assumed.
        lo = prev_end if prev_end is not None else float("-inf")
        g = [e for e in embeds if lo <= e["s"] < h["s"]]
        if not g:
            continue
        after = [a for a in argm if a["s"] >= h["s"]]
        wend = (after[0]["e"] if after else h["e"])
        windows.append({"idx": hi_, "s": g[0]["s"], "e": wend,
                        "embeds": [x["s"] for x in g]})
        prev_end = h["e"]
    nch = sorted({len(w["embeds"]) for w in windows})
    print(f"# prefill windows found: {len(windows)} (one per prefill lm_head); "
          f"passes per prefill: {nch}")

    api = []
    if api_path:
        for r in read_csv(api_path):
            s = fnum(col(r, "Start"))
            d = fnum(col(r, "Duration"))
            e = fnum(col(r, "End"))
            if s is None:
                continue
            if e is None:
                e = s + (d or 0.0)
            api.append((s, e, (col(r, "Name") or "").strip()))
        print(f"# host CUDA-API rows: {len(api)}")

    summary = []
    for w in windows:
        seg = [k for k in ks if w["s"] <= k["s"] <= w["e"]]
        if not seg:
            continue
        busy, naive = union_busy([(k["s"], k["e"]) for k in seg])
        wall = (w["e"] - w["s"]) / NS
        gaps = []
        for a, b in zip(seg, seg[1:], strict=False):
            if b["s"] - a["e"] > 0:
                gaps.append((b["s"] - a["e"], a, b))
        tg = sum(x[0] for x in gaps) / NS
        launch_api = [x for x in api if w["s"] <= x[0] <= w["e"]
                      and ("Launch" in x[2] or "Memcpy" in x[2] or "Memset" in x[2])]
        sync_api = [x for x in api if w["s"] <= x[0] <= w["e"] and "Synchronize" in x[2]]
        hub, _ = union_busy([(s, e) for s, e, _ in api if w["s"] <= s <= w["e"]])
        summary.append({"w": w, "seg": seg, "busy": busy / NS, "wall": wall,
                        "gap": tg, "gaps": gaps, "nlaunch": len(launch_api),
                        "nsync": len(sync_api),
                        "syncms": sum(e - s for s, e, _ in sync_api) / NS,
                        "hostapi": hub / NS, "naive": naive / NS})

    print("\n" + "=" * 108)
    print("## EVERY PREFILL WINDOW IN THE CAPTURE (one basis: wall and busy from the same trace)")
    print("   #   wall_ms    busy_ms    gap_ms   gap%   dev_ops  host_launch_apis "
          " syncs  sync_ms  host_in_api_ms")
    for s in summary:
        print(f"  {s['w']['idx']:2d} {s['wall']:9.3f} {s['busy']:10.3f} {s['wall']-s['busy']:9.3f}"
              f" {100*(s['wall']-s['busy'])/max(s['wall'],1e-9):6.2f}  {len(s['seg']):7d}"
              f"  {s['nlaunch']:15d} {s['nsync']:6d} {s['syncms']:8.3f} {s['hostapi']:14.3f}")
    if not summary:
        print("no windows")
        return 3
    med = sorted(summary, key=lambda s: s["wall"])[len(summary) // 2]
    print(f"\n   MEDIAN window: wall {med['wall']:.3f} ms  busy {med['busy']:.3f} ms  "
          f"gap {med['wall']-med['busy']:.3f} ms  "
          f"({100*(med['wall']-med['busy'])/med['wall']:.2f}% of wall)")
    print(f"   naive sum of kernel durations (overlap double-counted): {med['naive']:.3f} ms")

    # ── the decisive structure dump on the median window ────────────────────────────────────
    seg, wall = med["seg"], med["wall"]
    print("\n" + "=" * 108)
    print(f"## GAP STRUCTURE of window {med['w']['idx']}  (total {med['wall']-med['busy']:.3f} ms)")
    gaps = sorted(med["gaps"], key=lambda x: -x[0])
    tot = sum(g for g, _, _ in gaps) / NS
    print(f"   sum of positive inter-op gaps: {tot:.3f} ms over {len(gaps)} gaps")
    for lo, hi in [(0, 1), (1, 5), (5, 20), (20, 100), (100, 1000), (1000, 10**9)]:
        sel = [g for g, _, _ in gaps if lo * 1000 <= g < hi * 1000]
        tt = sum(sel) / NS
        print(f"   {lo:>6}-{hi:<9}us  n={len(sel):7d}  total {tt:8.3f} ms  "
              f"{100*tt/max(tot,1e-9):5.1f}%")
    print("\n   top 20 gaps with the bracketing device ops:")
    for g, a, b in gaps[:20]:
        print(f"     {g/1000:9.2f} us @ {(a['s']-med['w']['s'])/NS:8.3f} ms  "
              f"{a['name'][:46]:<46} -> {b['name'][:46]}")

    # ── per-chunk split ─────────────────────────────────────────────────────────────────────
    eb = med["w"]["embeds"]
    if len(eb) == 1:
        cb, _ = union_busy([(k["s"], k["e"]) for k in seg])
        print(f"\n## SINGLE-PASS PREFILL (ALGENTA_PF_PASS4096): one embed launch, "
              f"{len(seg)} device ops, wall {med['wall']:.3f} ms, busy {cb/NS:.3f} ms, "
              f"gap {med['wall']-cb/NS:.3f} ms, and NO chunk seams at all -- the three "
              f"~200 us token-upload+synchronize seams the 4-pass walk pays are gone.")
    if len(eb) >= 2:
        print(f"\n## PER-CHUNK (split on the {len(eb)} embed launches); "
              "chunk 3 runs to the window end")
        bounds = list(eb) + [med["w"]["e"] + 1]
        for i in range(len(eb)):
            cs = [k for k in seg if bounds[i] <= k["s"] < bounds[i + 1]]
            if not cs:
                continue
            cb, _ = union_busy([(k["s"], k["e"]) for k in cs])
            cw = (cs[-1]["e"] - cs[0]["s"]) / NS
            print(f"   chunk {i}: wall {cw:8.3f}  busy {cb/NS:8.3f}  gap {cw-cb/NS:7.3f} ms"
                  f"  ({100*(cw-cb/NS)/max(cw,1e-9):5.2f}%)  ops={len(cs)}")
        # the seam gap: last op of chunk i -> first op of chunk i+1
        print("   CHUNK SEAMS (the per-chunk token upload + ctx.synchronize() live here):")
        for i in range(len(eb) - 1):
            before = [k for k in seg if k["e"] <= bounds[i + 1]]
            after = [k for k in seg if k["s"] >= bounds[i + 1]]
            if before and after:
                print(f"     seam {i}->{i+1}: {before[-1]['name'][:40]:<40} -> "
                      f"{after[0]['name'][:40]:<40} "
                      f"gap {(after[0]['s']-before[-1]['e'])/1000:.2f} us")

    # ── per-family busy ─────────────────────────────────────────────────────────────────────
    fam = defaultdict(lambda: [0, 0.0])
    for k in seg:
        fam[k["fam"]][0] += 1
        fam[k["fam"]][1] += (k["e"] - k["s"])
    tot_fam = sum(v[1] for v in fam.values())
    print("\n## PER-FAMILY GPU BUSY in the window (naive sum)")
    for f, (c, tt) in sorted(fam.items(), key=lambda x: -x[1][1]):
        print(f"   {tt/NS:9.3f} ms {100*tt/max(tot_fam,1e-9):6.2f}%  n={c:6d}  {f}")
    print(f"   {tot_fam/NS:9.3f} ms  TOTAL   (union busy {med['busy']:.3f}, wall {wall:.3f})")

    # ── per-kernel table WITH LAUNCH GEOMETRY: this is how a cublas kernel is attributed to a
    #    GEMM role when the name does not say (cuBLAS picks one kernel per shape, so the grid
    #    identifies the shape). Round 3 published a wrong family roll-up by substring-matching
    #    "gemm" against "gemma"; geometry attribution is the fix that round 3 adopted. ────────
    byk = defaultdict(lambda: [0, 0.0, set()])
    for k in seg:
        r = byk[k["name"]]
        r[0] += 1
        r[1] += (k["e"] - k["s"])
        r[2].add((int(k["gx"]), 0))
    print("\n## PER-KERNEL in the window, with launch geometry (grid.x set) -- the GEMM role map")
    print("   total_ms    mean_us      n   grid.x values            name")
    for nm, (c, tt, grids) in sorted(byk.items(), key=lambda x: -x[1][1])[:26]:
        gs = sorted(g for g, _ in grids)[:6]
        print(f"   {tt/NS:9.3f} {tt/max(c,1)/1000:10.2f} {c:6d}   {str(gs)[:22]:<22} {nm[:76]}")

    # ── host side ───────────────────────────────────────────────────────────────────────────
    if api:
        inw = [x for x in api if med["w"]["s"] <= x[0] <= med["w"]["e"]]
        byapi = defaultdict(lambda: [0, 0.0])
        for s, e, nm in inw:
            byapi[nm][0] += 1
            byapi[nm][1] += (e - s)
        print(f"\n## HOST CUDA-API inside window {med['w']['idx']} ({len(inw)} calls)")
        print("   api                              count    total_ms   mean_us   %of_wall")
        for nm, (c, tt) in sorted(byapi.items(), key=lambda x: -x[1][1])[:18]:
            print(f"   {nm[:32]:<32} {c:8d} {tt/NS:10.3f} {tt/max(c,1)/1000:9.2f}"
                  f" {100*tt/NS/max(wall,1e-9):7.1f}%")
        print(f"\n   host time INSIDE cuda API calls (union) : {med['hostapi']:.3f} ms "
              f"of {wall:.3f} ms wall")
        print(f"   host time OUTSIDE every cuda API call   : {wall-med['hostapi']:.3f} ms"
              "   <- Mojo dispatch + cuBLAS heuristics + marshalling")
        print(f"   SYNCHRONIZE calls {med['nsync']} totalling {med['syncms']:.3f} ms")
        print(f"   device ops {len(seg)} vs host launch APIs {med['nlaunch']}"
              f"  -> {len(seg)/max(med['nlaunch'],1):.2f} device ops per launch API")
    print("\nDECOMP_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
