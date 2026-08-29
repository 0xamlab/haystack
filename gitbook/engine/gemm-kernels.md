---
icon: table-cells
description: Cache-blocked SIMD dense GEMM/GEMV in Float64, NF4/int4/int8 quantized matmul with dequantization fused into the reduction loop, and the shared status/dimension/work-budget contract behind both.
---

# GEMM kernels

Three modules for the operation that dominates a transformer's linear layers and every dense
decision-model fit behind it: `gemm.contract` is the one status vocabulary, dimension check and
work-budget guard the other two call before doing anything; `gemm.blocked` is a cache-blocked,
SIMD, multi-threaded dense matmul and matvec over flat row-major `Float64` buffers; `gemm.quantized`
is the same operation with the weight kept in NF4, int4 or int8 form, dequantized one block at a
time inside the reduction so the full-precision matrix is never materialized. None of this replaces
the tree's existing matrix types — `linalg.mat_mul` and `tensor2d.m2_matmul` are frozen, naive
triple loops with no blocking, no SIMD and no notion of a dtype, and `gemm.blocked` is checked
against `linalg.mat_mul` as a correctness oracle rather than asserted to match it bit for bit.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# A = [[1,2,3],[4,5,6]] (2x3), B = [[7,8],[9,10],[11,12]] (3x2)
a = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
b = [7.0, 8.0, 9.0, 10.0, 11.0, 12.0]

r = runtime.execute("gemm.blocked", "sgemm_flat",
                    [a, b, 2, 2, 3, 1.0, 0.0, False, False])["result"]
