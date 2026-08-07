# llama.cpp white-box competitor lab

Pinned, auditable teardown-and-dyno laboratory for the Attention Compiler Plan v1.0. llama.cpp is
the fully-inspectable generic control engine, not an opaque competitor: its source at the EXACT
commit inside the raced binary is vendored here (`upstream_src/`, hashes in `SOURCE_HASHES`,
provenance in `UPSTREAM_COMMIT` / `BUILD_FLAGS`, upstream `LICENSE` preserved). Upstream code
compiles ONLY inside this lab — never into any production Algenta binary. The production Mojo
kernels are independently written from the architectural understanding documented in `teardown/`.

## Layout

- `UPSTREAM_COMMIT` / `BUILD_FLAGS` / `SOURCE_HASHES` / `LICENSE` — the pin.
- `upstream_src/` — the Metal FA implementation at commit `000547513f15` (= Homebrew build 10210).
- `teardown/EXECUTION_DIAGRAM.md` — Stage-1 complete execution diagram (SIMD-group ownership,
  threadgroup memory map, barrier inventory, kargs ABI, negative specification for Qwen3).
- `operator_harness/` — identical-buffer dispatch of the pinned `kernel_flash_attn_ext_f16_dk128_
  dv128` vs. Algenta kernels vs. the CPU Float64 oracle, with counter capture.

## Pre-registered measurement tolerances (FROZEN 2026-08-07, before any candidate results)

Per Plan v1.0, these are recorded before Phase 0 runs and do not move afterward. Any change
requires a written justification in `REALRACE_RESULTS.md` BEFORE the measurement that needs it.

| Quantity | Tolerance | Rationale |
|---|---|---|
| Baseline reproducibility (20 alternating runs, each engine) | relative IQR (p75−p25)/median ≤ 5%; runs with >10% deviation from median flagged as thermal outliers, reported but excluded only if ≥16/20 remain | matches the observed 1940-1956 tok/s (±0.5%) warm spread; leaves room for llama-server variance |
| GPU-role-sum vs. wall time | GPU-time total within [80%, 100%] of host wall at m_rows ≥ 128; gap itemized (submission/host overhead), never ignored | measured 95.3% at m_rows=256, 98.2% at 512; small-M is host-dominated (43.9% at m=8) and excluded from this check |
| Operator output error vs. CPU Float64 | max abs delta ≤ 1.19e-7 × n_keys × (1 + max|out|) × 8 (the established F32 bound family used by the existing Gate-0 suites) | same bound shape `test_residentk_prefill_gemm_kernels.mojo` / `test_residentk_prefill_attn_kernels.mojo` already use |
| LSE error vs. CPU Float64 | same bound family as output error, evaluated per (head,row); LSE is the sharper check and both must pass | `attnk` module precedent: lse depends on every score, output can hide compensating errors |
| Amdahl predicted-vs-observed (per-phase e2e delta) | ±10% | frozen in Plan v1.0; larger mismatch = hidden pack/sync/submission cost, investigate before proceeding |
| Candidate tie/noise threshold | two candidates within 3% median attention time across 3 sessions are a TIE → the simpler architecture wins | below the observed session-to-session thermal noise floor documented in REALRACE_RESULTS.md (decode split-K chain) |
| Determinism soak | 1,000 identical dispatches, zero tolerance: any nonzero output diff = fail | the known Mojo 1.0.0b2 reduction bug manifests at ~1-2%; 1,000 dispatches gives P(miss) < 2e-9 at 2% |

## CORRECTION (2026-08-07): the pinned llama.cpp baseline was 7,117.6 tok/s; re-measured, it's 9,589.6

Phase 0A's own job is "re-pin, don't trust old numbers" — and the re-pin found a real, large
discrepancy. 20 alternating runs (Algenta prefill binary vs. `llama-server /completion` on the
EXACT 256-token manifest prompt, `cache_prompt: false` so every run is a fresh prefill, no
server-side KV reuse across runs):

```
algenta:   median=1999.5 tok/s   relative IQR=3.23%   PASS (tolerance 5%)
llama.cpp: median=9589.6 tok/s   relative IQR=0.59%   PASS (tolerance 5%)
```

**This supersedes the previously-recorded 7,117.6 tok/s figure.** Neither existing RealRace driver
(`realrace_llama_cpp.py`, `realrace_llama_cpp_longctx.py`) actually runs the 256-token manifest
prompt through llama.cpp with a documented methodology — both use a short default text prompt
("The capital of France is") for functional/decode-latency checks, not this prefill benchmark. The
exact methodology behind the original 7,117.6 number is not reconstructable from anything currently
in this repo; plausible explanations include a llama.cpp version difference since that number was
recorded (Homebrew bottle 10210 is CURRENT, installed now — an earlier measurement could predate an
upstream FA optimization) or thermal/contention conditions on this shared development machine at
the time. The fresh number is preferred specifically because its methodology is fully transparent
and reproducible (exact token IDs, `cache_prompt: false`, 20 runs, tight variance) where the old
number's is not.

