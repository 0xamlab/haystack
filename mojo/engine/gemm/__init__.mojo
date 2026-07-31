"""
gemm — dense and quantized matrix multiplication, the CPU reference for the LLM plane. Zero Python.

Why a new package when the tree already multiplies matrices
-------------------------------------------------------------
It has two multipliers and both are frozen, reachable and correct for what they do:
`linalg.mat_mul` over a `Matrix` struct, and `tensor2d.m2_matmul` over `Matrix2D`. Both are naive
triple loops over `Float64` with no blocking, no vectorization and no notion of a dtype. Across 625
files, 16 mention SIMD and none mention a GPU.

That is fine for the decision workloads they were written for and useless for a 4096x4096 projection.
Neither is modified, neither is replaced, and `gemm.blocked.gemm_reference_delta_flat` calls
`linalg.mat_mul` directly as the correctness oracle — so the new driver is checked against the old
one rather than asserted to match it. They are not bit-identical and cannot be: a blocked kernel
accumulates in a different order, and float addition is not associative. The delta is measured and
bounded, not hidden.

Modules
-------
  contract   — status codes 320-339, dimension and work-budget checks
  blocked    — tiled + SIMD dense GEMM, GEMV, tile planning, the frozen-oracle delta
  quantized  — int8/int4/NF4 matmul with dequantization fused into the k-loop

Dependency direction is one-way: `gemm` uses `tensorx` for dtypes, tolerances and finiteness, and
never the reverse. `tensorx.contract.tx_finite` is the package's finiteness predicate here too —
declaring a second one is the `_finite`-written-six-times defect rule 3 names.

Bounding memory is not bounding work
--------------------------------------
A GEMM has three dimensions that each sit comfortably inside an element ceiling and multiply into
something that does not. `m = n = k = 2^20` is three 8 MB buffers and 2^60 multiply-accumulates —
memory-legal, and it never returns. Rule 1c calls this out explicitly: a budget that charges one
factor of a product is not a budget. So `contract.mojo` carries a separate FLOP-cell ceiling checked
by division, and every driver charges `m * n * k` against it before allocating anything.

The dequantized weight is never materialized
----------------------------------------------
`quantized.mojo` exists for one reason: a 4-bit 4096x4096 weight is 8 MB packed and 128 MB as f32. A
"quantized" matmul that dequantizes into a temporary and calls a dense kernel has spent the entire
memory saving before it does any arithmetic, and on a memory-bound decode step that is the whole cost.
Dequantization therefore happens per element inside the k-loop, against the frozen
`quantization.dequantize_symmetric` and the `tensorx.pack` NF4 codebook.
"""
