# Pricing the TMA-staged wgmma route for the gemma-3 windowed attention kernel

**Status:** scope document, written on CPU at zero VM cost, 2026-09-19 (round 13).
**Trigger:** round 12's layout probe cleanly refuted the hand-staged descriptor route — 18
combinations (9 encodings × both `trans-b` values) all mismatched the exact-integer identity, with
no crashes and the out-of-bounds guard firing 0 times, so the swept space was genuinely complete.

**What this document is for:** deciding whether to spend VM windows on wgmma at all, and if so, in
what order. It is deliberately an estimate *in windows*, not in vibes.

---

## 1. What is refuted, and what is not

Refuted: **assembling operand tiles in shared memory by hand and pointing a wgmma descriptor at
them with a guessed `(LBO, SBO, swizzle, trans)` tuple.**

Not refuted:

* **wgmma itself.** Round 8's census stands and was calibrated 6/6 exact against this box:
  descriptor/descriptor BN=32 = 106 registers, BN=64 = 122, register-A = 126, all zero spill,
  against the shipped v2's 158-172 (BN=32) / 165-172 (BN=64) and round 7's fatal v3 at 255 +
  424-488 B of spill. The instruction and its register profile are the *good* news and they are
  measured, not modelled.
* **The accumulator (D) layout assumption.** This is important and easy to get wrong: the probe
  *cannot* separate "wrong operand descriptor" from "wrong D layout", because both produce wrong
  values in the same registers. A refuted product says at least one of the two is wrong, not that
  the D mapping is. See §4 for the probe change that separates them.

## 2. Why hand-staging failed — the coupling nobody can guess

CUTLASS and flashinfer do not hand-stage. They load operand tiles with **`cp.async.bulk.tensor`
(TMA)** against a `CUtensorMap` built host-side by `cuTensorMapEncodeTiled`, and the tensor map
carries the **swizzle mode**. The copy engine then writes shared memory in the canonical swizzled
core-matrix layout *that the swizzle mode names*, and the wgmma descriptor's `LBO`/`SBO`/`swizzle`
fields are **derived from that same layout type** rather than chosen independently.

So the descriptor fields are not free parameters to search. They are a *function* of how the tile
got into shared memory. Round 12 staged a plain row-major tile and then asked a descriptor to read
it as a swizzled core-matrix grid — which is why every candidate failed, and why the two surviving
diagnostics look the way they do:

* at `LBO=32`, element 0 returned **5** where the assumed layout implies 1, and `(r+1)(c+1)=5` has
  exactly two small solutions, `(0,4)` and `(4,0)` — a row-or-column **permutation**, not noise;
* at the natural row-major encoding (`LBO=16, SBO=256`), exactly **128 of 4096** elements matched
  at `trans-b=0` and **64** at `trans-b=1` — one per thread, and one per two threads. A systematic
  offset signature.

Both point at the **core-matrix internal arrangement** (the 8×8×16-byte atom and its swizzle
phases), not at the strides. Searching more strides would not have found it, which is why the
correct response is to stop searching and start staging the way the hardware expects.

## 3. The design consequence that makes this tractable: Q never needs a descriptor

The blocker looks worse than it is. Split the two products:

* **S = Q[64,128] @ K^T[128,BN]** — use **register-A for Q** and **descriptor-B for K**.
  Q is loaded once per CTA and must be converted f32→f16 with the attention scale folded in at
  `_pf_q_pack_hm_f16`'s rounding point. **TMA cannot convert and cannot scale**, so Q has to be
  hand-staged regardless. But a hand-staged Q read by `ldmatrix` is *exactly what v2 already does
  correctly today* — so Q keeps v2's proven path and never needs a wgmma descriptor at all.
  Cost: 8 k-steps × 4 registers of A-fragment per step, re-read per key block, which is v2's
  existing `qa[8][4]` pattern.
