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

---

## 8. PASS 1 RESULTS — authored and censused on CPU, 2026-09-19 (round 14), zero VM time

`benchmarks/llm_smoke/nvidia_race/fa_g3_tma_probe.cu` exists, **compiles clean for `sm_90a`** under
the calibrated CUDA 12.6 container (`NVCC_RC=0`, `error_lines=0`), and is censused. Calibration was
re-run first and passed **6/6 exact** against the VM's round-7 log (165/172/165/172/166/166), so the
numbers below are evidence and not a local-toolchain artifact.

| kernel | role | BN=32 | BN=64 | spill |
|---|---|---|---|---|
| `_tma_dump_kernel` | probe [0], staging byte-dump | 26 | 26 | 0 |
| `_tma_dlayout_kernel` | probe [1], accumulator layout, identity B | 58 | 64 | 0 |
| `_tma_product_kernel` | probe [2], product identity over a TMA-staged tile | 58 | 64 | 0 |
| `_tma_regA_kernel` | probe [3], m64n128k16 with **register-A** (64 f32 accumulators) | **96** | **96** | **0** |

**12 instantiations, peak 96/255 registers, zero spill in all 12**, across both swizzle modes
(0=none, 1=128B) and both key-block widths.

What that establishes, and what it does not:

* **Established:** the TMA + wgmma *mechanics* compile and do not blow the register file. That
  includes `cp.async.bulk.tensor.2d.shared::cluster.global.tile.mbarrier::complete_tx::bytes`, the
  full mbarrier handshake (`init` / `arrive.expect_tx` / `try_wait.parity` spin), a
  `__grid_constant__ CUtensorMap` kernel parameter, and host-side `cuTensorMapEncodeTiled` over the
  **real** cache layout — 2D map, `globalDim={d,n_keys}`, `globalStrides={kvld*2}` bytes, kv-head
  folded into the base pointer at `hk*d*2`. The heaviest arm, register-A with 64 accumulators, costs
  **96**, leaving **159 registers of headroom** to the 255 cliff. Round 7 died because its RT=2
  shared-B-fragment route needed 255 **and spilled in 24 of 36 instantiations**; this route's
  ceiling is nowhere near that, so the register file is not the obstacle here.
* **NOT established:** 96 is a **floor for the real kernel, not an estimate of it**. These probes
  carry no online softmax, no running max/sum, no alpha rescale, no `kb_min`/`kb_max` window logic,
  no double buffering and no epilogue. Round 8's censused arms (106 descriptor-BN32 / 122
  descriptor-BN64 / 126 register-A) were closer to real because they included more of the loop. The
  honest statement is that the *staging and MMA mechanics* are cheap and the budget question is
  entirely about the softmax/window machinery that has to live alongside them — which is the same
  machinery v2 already fits in 158-172.
* **A defect found and fixed in the probe itself, worth keeping visible:** the first census reported
  *"1 instantiation, 26 registers"* because a `__global__` **template is emitted only where it is
  instantiated**, and `main()` launched just the dump kernel. The three wgmma arms — the only ones
  whose register count decides anything — were never compiled. A `g_tma_force_instantiations[]` array
  taking each variant's address now forces all 12. **Generalises: any census of a templated probe
  must assert the instantiation COUNT matches the intended sweep, or it silently censuses one arm
  and looks like a pass.** Round 7's census did not have this trap because `tc_shim.cu` instantiates
  through explicit macros.

### Design change made during pass 1, and why it is better than §4 proposed

§4 proposed pinning the accumulator layout with an identity B. That still **infers** the operand
layout from a product result — the exact ambiguity that made round 12 inconclusive between "wrong B
descriptor" and "wrong D layout". So probe **[0]** does something strictly better and nearly free:
after the TMA copy it writes the shared-memory bytes **straight back to global**, and the host
recovers the core-matrix permutation the copy engine actually applied by reading which source row
each 16-byte chunk came from (the source pattern makes rows identifiable: only `x==0` is non-zero,
and its value is `y+1`). **That converts the descriptor's LBO/SBO/swizzle from a search space into a
lookup table**, and it is the measurement round 12 lacked. Probes [1]-[3] then run in dependency
order behind it, so a failure in any of them is attributable rather than ambiguous. §4's caveat about
identity B still holds and is now recorded in the file itself: identity is invariant under transpose
but **not** under an arbitrary core-matrix permutation, so [1] alone could not have separated B from
D.

