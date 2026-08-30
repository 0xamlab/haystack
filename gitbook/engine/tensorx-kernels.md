---
icon: cube
description: Dtype-tagged byte buffers, elementwise ops, wide-accumulating reductions, N-D shape/broadcasting and low-bit quantization — the flat tensor substrate other kernel families decode through.
---

# Tensor buffer primitives

Seven modules for representing a tensor without a tensor class: a value here is a `List[UInt8]`
tagged with a dtype code and a shape, and every operation on it — arithmetic, reduction,
broadcasting, quantization — takes that same `(bytes, dims, rank, dtype)` shape rather than an
object. There are ten dtype codes, from `float64` down to the 4-bit `nf4` codebook, one status
vocabulary shared across the whole package, and no Python anywhere in the implementation. This is
the layer other kernel families reach into rather than re-derive: `attnk`, `mlpk`, `normk`,
`gemm`, `lossk`, `llmk`, `accel` and `residentk` all import `tensorx.contract`'s finiteness test
directly, and `gemm.quantized` reconstructs one NF4-packed weight at a time, using
`tensorx.pack`'s own codebook, inside its own matmul reduction loop.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# DT_BF16 = 3. Cast pi down to bfloat16 and back with the compiler's own rounding.
runtime.execute("tensorx.dtype", "dtx_round_trip", [3.14159, 3])["result"]
# 3.140625 — matches torch.tensor(3.14159, dtype=torch.float32).to(torch.bfloat16)

ones = [1.0] * 300
bf16_bytes = runtime.execute("tensorx.buffer", "tx_buf_encode_flat", [ones, 300, 3])["result"]

wide = runtime.execute("tensorx.reduce", "tx_reduce_sum", [bf16_bytes, 300, 3])["result"]
narrow = runtime.execute("tensorx.reduce", "tx_reduce_sum_narrow_accum", [bf16_bytes, 300, 3])["result"]

wide["value"]   # 300.0 — decoded to Float64 once, accumulated there
narrow          # 256.0 — same 300 bf16 ones, re-rounded to bf16 after every add
```

Both calls sum the same 300 bytes. The only difference is where the running total lives: decoded
once to `Float64` it reaches the right answer; rounded back to `bfloat16` after every addition —
what an in-place same-width accumulator register does — it saturates at 256.0, because bfloat16's
8-bit significand cannot represent `256.0 + 1.0` as anything but `256.0`. Cross-checked against
real `torch.bfloat16` in-place accumulation before `tensorx.reduce` was written.

## The modules

| Module | What it does |
| --- | --- |
| `tensorx.contract` | the package's status vocabulary (codes 300-319), the one finiteness predicate (`tx_finite`) every other kernel family also imports, and the division-based shape checks (`tx_dims_fit`, `tx_numel_checked`) that a wrapping 64-bit multiply cannot walk past |
| `tensorx.dtype` | the ten-code dtype system from `float64` down to `nf4`: names, bit widths, epsilon/max-finite tables, the single accumulation policy, and `dtx_tol_for`, the tolerance constructor `gemm` and `attnk` both call for their own self-checks |
| `tensorx.buffer` | `TxBuffer` — a `List[UInt8]` tagged with a dtype and a shape — plus the encode/decode functions that bitcast every self-contained dtype to and from little-endian bytes |
| `tensorx.shape` | N-D shape validation, contiguous row-major strides, and NumPy-rule broadcasting, right-aligned, up to rank 8 |
| `tensorx.elementwise` | add/sub/mul/div and an explicit cast over dtype-tagged buffers — decode both operands to `Float64`, compute, re-encode once on the way out |
| `tensorx.reduce` | sum/mean/min/max/variance/stddev over a dtype-tagged buffer, always accumulating in `Float64` regardless of the storage width |
| `tensorx.pack` | blockwise int4/int8 quantization, the 16-level NF4 codebook, nibble packing and double quantization — the low-bit storage `gemm.quantized` reconstructs from inside a matmul |

## No tensor class — a shape is four arguments

There is no `Tensor` struct passed between these modules' public drivers. `tensorx.buffer.TxBuffer`
and `tensorx.shape.TxShape` exist as same-file conveniences for a single call site, but
`tensorx.elementwise` and `tensorx.reduce` both take the struct's fields apart and pass
`(bytes, dims, rank, dtype)` across the file boundary instead. That is not an oversight: this
tree's rule for public drivers is that a struct returned from one has to be declared in the same
file the driver lives in, or the runtime-contract generator silently drops the function, so a
value that needs to cross `tensorx.buffer` into `tensorx.elementwise` travels as its flat parts.
`TX_MAX_RANK` is 8 and `TX_MAX_ELEMS` is `2^26` (67,108,864 — 512 MiB of `Float64`, the resident-
dataset budget's outer limit for one object); every loop in `tensorx.shape` is a fixed
`range(rank)` bounded by the first number, never a recursion.

## Encoding is the compiler's bitcast, not a hand-rolled layout

`tx_buf_encode_flat` and `tx_buf_decode_flat` go through `std.memory.bitcast` between a dtype's
native `Scalar` and an unsigned integer of the same width, then spread that integer across bytes
little-endian. Nothing here re-derives an IEEE bit layout by hand:

```python
runtime.execute("tensorx.buffer", "tx_buf_encode_flat", [[1.5], 1, 2])["result"]
# [0, 0, 192, 63] — float32(1.5), matching struct.pack('<f', 1.5)