r["c"]              # [58.0, 64.0, 139.0, 154.0]
r["backend_used"]   # 1 — cpu_simd
r["flop_count"]      # 24.0 == 2*m*n*k
r["status"]          # 320 — GEMM_OK
```

## The modules

| Module | What it does |
| --- | --- |
| `gemm.contract` | the status vocabulary (320-339), backend/status name lookups, exact shape checking, and the division-based `m*n*k` work budget every other module in this family calls before allocating anything |
| `gemm.blocked` | cache-blocked, SIMD, multi-threaded dense GEMM and GEMV over `Float64` row-major buffers, plus tile planning and a frozen-oracle reference delta |
| `gemm.quantized` | NF4, int4 and int8 matmul/matvec with dequantization fused into the reduction loop, plus a fused-versus-materialized golden delta |

## Why this package exists alongside the frozen matrix types

`linalg.mat_mul` (over a `Matrix` struct) and `tensor2d.m2_matmul` (over `Matrix2D`) both already
multiply matrices, and neither is touched by this package. Across the tree, 16 files mention SIMD
and none mention a GPU — both existing multipliers are naive triple loops that are fine for the
decision workloads they were written for and too slow for a 4096x4096 projection. `gemm.blocked`'s
own `gemm_reference_delta_flat` calls `linalg.mat_mul` directly as its correctness oracle, so the new
driver is checked against the old one rather than declared equivalent to it — and the two are **not**
expected to be bit-identical, because a blocked kernel accumulates in a different order and float
addition is not associative.

## The loop order is the kernel

`C` is row-major, so for `C[i][j] += A[i][kk] * B[kk][j]` the `j` loop walks contiguous memory in
*both* `C` and `B` while `A[i][kk]` is loop-invariant — the reason `sgemm_flat` is `i-k-j` rather
than the textbook `i-j-k`, which walks `B` down a column one cache line per element and gains
nothing from vectorization. Blocking factors default to `TILE_M=64`, `TILE_N=256`, `TILE_K=128`
(one `TILE_K x TILE_N` slice of `B` is roughly 256 KB of `Float64`, an L2-resident working set reused
across all `TILE_M` rows of `A`); `gemm_tile_plan(m, n, k, cache_bytes)` recomputes real factors from
an actual cache size via the frozen `gpu_kernels.tile_size_for_smem`, and reports rising
`arithmetic_intensity` as the problem grows — a bigger GEMM reuses each loaded byte more.

`alpha` scales the product exactly (`sgemm_flat(a, b, 2, 2, 3, 2.0, 0.0, False, False)` doubles the
example above to `c[0] == 116.0`, `c[3] == 308.0`); `beta` scales a prior `C`, which `sgemm_flat`
itself always takes as zero.

**Transposed operands take the scalar path, on purpose.** With `trans_b`, `B`'s `j` stride becomes
`k` rather than `1`, so the contiguity the SIMD path depends on is gone. Rather than pretend
otherwise, `trans_a`/`trans_b` route to a straightforward indexed triple loop and the result reports
`GEMM_BACKEND_SCALAR` (`0`) instead of `GEMM_BACKEND_CPU_SIMD` (`1`). Reading `A` transposed as a
3x2 from the same 6-element buffer (`op(A) = [[1,4],[2,5],[3,6]]`) against a 2x2 `B = [[1,2],[3,4]]`
gives `sgemm_flat(a, b22, 3, 2, 2, 1.0, 0.0, True, False)` a checkable first row,
`c[0] == 13.0, c[1] == 18.0`, tagged `backend_used == 0` — a caller who cares about speed transposes
once up front instead of running the slower kernel under the faster kernel's label.

`gemv_flat(a, x, m, n, trans)` is kept as its own entry point rather than `sgemm_flat` with `n=1`,
because a GEMV reads every weight exactly once and is bandwidth-bound, not compute-bound — routing
it through the blocked path would add tiling bookkeeping to a loop already at its roofline. Row sums
of `[[1,2,3],[4,5,6]]` against `x = [1,1,1]` give `gemv_flat(a, x, 2, 3, False)` an output
`c == [6.0, 15.0]`; the transposed form sums down columns instead, so
`gemv_flat(a, [1,1], 2, 3, True)` returns `n = 3` rows, `c == [5.0, 7.0, 9.0]`, not `m`.

## A budget that charges one factor of a product is not a budget

`gemm.contract` carries two ceilings because they bound different things. `GEMM_MAX_DIM_ELEMS`
(`22369621`, `TX_MAX_ELEMS // 3` — `tensorx`'s per-object ceiling divided by three because `A`, `B`
and `C` are all live for the call) bounds any single buffer. `GEMM_MAX_FLOP_CELLS` (`1 << 36`, about
a few seconds of scalar CPU work) bounds `m * n * k`, a different quantity that is the one that
actually runs away: `m = n = k = 2^20` is three 8&nbsp;MB buffers — memory-legal — and `2^60`
multiply-accumulates, which never returns. `gemm_work_fits(m, n, k, ceiling)` checks this by
division, growing the bound one factor at a time so no oversized product is ever formed:
`gemm_work_fits(3, 6148914691236517206, 3, GEMM_MAX_FLOP_CELLS)` is refused outright rather than
letting the multiply wrap around to something small. `gemm_dims_check(m, n, k, len_a, len_b)` then
checks each operand's own element count, the FLOP budget, and exact — not `>=` — agreement between
declared shape and real buffer length: a buffer longer than its shape says the caller and the kernel
disagree about what the data is, and a silently-used prefix is the wrong-answer failure mode the
check exists for. `gemm_scalars_ok(alpha, beta)` refuses a non-finite `alpha`/`beta` before it can
poison every output element with NaN.

## Not bit-identical to the frozen oracle, and that is stated

`gemm_reference_delta_flat(a, b, m, n, k)` runs `sgemm_flat` and the frozen `linalg.mat_mul` on the
same inputs and diffs them element by element against a per-element tolerance built from
`tensorx.dtype.dtx_tol_for`, scaled by the reduction length `k` — the accumulated rounding a sum can
carry grows with how many terms produced it, so the allowance is built from *that* element's own
magnitude and `k`, never from a max over the whole matrix. The test suite runs six shapes that
deliberately cross every blocking boundary (64 in `m`, 256 in `n`, 128 in `k`) individually and
together, plus a couple of degenerate 1-element shapes; every one agrees with `linalg.mat_mul` within
tolerance, and the worst delta observed across all of them stays under `1e-9`. Asserting bitwise
equality here would either be false or force the blocked kernel back to the frozen accumulation
order — the thing that makes it fast in the first place.

