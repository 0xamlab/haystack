#!/usr/bin/env python3
"""mr_subtract_gemma3_round6.py — exact measured-request buckets by PRIMING-TRACE SUBTRACTION.

argv: <full_trace.json> <priming_trace.json> [cell]   (JSONs from mr_extract_gemma3_round6.py
      run with --gap-ms small enough to keep load+priming+timed in the LAST cluster, or with
      the default 3 ms gap when load separates cleanly; the extractor's cluster census in the
      log shows which clusters were picked, and both traces must pick comparably)

seal() runs the four priming prefills REGARDLESS of the prompt, so the 32-row priming capture
(m < TC_MIN_M => its own timed prefill stays on the tiny SIMT path, ~1 ms of small kernels)
is load + priming + epsilon. Subtracting its buckets from the full trace's LAST-cluster
buckets leaves the timed request's per-bucket milliseconds — the same-arm, same-session,
clock-pinned alternative to modelling the priming share (round 5 reconciled instance COUNTS
this way; this subtracts TIME).

The epsilon (the 32-row prefill's own kernels) is bounded and reported: it is at most a few
ms of SIMT attention + small-m GEMMs, and it makes the subtraction CONSERVATIVE for the
buckets the levers move (fused attention, converts) because those kernels do not run in the
32-row prefill at all (m < _G3_PF_FA_MIN_M => the fused kernel declines; m < TC_MIN_M => the
TC GEMM seam declines). It slightly OVER-subtracts gemm/mojo buckets by the 32-row share.
"""
import json
import sys

full = json.load(open(sys.argv[1]))
prim = json.load(open(sys.argv[2]))
cell = sys.argv[3] if len(sys.argv) > 3 else full.get("cell")

FLOP_PER_TOKEN = (2 * 5376 * (4096 + 4096) + 2 * 4096 * 5376
                  + 2 * 5376 * 2 * 21504 + 2 * 21504 * 5376)
N_LAYERS = 62
CELL_TOKENS = {"pp256": 256, "pp1024": 1024, "val550": 550, "rag4096": 4096}

fb = full["measured_request"] if "measured_request" in full else full
buckets_f = full["buckets"]
buckets_p = prim["buckets"]

print(f"=== measured-request buckets by priming subtraction ({cell}) ===")
print(f"full last-cluster busy {full['measured_request']['busy_ms']:.3f} ms  -  "
      f"priming last-cluster busy {prim['measured_request']['busy_ms']:.3f} ms")
print(f"{'bucket':<20}{'full ms':>10}{'priming ms':>12}{'measured ms':>13}{'inst f/p':>12}")
tot_f = tot_p = 0.0
out = {}
for b in sorted(set(buckets_f) | set(buckets_p),
                key=lambda b: -(buckets_f.get(b, {}).get("ms", 0))):
    f = buckets_f.get(b, {"ms": 0.0, "instances": 0})
    p = buckets_p.get(b, {"ms": 0.0, "instances": 0})
    tot_f += f["ms"]; tot_p += p["ms"]
    out[b] = {"full_ms": f["ms"], "priming_ms": p["ms"],
              "measured_ms": round(f["ms"] - p["ms"], 3),
              "inst_full": f["instances"], "inst_priming": p["instances"]}
    print(f"{b:<20}{f['ms']:>10.3f}{p['ms']:>12.3f}{f['ms'] - p['ms']:>13.3f}"
          f"{'  %d/%d' % (f['instances'], p['instances']):>12}")
print(f"{'TOTAL':<20}{tot_f:>10.3f}{tot_p:>12.3f}{tot_f - tot_p:>13.3f}")

if cell in CELL_TOKENS:
    g = out.get("gemm_projection", {}).get("measured_ms", 0)
    if g > 0:
        flops = FLOP_PER_TOKEN * CELL_TOKENS[cell] * N_LAYERS + 2 * 5376 * 262208
        tf = flops / (g / 1000.0) / 1e12
        print(f"\nGEMM measured {g:.3f} ms -> {tf:.1f} TFLOP/s "
              f"({100 * tf / (989 * 1410 / 1980):.1f}% of the pinned peak); "
              f"TRT-LLM 1.2.1 reference: 296.55 ms / ~707 TFLOP/s at rag4096")
json.dump(out, open(sys.argv[1].replace(".json", "_subtracted.json"), "w"), indent=2)
print(f"WROTE {sys.argv[1].replace('.json', '_subtracted.json')}")