Honest status of the host side: **[0] is fully wired and runnable**; the host-side identity-pattern
buffers and exact-integer comparisons for **[1]/[2]/[3] are pass-2 work** and `main()` says so
explicitly rather than pretending to run them. The kernels compile and are censused, which is what
pass 1 was for.

## 9. PASS 2, PRICED

| step | where | cost | produces |
|---|---|---|---|
| B1. Host drivers for [1]/[2]/[3]: a second source buffer with the identity and `(r+1)(n+1)` patterns, the exact-integer comparison, and per-probe exit codes | **CPU, 0 VM** | one short authoring pass (~the size of pass 1's host side) | a probe binary that returns pinned/refuted per probe |
| B2. Run [0] then [1]-[3] on the box, in that order | **VM, ~20 min** | one short window | the swizzle→(LBO,SBO) lookup table, the D mapping, and whether register-A feedback holds |
| C. `_fa_g3_window4_kernel`: the windowed wgmma kernel against the pinned layout, + host entry + DECLINED fallbacks to v2/v1 + `fa_g3_probe` arms with the host-f64 windowed reference | **CPU, 0 VM** | the largest pass; census is free and calibrated | kernel + a register number for the REAL loop, which is the number that actually matters |
| D. f64 numeric gate + bit-identity vs v2 + A/B cells + same-session TRT re-serve | **VM, ~60-90 min** | one full window | a publishable number or a measured refutation |

**Unchanged from §6: 2 VM windows (~1.5-2 h of cap) and 2 CPU authoring passes**, now with pass 1 of
the two CPU passes spent and its risk retired — the mechanics compile, the tensor-map plumbing is
written against the real layout, and the register file is not the blocker. What remains genuinely
unknown is only what B2 answers: the swizzle→descriptor mapping and the accumulator layout, both of
which [0] and [1] observe directly instead of inferring.

One integration cost now confirmed rather than predicted: the probe needs **`-lcuda`** for
`cuTensorMapEncodeTiled`, on top of the shim's existing `-lcublas -lcudart`, and the host entry must
build and cache one map per (cache pointer, geometry, kv-head-base) with an **explicit** answer to
what happens when the cache is reallocated. Both are in the file's header rather than left to be
discovered during C.

**Recommendation, unchanged and now better-supported:** the prize is still bounded by flashinfer's
21.01 ms, so ~12.5 ms of headroom and ~10 ms after the ~65-80% transfer discount ⇒ rag4096 ≈
1.133x — the largest remaining single-lever win but **not** the route to the 1.15x bar. Pass 1 has
made it cheaper to finish and removed the register-file risk, but it has not changed the prize, so
norm-accum (still unpriced; ~25 min of nsys) remains the better next spend per unit of VM time.

---

## 10. HEADROOM RE-DERIVED ON THE ROUND-15 BASIS — §7's "not the route to the bar" IS SUPERSEDED

Round 15 obtained the first **exactly attributed** bucket census of the shipped default
(`--from-first-attn` region, 5725 records, **555.876 ms** busy, arm `R9_both` = `3c70880f9fe95910`,
1410 MHz), with kernel identities recovered by **differential compilation** rather than by name
substring (see `mojo_kernel_identity.sh` / `rebucket_by_identity.py`). §7's arithmetic used round 6's
idle-gap basis and a post-GQA2 attention figure of ~30 ms; both are now replaced by measurement.

| pool | ms | % of busy | note |
|---|---|---|---|
| GEMM (all `nvjet_*` + `splitKreduce`) | **432.694** | **77.84%** | 484.7 TFLOP/s = **68.8%** of the 1410 MHz-pinned 989 TF/s peak |
| **f16 MLP kernel** | **45.687** | 8.22% | 434 instances = 62 layers x 7, 105 us each. **Larger than the entire attention bucket and never targeted by any round** |
| fused attention (v3 24.564 / 186 inst + v2 13.550 / 248 inst) | **38.114** | 6.86% | the wgmma target |
| unattributed Mojo kernel | 14.225 | 2.56% | 868 instances = 62 x 14; no comptime flag toggles it, identity still open |
| **f16 NORM** (= norm-accum) | **11.782** | 2.12% | 867 instances = 62 x 14 |
| ROPE vector | 6.680 | 1.20% | shipped in round 13 |
| f32->f16 convert (KV16 staging) | 5.867 | 1.06% | **~2x** round 6's ~2-3 ms estimate |

### The wgmma prize, recomputed

* fused attention measured **38.114 ms**; flashinfer comparator **21.01 ms** ⇒ gap **17.104 ms**.
  §7 said "~12.5 ms between our 33.53 and their 21.01" — the measured gap is **37% larger**.
* The bar (rag4096 ≥ 1.15x) against round 13's same-session pair (ours 385.458, TRT 429.400) needs
  our time ≤ **373.39 ms**, i.e. **save 12.07 ms**.
* At the calibrated transfer ratios: 65% ⇒ 11.12 ms ⇒ **1.1471x**; 70% ⇒ 11.97 ms ⇒ **1.1497x**;
  80% ⇒ 13.68 ms ⇒ **1.1550x**.
* **The transfer ratio required to hit exactly 1.15x is 70.5%** — inside the campaign's calibrated
  **65-80%** band, whose midpoint is above it.

**So §7's conclusion is reversed: wgmma is no longer "clearly short of the bar", it is AT THE EDGE of
reach.** But the honesty obligations are larger now, not smaller, because the new number rests on a
conjunction of optimistic assumptions:

1. **Full flashinfer parity is assumed.** The 17.104 ms gap is captured only if the wgmma kernel
   reaches flashinfer's own 21.01 ms exactly. Anything less scales the prize down directly.
2. **The comparator crosses bases.** flashinfer's 21.01 ms was measured in round 6 under a different
   region definition and session. Our 38.114 ms is `--from-first-attn`. If the two buckets do not
   cover identical work, the gap is wrong in an unquantified direction. **This is the single largest
   uncertainty in the number and it should be closed before any window is spent** — re-measure
   flashinfer's attention bucket on the same basis, same session.
3. **Both attention paths must be replaced.** 248 of the 434 attention launches (13.550 ms) still run
   v2, because GQA2 is shape-gated to `n_keys >= 2048`. A wgmma kernel that only replaces the v3 path
   captures at most 24.564 ms of the bucket, and the gap to flashinfer on that subset is not
   separately known.
4. **The transfer ratio is calibrated on two levers**, both of which were *isolated kernel* changes
   measured against a same-configuration control. wgmma is a larger structural change, so 65-80% is an
   extrapolation of the band rather than an instance of it.

### Revised recommendation, and it is not the one §7 gave

Ranked by measured pool, not by campaign momentum:

1. **GEMM — 432.694 ms, 77.84% of busy, at 68.8% of pinned peak.** +5% efficiency is **21.6 ms**,
   which alone would clear the 12.07 ms the bar needs. The 7B lane already has the machinery
   (`ALGENTA_7B_PF_LTALGO`: stage-time cublasLt algorithm search, per-shape, persisted, with
   `lt_shapes_tuned` reported in the banner); **the gemma-3 lane has no cublasLt path at all**, so
   this is a port rather than a new invention. Highest prize, existing pattern, and unlike wgmma its
   comparator is the same library on the same shapes rather than a cross-basis number.
2. **The f16 MLP kernel — 45.687 ms, 8.22% of busy, never examined by any round.** It is bigger than
   all of attention and nobody has ever profiled inside it. Cheapest unexplored pool in the model.
3. **wgmma — 38.114 ms bucket, 17.104 ms ceiling, bar reachable at 70.5% transfer.** Largest
   single-lever structural win, but 2 VM windows + 2 CPU authoring passes, and it carries all four
   caveats above. Do it **after** closing caveat 2, not before.
4. **norm-accum — 11.782 ms measured, 1.73x its 6.83 ms DRAM roof.** Max headroom **4.952 ms** raw,
   **3.2-4.0 ms** after transfer. It is *not* "nothing to win" (it runs at 58% of roof) and *not*
   near round 6's ~16.2 ms either (it is 72.7% of it) — it falls between the two pre-registered
   branches, and its ceiling is ~4x smaller than GEMM's. Lowest priority of the four.

**Bottom line: the bar is reachable, but the route with the best evidence-per-VM-minute is GEMM
algorithm selection, not wgmma.** wgmma moved from "out of reach" to "at the edge" purely because the
attention bucket turned out to be measured 37% larger than the basis §7 used — which is itself the
strongest argument for closing caveat 2 before committing windows to it.