## Quantized: the dequantized weight never leaves a register

A 4096x4096 NF4 weight is 8 MB packed and 128 MB as `Float64`. A "quantized" matmul that
dequantizes into a temporary and then calls a dense kernel has already spent the entire memory
saving before doing any arithmetic — and on token-at-a-time decode, which is bandwidth-bound, that
temporary *is* the cost. So every kernel in `gemm.quantized` reconstructs one weight at a time,
inside the reduction loop, against the real NF4 codebook (`tensorx.pack.nf4_levels()`) or the frozen
`quantization.dequantize_symmetric` for uniform int4/int8 grids.

**The scale index is easy to get silently wrong.** A blockwise scale array has one entry per `block`
consecutive weights in the flattened row-major order the quantizer saw, so the scale for element
`(i, j)` of an m-by-n weight is `scales[(i * n + j) // block]` — not `scales[i]`. Indexing by row
instead is the natural mistake, and it produces a plausible tensor that is wrong by a factor that
varies per block. The test pins this down with two blocks per row, where the two indexings actually
disagree: with codes `[15, 0, 15, 0, 7, 7, 15, 15]` (NF4 level 15 is `+1`, level 0 is `-1`, level 7
is `0`) and scales `[1.0, 2.0, 3.0, 4.0]` over a 2x4 weight with `block = 2`,

```python
codes  = [15, 0, 15, 0, 7, 7, 15, 15]
scales = [1.0, 2.0, 3.0, 4.0]
x      = [1.0, 1.0, 1.0, 1.0]

y = runtime.execute("gemm.quantized", "gemv_nf4_flat", [codes, scales, x, 2, 4, 2])["result"]
y["y"]   # [0.0, 8.0]
```

row 0 is `(+1*1) + (-1*1) + (+1*2) + (-1*2) == 0`, row 1 is `(0*3) + (0*3) + (1*4) + (1*4) == 8` —
the answer scale-indexing-by-row would get instead is different and just as plausible-looking. A
single 1x1 weight at NF4 level 15 with scale 2.5 reconstructs to exactly `levels[15] * 2.5 == 2.5`,
confirming the codebook itself is the real one, not a stand-in.

`gemm_nf4_flat(w_codes, w_scales, x, m, n, k, block)` extends this to a dense right-hand side: the
loop order is `i-k-j` for the same reason as `gemm.blocked`, so each reconstructed weight
`W[i][kk]` is rebuilt once per `(i, kk)` rather than once per output element. With the same 2x4
codes/scales above against an all-ones 4x2 `x`, every output column repeats the GEMV result:
`gemm_nf4_flat(codes, scales, xm, 2, 2, 4, 2)` gives `y == [0.0, 0.0, 8.0, 8.0]`.
`gemv_int_flat(w_codes, w_scales, x, m, n, block, bits)` serves a uniform symmetric int4 (`bits=4`,
codes in `-8..7`) or int8 (`bits=8`, codes in `-128..127`) grid through the frozen
`dequantize_symmetric`, so a uniform code means exactly one thing across the whole tree.

`quantized_gemv_golden_delta(w_codes, w_scales, x, m, n, block)` is the check that makes "same
answer, less memory" a claim rather than an assertion: it materializes the dense weight the slow
way — the exact path this module exists to avoid — multiplies densely, and diffs against the fused
result. The bound is a tolerance, not exact equality: hoisting the block scale out of the fused
kernel's inner loop re-associates the arithmetic (accumulate `sum(level * x)`, then multiply by the
scale once per block) and costs about one ULP against the dequantize-then-dense path. A
scale-indexing bug is wrong by a *factor*, not an ULP, so it still fails this same bound by orders of
magnitude — the tolerance gives up detecting re-association, not the defect it exists to catch.