runtime.execute("tensorx.buffer", "tx_buf_encode_flat", [[-0.75], 1, 3])["result"]
# [64, 191] — bfloat16(-0.75) bitcasts to uint16 48960 = 0xBF40, little-endian [0x40, 0xBF]
```

Integer dtypes clamp before converting rather than after: `Int64` past a value's representable
range is undefined, not saturating, so `int8`/`uint8` encode clamps in `Float64` first — a value of
`200.0` encoded as `int8` decodes back as `127.0`, and `300.0` as `uint8` decodes back as `255.0`,
never a wrapped negative or an uncaught abort. `int4` and `nf4` report element width `0` and are
refused everywhere a buffer expects a self-contained value (`TX_ERR_DTYPE_UNSUPPORTED_FOR_OP`): a
4-bit code means nothing without the per-block scale that produced it, and that scale lives in a
`tensorx.pack.BlockQuant`, not in a buffer's bytes.

## Broadcasting follows NumPy's rule, right-aligned

`tensorx.shape.tx_shape_broadcast_dims` is the one place the package decides whether two shapes
combine and what the result is; `tensorx.elementwise` calls it rather than carrying a second rule
that could disagree. Comparing dimensions from the trailing axis backward, each pair must be equal
or one of them must be 1, and a shorter shape is padded with implicit **leading** 1s — never
trailing, which would silently broadcast over the wrong axis (batch against sequence, say) instead
of refusing:

```python
runtime.execute("tensorx.shape", "tx_shape_broadcast_dims", [[3], 1, [4, 3], 2])["result"]
# [4, 3] — (3,) pads to (1,3) on the LEADING side, matching numpy.broadcast_shapes((3,), (4,3))

runtime.execute("tensorx.shape", "tx_shape_broadcast_dims", [[5, 1, 4], 3, [1, 3, 4], 3])["result"]
# [5, 3, 4] — matching numpy.broadcast_shapes((5,1,4), (1,3,4))

runtime.execute("tensorx.shape", "tx_shape_broadcastable", [[2, 3], 2, [3, 2], 2])["result"]
# False — (2,3) vs (3,2): neither axis is 1 and 3 != 2, matching numpy's ValueError
```

Every one of these is cross-checked against a real `numpy.broadcast_shapes` call in the test file,
run before the module was written — including the case that catches padding on the wrong side:
`(3,)` against `(3, 1)` broadcasts to `(3, 3)` only because the leading pad makes it `(1, 3)` vs
`(3, 1)`, and a trailing pad would have produced a different, silently wrong answer instead of the
`(3, 3)` numpy actually returns.

## Elementwise ops never promote a dtype mismatch, and never hide a division by zero

`tx_ew_add`/`sub`/`mul`/`div` decode both operands to `Float64`, broadcast, compute, and re-encode
to the shared input dtype — that re-encode is where a real bf16 add's precision loss actually
happens, once, on the way out, never accumulated across intermediate steps:

```python
a = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]   # (2,3), DT_F32 = 2
b = [10.0, 20.0, 30.0]                # (3,)
a_bytes = runtime.execute("tensorx.buffer", "tx_buf_encode_flat", [a, 6, 2])["result"]
b_bytes = runtime.execute("tensorx.buffer", "tx_buf_encode_flat", [b, 3, 2])["result"]