**Revised required speedup: 9589.6 / 1999.5 = 4.80x end-to-end** (was 3.57x). Revised latency
floor: llama.cpp now runs 256-token prefill in **26.70 ms** (was 36.0 ms). The plan's own
"internal engineering target" and "minimum public victory" numbers need re-deriving from this —
see the plan file's own corrected target table. This is exactly the kind of Phase-0-contradicts-an-
assumption event the frozen plan explicitly allows revising numbers (not architecture) for.

## Phase 0A measured anchors (2026-08-07, this M4 Max, 40 GPU cores)

GPU-role breakdown from `qwen3_probe_counters_i8_allsimd7_prefill.mojo` (sweep extended to
8/32/128/256/512 for this plan; 8 reps per point):

| m_rows | attention share | GPU-time total | wall | implied tok/s |
|---|---|---|---|---|
| 8 | 2.6% | 15.2 ms | 34.6 ms | 231 |
| 32 | 6.5% | 17.2 ms | 21.9 ms | 1,461 |
| 128 | 21.2% | 47.3 ms | 52.0 ms | 2,461 |
| **256** | **35.3%** | **101.3 ms** | **106.3 ms** | **2,408** |
| 512 | 52.6% | 258.6 ms | 263.4 ms | 1,944 |

**`f_256 = 0.353`.** Recomputed targets (formula `S_rest = (1-f)/(1992/P − f/S_attn)`):
- 8x attention + **3.40x rest** → 8,500 tok/s (engineering target)
- 8x attention + **2.92x rest** → 7,500 tok/s (minimum public victory)
- At 256, the non-attention side is 65.5 ms of GPU time; the total budget at 8,500 tok/s is
  ~30.1 ms — so the non-attention side ALONE must shrink from 65.5 ms to ≤ ~25.6 ms even with
  8x-faster attention (35.7 ms → 4.5 ms). Both tracks are mandatory, as the plan states.

Detail at m_rows=256 (% of GPU-time total): attention 35.3%, swiglu 17.5%, qkv_proj 15.4%,
down_proj 15.1%, o_proj 10.0%, ropewrt 5.9%, rmsnorms 0.4%, lmhead+argmax 0.4%, embed 0.03%.

## Operator harness: L0 verified (2026-08-07)

`operator_harness/fa_operator_harness.m` dispatches the PINNED `kernel_flash_attn_ext_f16_dk128_
dv128` directly (byte-exact `ggml_metal_kargs_flash_attn_ext` struct and FC indices, both read
from the vendored headers, never hand-transcribed), at the real Qwen3-0.6B-Base GQA shape
(h_q=16, h_kv=8, d_head=128), causal, one Q-tile/one K-tile. Verified against an independent CPU
Float64 reference: **worst abs delta 1.35e-5**, reproducible bit-for-bit across 3 runs. This is
L0 of the ablation ledger — the fixed point every later candidate (Phase 1's parity replica,
Phase 2A's tournament) is measured against.

**One real bug found and fixed while building this, worth recording**: `blk[ic0]` (the mask-tile
classification byte) is read UNCONDITIONALLY by the main kernel whenever `has_mask=true`
(`ggml-metal.metal:6599-6629`), even when the separate `kernel_flash_attn_ext_blk` pre-pass isn't
dispatched. `blk_cur==0` means "this tile is fully masked, skip it" — a zero-initialized dummy
buffer (the natural first guess for "unused, not dispatching the classifier") silently skips
every tile, giving all-zero output with **no Metal validation error, no crash, nothing to signal
the mistake**. Root-caused by systematic bisection (disable masking entirely → real output;
re-enable with an all-zero mask → still zero → buffer-that-matters had to be `blk`, not the mask
itself). Fix: for a single-tile shape, `blk[0] = 1` (mixed/diagonal — always correct for a shape
where the causal boundary falls inside the one tile that exists). Anyone building on this harness
for multi-tile shapes needs to either dispatch the real `kernel_flash_attn_ext_blk` pre-pass or
compute the classification analytically per the teardown's own §5.1 formula.

## Uses (per Plan v1.0)

1. **Exact operator control** — identical Q/K/V into L0 (pinned kernel), L1 (Mojo replica),
   candidates A/B/C, CPU Float64 oracle.
2. **Counter comparison** — duration, occupancy, threadgroup memory, spills, bytes, barrier time,
   MMA utilization, output/LSE error, cold/warm.
3. **Negative specification** — itemized compile-away targets per specialization (see teardown).