## Refused, not clamped or silently absorbed

- A code outside the NF4 codebook (`0..15`) or outside its declared int grid (`-8..7` for 4-bit,
  `-128..127` for 8-bit) returns `GEMM_ERR_CODE_OUT_OF_RANGE` rather than clamping to a codebook
  endpoint — a code outside the grid means the weights did not come from this quantizer, and
  silently clamping would return a confident wrong answer.
- `block <= 0` or `block` past `tensorx.pack.PACK_MAX_BLOCK` (`1024`, mirrored here as
  `QGEMM_MAX_BLOCK` and asserted equal to it in the test) is `GEMM_ERR_BLOCK_SIZE`.
- Too few scales for the code count and block size together is its own status,
  `GEMM_ERR_SCALE_LENGTH`, distinct from a generic length mismatch — `elems` codes at `block` per
  scale need exactly `ceil(elems / block)` scales, and checking any two of the three lets the third
  disagree.
- A declared shape larger than the actual buffer is refused before any read: `gemm.blocked` reports
  `GEMM_ERR_A_LENGTH`/`GEMM_ERR_B_LENGTH` depending on which operand disagrees, and `gemm.quantized`
  reports `GEMM_ERR_A_LENGTH` when the code or input-vector buffer is too short. Both modules are
  tested directly against the shape the harness sends on a malformed call (five-element buffers, `5`
  for every dimension) and refuse it cleanly instead of aborting.
- Empty or negative dimensions (`m <= 0`, `n <= 0`, `k <= 0`, `block <= 0`) are `GEMM_ERR_EMPTY_DIM`
  on every entry point, in both the GEMV and GEMM forms.

## Relationship to the GPU path

`gemm.blocked` computes in `Float64`, on the CPU. `accel.gemm_metal` is a separate module — a
threadgroup-tiled GEMM that runs on Apple Silicon's GPU in `Float32`, because Apple Silicon has no
meaningful `Float64` throughput and a `Float64` Metal kernel would be slower than the CPU it is
trying to beat. The two therefore do not compute the same function, and `accel.gemm_metal`'s own
`gemm_metal_agreement` reports the measured delta between the GPU and CPU paths rather than
asserting a tolerance bounded by anything other than `Float32`'s roughly `1e-7` relative precision —
the same "measure and report, don't assert" posture `gemm_reference_delta_flat` takes above, applied
to a genuinely lower-precision computation instead of a reordered one. See
[GPU support](gpu-support.md) for where the Metal serving path fits.

## Verification

`mojo/tests/libs/test_gemm_contract.mojo` pins the status vocabulary to its declared 320-339 range
with no collisions and no overlap with `tensorx`'s 300-319, confirms `GEMM_MAX_DIM_ELEMS ==
TX_MAX_ELEMS // 3` and `GEMM_MAX_FLOP_CELLS == 68719476736` (`2^36`), and exercises the
wrapping-multiply trap directly. `mojo/tests/libs/test_gemm_blocked.mojo` hand-checks the 2x3-by-3x2
product above, the transposed product and its honest backend tag, GEMV row sums both orientations,
and the frozen-oracle delta across six shapes chosen to straddle every tile boundary.
`mojo/tests/libs/test_gemm_quantized.mojo` hand-checks the two-blocks-per-row scale-indexing case
above, the NF4-codebook single-weight reconstruction, the GEMM form's agreement with its own GEMV,
the int4 path against a hand reduction through the frozen dequantizer, and every refusal path listed
above, including the A-Z harness's malformed-call shape.

**Next:** see how `gemm.blocked`'s frozen oracle relates to the rest of the dense-matrix layer in
[Dense 2D matrices (Matrix2D)](ml-tensor2d.md), or browse the [engine catalog](catalog.md).