r = runtime.execute("tensorx.elementwise", "tx_ew_add",
                    [a_bytes, [2, 3], 2, 2, b_bytes, [3], 1, 2])["result"]
runtime.execute("tensorx.buffer", "tx_buf_decode_flat", [r["bytes"], 6, 2])["result"]
# [11.0, 22.0, 33.0, 14.0, 25.0, 36.0] — matches numpy's (2,3)+(3,) broadcast exactly
```

A caller with two different dtypes gets `TX_ERR_DTYPE_MISMATCH`, never a silent promotion —
`tx_ew_cast` is the explicit path when a caller genuinely wants one side converted first. And
dividing by zero is a real `inf`/`nan`, not an error, but it is **counted**: dividing all six
elements of the tensor above by an all-zero `(3,)` buffer returns `status == TX_OK` with
`n_non_finite == 6`, the same visibility contract `tensorx.dtype.DtypeCast.n_overflow` uses for a
dtype round trip that overflows.

## Quantization: uniform grids and the NF4 codebook

`tensorx.pack` reuses the frozen `quantization`/`quantization_stack` kernels for the scale, the
dequantization, and the calibrators, and adds only what they cannot do: a code producer that
clamps to a 4-bit grid instead of `quantization.quantize_symmetric`'s hardcoded ±127, and the
16-level NF4 codebook itself (fixed normal-distribution quantiles, not a formula — level 0 is
`-1.0`, level 7 is `0.0`, level 15 is `1.0`).

| Module | What it does |
| --- | --- |
| `quantization` | the frozen symmetric/asymmetric INT8 quantize/dequantize math — scale and zero-point construction, round-trip error, the hardcoded ±127 clamp, and `int4_pack_error`, the oracle `tensorx.pack`'s 4-bit code producer is checked against |
| `quantization_stack` | the frozen calibration layer above it — absmax/percentile calibration, AWQ/SmoothQuant/GPTQ scales, bitsandbytes double quantization, dynamic KV-cache INT8 scale, and the BF16/FP16 round-trip and overflow checks `tensorx.pack` reuses rather than re-deriving |

```python
codes = [-8, 7, 0, -1, 3]
runtime.execute("tensorx.pack", "pack_int4", [codes, 5])["result"]["bytes"]
# [240, 120, 11] — low nibble first: -8 -> nibble 0, 7 -> nibble 15, byte0 = (15<<4)|0 = 240