* **O += P[64,BN] @ V[BN,128]** — use **register-A for P** (packed in-register from the S
  accumulator, v2's `fa2_pk` trick) and **descriptor-B for V**. Round 8 censused this at 126
  registers, only **+4** over the descriptor-A form, so the `sP` window, its fences and its shared
  traffic are all deletable.

**Net: only K and V need TMA staging.** That is two tensor maps over the f16 KV-cache staging twin
(the `ALGENTA_G3_PF_KV16` route, which is already the production route and already f16), and no
descriptor is needed for either Q or P. This is the single most important scoping fact in this
document: it reduces the problem from "get wgmma descriptors right for three operands" to "get TMA
right for two".

Tensor-map feasibility for K/V, checked against the actual layout: the cache is
`[n_keys][h_kv][d]` f16 with `kvld = h_kv * d`, and the kernel slices
`[gj][hk*d .. hk*d+d)`. That is expressible as a 2D tensor map with `globalDim = {d, n_keys}`,
`globalStrides = {kvld * 2}` bytes, and a base pointer offset by `hk * d * 2` — so the head index
folds into the base and needs no map of its own. With `d = 128` halves = 256 B per row, a 128B
swizzle atom spans two atoms per row, which is a legal box shape. TMA also requires a 16-byte
aligned base and `boxDim` within hardware limits; both hold here.

## 4. The probe change that separates the two unknowns

Round 12's probe conflated operand layout with accumulator layout. Fix it by making **B the
identity**: set `B[n][k] = (n == k) ? 1 : 0` for `n, k < 16` and `A[r][k] = r*16 + k`. Then
`D[r][n] = A[r][n] = r*16 + n`, so **every accumulator element reads back its own coordinates
directly** and the D layout is pinned independently of what B's descriptor does. Only then run the
`(r+1)(n+1)` product form to test the operand staging.

Three probes, each exact-integer and each independently pass/fail:

1. **D-layout probe** (identity B) — pins the m64nNk16 accumulator → (row, col) mapping. If this
   passes, v2's online softmax (`fa_wmax`/`fa_wsum` over the 4 lanes of a row group) and v2's
   straight-to-global epilogue carry over close to verbatim, because both already index that
   per-warp m16n8 pattern.
2. **TMA operand probe** — stage K/V via `cp.async.bulk.tensor` and confirm the product identity.
   This is the one round 12 could not run, because it needs the tensor map.
3. **Accumulator → register-A identity probe** — feed the D registers back as A (converted to f16,
   packed as v2's `fa2_pk` does) against a known B and require the exact-integer result. If it
   fails, the O product falls back to descriptor-A with an `sP` window, which round 8 priced at
   **122 vs 126 registers** — a 4-register difference, so the kernel is not blocked either way.

## 5. What does NOT change, and why that bounds the risk

The window, the mask and the online softmax are all **accumulator-side** and therefore independent
of how operands reach the tensor cores:

* `kb_min` / `kb_max` and the monotonicity argument (`lo(qpos) = max(0, qpos+1-window)` is monotone
  in `qpos`, so the CTA's first row has the smallest `lo`) — unchanged, and still computed from the
  CTA's 64 rows since one warpgroup is 128 threads at m64, the *same* CTA shape as v2's
  `FA_BM=64` with 4 warps.
* The per-element predicate `j > qpos || j < lo || j >= n_keys` — unchanged, applied to the
  accumulator registers.
* f32 running max/sum, `__expf`, f16 P rounded at the same point, O divided in f32 and rounded once
  at the store — all unchanged.
* **Numerics:** the summation order *does* change (wgmma accumulates k16 per instruction against a
  64-row tile rather than v2's m16n8k16 per warp), so this is the same evidence class as round 5's
  windowed-TC kernel, round 6's raw-mma port and round 7's v3: own build flag, own token-identity
  gate, and a bit-identity comparison against v2 where the math is unchanged. Round 7's v3 achieved
  **216/216 BITIDENT-v2 with 0 BITDIFF**, which is the bar to aim at and shows the bar is reachable.

One real integration cost to budget for: TMA's tensor map is a **driver-API** object
(`cuTensorMapEncodeTiled`), so the shim needs `-lcuda` in addition to its current
`-lcublas -lcudart`, and the host entry must build and cache two tensor maps per (cache pointer,
geometry) pair. Maps are cheap to build but must be rebuilt if the cache is reallocated, which is a
lifetime question the shim's existing staging path has to answer explicitly rather than implicitly.

## 6. Effort estimate, in windows

| step | where | cost | produces |
|---|---|---|---|
| A. Rewrite the probe: identity-B D-layout test, TMA staging, tensor-map plumbing, accumulator→register-A test | **CPU, 0 VM** | one authoring pass | a probe that can *pin* rather than *search* |
| B. Run the three probes | **VM, ~20 min** | one short window | layout pinned, or a second clean refutation |
| C. Write `_fa_g3_window4_kernel` (windowed wgmma) against the pinned layout + host entry + DECLINED fallbacks + `fa_g3_probe` arms with the host-f64 reference | **CPU, 0 VM** | one authoring pass, the largest | kernel + local census (free, calibrated harness) |
| D. f64 numeric gate + bit-identity vs v2 + A/B cells + same-session TRT re-serve | **VM, ~60-90 min** | one full window | a publishable number or a measured refutation |

**Total: 2 VM windows (~1.5-2 h of cap) and 2 CPU authoring passes.** Add one more short VM window
if step B refutes again, to investigate the swizzle atom directly (dump shared memory after a TMA
copy and read the layout off the bytes, rather than inferring it from product results).

The local ptxas harness makes step C's census free and already calibrated (6/6 exact against this
box), so the register question — the one that killed round 7 — is answered before any VM minute is
spent on it. That ordering is the point: **census on CPU, layout on GPU, numerics on GPU, speed
last.**

## 7. Should we do it at all?

The case for: it is the **only** identified route to the remaining attention gap. Round 6 measured
the fused attention kernel at 33.53 ms (+4.77 ms staging) against flashinfer's 21.01 ms, and round
11's GQA2 recovered 3.397 ms of it, leaving ~9 ms. The bar (rag4096 ≥ 1.15x) needs ~18.3 ms from
the published baseline and is unreachable without it — round 7 showed that even *full* attention
plus *full* rope parity yields only 1.1406x.

The case against, honestly: the prize is bounded by flashinfer's own 21.01 ms. Beating the shared-
load bottleneck buys at most the ~12.5 ms between our 33.53 and their 21.01, and at round 11's
measured **~80% probe-to-wall-clock transfer ratio** the realistic wall-clock capture is ~10 ms,
i.e. rag4096 ≈ 377 ms ≈ **1.133x** — still short of 1.15x. So wgmma is best understood as *the
route to the largest remaining single-lever win*, not as the route to the bar.

Cheaper alternatives still on the board, for comparison: **ROPEVEC is certified and untimed**
(modelled -2.2..-2.7 ms, ~80% transfer ⇒ **-1.8 to -2.2 ms**, needs only a bracket, ~25 min);
**norm-accum is unpriced** because round 6's ~16.2 ms is geometry-attributed and the fixed
`--from-first-attn` extractor has still never been run on a real trace (~25 min of nsys to price
it). Both are an order of magnitude cheaper than wgmma for a fraction of the win, and neither is
finished.

**Recommendation:** land ROPEVEC and price norm-accum first — they are hours, not windows — and
treat wgmma as a scoped project with its own budget, undertaken only once those are closed and the
remaining gap is still worth ~10 ms.