x = [0.5, -0.25, 1.0, -1.0, 0.125, 0.0, -0.75, 0.33]
bq = runtime.execute("tensorx.pack", "quantize_blockwise", [x, 8, 4, 4])["result"]
bq["n_blocks"], len(bq["codes"]), len(bq["scales"])
# 2, 8, 2 — two 4-element blocks, one absmax scale each
```

Two 4-bit codes share a byte, low nibble first; getting the order backwards does not raise an
error, it silently transposes adjacent weights and trains to a slightly worse model, which is why
the test pins the packed byte by hand rather than only round-tripping. A trailing partial block is
scaled on its own real length rather than padded with zeros, which would drag that block's absmax
down and misquantize the values that are actually there. On the `x` above, NF4 reconstructs with a
lower max absolute error than the uniform int4 grid at the same 4-bit width — the reason NF4
exists, since model weights are approximately normal and a codebook of normal quantiles fits that
distribution better than an evenly-spaced one. `double_quant_scales` then quantizes the per-block
scales themselves against an outer block, the second level of a QLoRA-style layout: at a 64-element
block, one f32 scale per block is otherwise half a bit per weight.

## Refusal, not a confident wrong number

Every module in this family shares the same posture toward inputs it cannot honestly answer:

- **No scale, no value.** `int4`/`nf4` report element width `0`; buffer encode/decode, elementwise
  ops and reductions all refuse them with `TX_ERR_DTYPE_UNSUPPORTED_FOR_OP` rather than reporting a
  value with no scale behind it.
- **A NaN inside a reduction is refused, not summed.** `tx_reduce_sum`/`mean`/etc. reject any
  non-finite live value with `TX_ERR_NON_FINITE` before touching the accumulator, rather than
  letting one NaN turn every subsequent comparison false.
- **Absent is not zero.** `tx_reduce_mean`/`min`/`max`/`variance`/`stddev` over zero elements come
  back `present: False`; `tx_reduce_sum` over zero elements is `present: True`, `value: 0.0` — sum
  of nothing is a real answer, a mean of nothing is not.
- **A count past a buffer's length is refused, not read past.** `n > len(data)` returns an error
  status (or an empty list) rather than an uncatchable abort — the generated A-Z conformance suite
  calls every function with a fixed five-element list and `n = 5`, so this is exactly the class of
  bug that call shape structurally cannot find, and every `tensorx.*` test file adds it back by
  hand.
- **A product is grown by division, never formed and compared.** `tx_dims_fit` and
  `tx_numel_checked` check each factor against the ceiling before multiplying; a wrapping 64-bit
  product like `3 * 6148914691236517206 == 2` is how an equivalent guard was walked past and
  aborted a worker in `sparse_numerics`.

## What builds on this

`tensorx.contract.tx_finite` is imported directly by `attnk.contract`, `attnk.rope`,
`attnk.backward`, `mlpk.activation`, `mlpk.contract`, `normk.contract`, `normk.layernorm`,
`normk.rmsnorm`, `gemm.contract`, `lossk.contract`, `llmk.contract`, `accel.contract` and
`residentk.contract` — it is the one finiteness test those eight kernel families rely on rather
than each defining their own. `tensorx.dtype.dtx_tol_for` is imported by `attnk.tiled`,
`attnk.flash`, `gemm.blocked` and `gemm.quantized` to build the tolerance their own self-checks
compare against (the same shape as `attnk.flash`'s `flash_agrees_with_sdpa`, described in
[Attention kernels](attention-kernels.md)). And `gemm.quantized` imports `tensorx.pack.nf4_levels`
and `PACK_MAX_BLOCK` directly: its fused kernels reconstruct one NF4-packed weight at a time inside
the matmul's own reduction loop, so the dequantized value never leaves a register and a 4096x4096
weight that is 8 MB packed never becomes the 128 MB `Float64` copy a dequantize-then-dense
approach would allocate first.

## Verification

Every numeric claim in this family is pinned against an independent implementation, not just
against itself. Byte layouts are cross-checked against Python's `struct.pack` and the compiler's
own `bitcast`; broadcasting results against real `numpy.broadcast_shapes` calls; bf16 and both fp8
casts against real `torch` casts (`pi -> 3.140625` bf16, `3.25` fp8-e4m3, `3.0` fp8-e5m2; `100.0 ->
96.0` in both fp8 formats); base reductions against Python's `statistics` module
(`variance([1,2,3,4]) == 1.6666666666666667`, `stdev == 1.2909944487358056`); the wide-vs-narrow
accumulation divergence against real `torch.bfloat16` in-place summation; and the new 4-bit code
producer against the frozen `quantization.int4_pack_error` oracle, swept over nine probe values.
See `mojo/tests/libs/test_tensorx_buffer.mojo`, `test_tensorx_shape.mojo`,
`test_tensorx_elementwise.mojo`, `test_tensorx_reduce.mojo`, `test_tensorx_dtype.mojo`,
`test_tensorx_pack.mojo` and `test_tensorx_contract.mojo` for the full suites.

**Next:** see the NF4 codebook and tolerance builder in use inside a real matmul in
[GEMM kernels](gemm-kernels.md), or browse the [Runtime library catalog](runtime-library-catalog.md)
for every module and function.
