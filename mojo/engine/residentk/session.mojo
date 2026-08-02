"""
residentk.session — the resident state itself: one `DeviceContext`, one Float32 conversion, one
upload, an in-place KV cache, and the six-dispatch-per-layer decode step. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32
backend: metal
surfaces: none
golden_vectors: mojo/tests/libs/test_residentk_session.mojo
benchmark: benchmarks/llm_smoke/qwen3_generate_metal.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Every entry point here is private, and every launch is gated
--------------------------------------------------------------------------------------
Two independent defences, both required, exactly as `docs/mojo/new-kernel-package-rules.md` and
`accel/launch.mojo` set out:

1. **Private.** Nothing in this file is public, so `apps/runtime/mojo_inventory.py` skips it, it
   never enters the runtime contract, and the generated dispatch never imports it. That is the same
   protection `accel/launch.mojo` relies on, and it is why a launch here cannot reach a Linux CI
   build at all — the worker binary compiles only what `main.mojo` reaches.
2. **Compile-time gated.** Every function here that issues an `enqueue_function` returns a status
   and opens with `@parameter if not RESIDENT_GPU_BUILD: return <shader_toolchain_absent>`. With the
   flag unset the launches are removed BEFORE shader codegen runs, so even if this module were made
   reachable tomorrow a host with no Metal compiler would still build it. A runtime `if` would not
   do this: codegen happens at compile time for anything statically reachable.

The one construct that cannot carry the gate is `_ResidentQwen3.__init__`, because a constructor
must initialise every field and there is no Float32 stand-in for a `DeviceContext`. It is instead
protected structurally: the struct is constructed ONLY from inside a `@parameter if
RESIDENT_GPU_BUILD` branch, so on a build without the flag the constructor is never elaborated.
Verified on this toolchain by compiling this package three ways — default (accelerator present, no
flag), `--target-accelerator=none`, and with the flag — and the first two build, link, and answer
`resident_shader_toolchain_absent`.

Why the compiled kernel handles are struct FIELDS
----------------------------------------------------
Measured on this host, same binary, same trivial kernel, 50 launches:

    enqueue through a struct-held compiled handle   ~180 us
    enqueue_function[kernel, kernel](...)           ~390 us

2.2x, and at 171 dispatches per token that is ~36 ms of a token's latency. So every kernel is
compiled ONCE at session open with `compile_function_unchecked` and the handle is held for the
session's life.

`_unchecked` is not a shortcut, it is the only spelling whose RESULT TYPE can be written down. The
checked `compile_function[k, k]()` returns a type parameterised on the packed argument list, which
has no writable surface syntax, so it cannot be a struct field. The cost of `_unchecked` is that
argument types are not verified at the call site — a swapped pointer compiles and produces wrong
numbers rather than a compile error. That is a real hazard and it is answered by measurement, not
by care: `mojo/tests/libs/test_residentk_session.mojo` checks every kernel against a hand-computed
value, and `benchmarks/llm_smoke/verify_generation.py` checks the whole stack against an
independent `transformers` reference token by token.

What is resident, and what crosses the bus per step
------------------------------------------------------
Resident for the whole session: every weight as Float32 (converted from the Float64 wire ONCE, at
upload), the RoPE cos/sin tables, and the KV cache at `max_ctx` positions.

Per decode step, in: ONE integer — the token id, passed as a kernel scalar argument. The embedding
row is gathered on the device from the resident table, so not even the activation vector is
uploaded.

Per decode step, out: 8 bytes — the winning `(logit, token_id)` pair. The 151,936-wide logits row is
never materialised off-device and never downloaded; the argmax is computed by
`_lmhead_argmax_kernel` and `_argmax_reduce_kernel`. A `map_to_host` costs ~250 us FLAT regardless
of size on this backend, so a per-step download of the logits would cost more than four dispatches.
"""

from std.gpu.host import DeviceBuffer, DeviceContext, DeviceFunction, HostBuffer
from std.sys import has_accelerator, is_defined
from residentk.contract import (
    RESIDENT_ERR_CONTEXT_FULL,
    RESIDENT_ERR_LAUNCH_FAILED,
    RESIDENT_ERR_NO_DEVICE,
    RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT,
    RESIDENT_ERR_UPLOAD_LENGTH,
    RESIDENT_MAX_CONTEXT,
    RESIDENT_OK,
    residentk_context_check,
    residentk_dims_check,
    residentk_dispatch_budget,
)
from std.math import abs as _fabs64
from residentk.kernels import (
    _TG,
    _SUBS,
    _argmax_reduce_kernel,
    _embed_row_kernel,
    _embed_row_kernel_f16,
    _embed_row_kernel_i8,
    _gemv_accum_kernel,
    _gemv_accum_kernel_f16,
    _gemv_accum_kernel_i8,
    _lmhead_argmax_kernel,
    _lmhead_argmax_kernel_f16,
    _lmhead_argmax_kernel_i8,
    _norm_gemv2_swiglu_kernel,
    _norm_gemv2_swiglu_kernel_f16,
    _norm_gemv2_swiglu_kernel_i8,
    _norm_gemv_kernel,
    _norm_gemv_kernel_f16,
    _norm_gemv_kernel_i8,
    _qk_rope_write_kernel,
    _sdpa_kernel,
)

comptime RESIDENT_GPU_BUILD: Bool = is_defined["ALGENTA_GPU"]()
"""Whether this binary was built with `mojo build -D ALGENTA_GPU`. The SAME define
`accel.gemm_metal.ACCEL_GPU_BUILD` and `residentk.probe.RESIDENT_GPU_BUILD` key off; asserted by
`tests/test_accel_gpu_isolation.py`. Unset by default so the ordinary build needs no shader
compiler."""

comptime _LM_BLOCKS: Int = 2048
"""Threadgroups the lm_head projection launches, regardless of vocabulary size.

Not `ceil(vocab / 8)`. MAX's per-dispatch HOST cost grows with the grid on this backend — measured
113 us at 96 threadgroups, 194 us at 4096, and 499 us at 19,008, which is what a
one-group-per-8-columns launch over a 151,936-word vocabulary would need. 2048 groups keeps that
term near its floor while still filling a 40-core GPU roughly 50 threadgroups deep; the kernel walks
the remaining columns with a grid-stride loop."""

comptime _TILE: Int = 64
"""Host-side transpose tile. The upload converts `[in, out]` Float64 into `[out, in]` Float32, and a
naive element loop reads the source with a stride of `out` — a cache miss per element, 4.2M of them
for one QKV matrix. A 64x64 tile is 32 KiB of source and 16 KiB of destination, both inside L2, and
measured about 5x faster on this host. One-time cost either way, but the driver reports it and a
number nobody would publish is a number worth fixing."""


fn _ceil_div(a: Int, b: Int) -> Int:
    return (a + b - 1) // b


@fieldwise_init
struct _StepOut(Copyable, Movable):
    """One decode step's answer: the greedy token, its logit, the dispatches issued, and a status."""

    var token_id: Int
    var logit: Float64
    var dispatches: Int
    var status: Int


@fieldwise_init
struct _LayerGpu(Copyable, Movable):
    """One transformer layer's resident Float32 weights, plus its slice of the KV cache.

    `w_qkv` is the three attention projections CONCATENATED as `[(h_q + 2*h_kv) * d_head, d_model]`
    row-major, and `w_gu` is gate-then-up as `[2 * d_ff, d_model]`. The concatenation is what makes
    "three projections, one dispatch" and "two projections, one dispatch" possible at all; it
    happens once, on the host, during upload.

    `ck`/`cv` are `[RESIDENT_MAX_CONTEXT, h_kv, d_head]` and are written one slot per step in place.
    """

    var ln1: DeviceBuffer[DType.float32]
    var ln2: DeviceBuffer[DType.float32]
    var qn: DeviceBuffer[DType.float32]
    var kn: DeviceBuffer[DType.float32]
    var w_qkv: DeviceBuffer[DType.float32]
    var w_o: DeviceBuffer[DType.float32]
    var w_gu: DeviceBuffer[DType.float32]
    var w_down: DeviceBuffer[DType.float32]
    var ck: DeviceBuffer[DType.float32]
    var cv: DeviceBuffer[DType.float32]


@fieldwise_init
struct _LayerGpuF16(Copyable, Movable):
    """The fp16-weight twin of `_LayerGpu`: the four GEMV weight matrices (`w_qkv`, `w_o`, `w_gu`,
    `w_down`) resident as Float16 instead of Float32 — halving this layer's dominant device-memory
    traffic. `ln1`/`ln2`/`qn`/`kn` (the norm gains, `d_model` or `d_head` elements each) and
    `ck`/`cv` (the KV cache, activations rather than weights) stay Float32: none of the four is a
    weight matrix in the sense the task this package's fp16 arm was built for means, and all four
    are negligible next to the matrices — `2 * d_model + 2 * d_head` elements against
    `n_qkv * d_model` alone.
    """

    var ln1: DeviceBuffer[DType.float32]
    var ln2: DeviceBuffer[DType.float32]
    var qn: DeviceBuffer[DType.float32]
    var kn: DeviceBuffer[DType.float32]
    var w_qkv: DeviceBuffer[DType.float16]
    var w_o: DeviceBuffer[DType.float16]
    var w_gu: DeviceBuffer[DType.float16]
    var w_down: DeviceBuffer[DType.float16]
    var ck: DeviceBuffer[DType.float32]
    var cv: DeviceBuffer[DType.float32]


@fieldwise_init
struct _LayerGpuI8(Copyable, Movable):
    """The int8-weight twin of `_LayerGpu`/`_LayerGpuF16`: the four GEMV weight matrices resident as
    Int8, each with its OWN companion Float32 per-output-row scale buffer (`w_qkv_scale` has
    `n_qkv` elements, `w_o_scale` has `d_model`, `w_gu_scale` has `2 * d_ff`, `w_down_scale` has
    `d_model` — one scale per row of the matrix it belongs to, matching `_norm_gemv_kernel_i8` and
    its siblings' `wscale[j]` indexing exactly). `ln1`/`ln2`/`qn`/`kn` and `ck`/`cv` stay Float32,
    identically to the fp16 twin, for the same reason that struct's docstring gives: none of the
    six is a weight MATRIX in the sense this arm's task was built for, and all six are negligible
    next to the four matrices.
    """

    var ln1: DeviceBuffer[DType.float32]
    var ln2: DeviceBuffer[DType.float32]
    var qn: DeviceBuffer[DType.float32]
    var kn: DeviceBuffer[DType.float32]
    var w_qkv: DeviceBuffer[DType.int8]
    var w_qkv_scale: DeviceBuffer[DType.float32]
    var w_o: DeviceBuffer[DType.int8]
    var w_o_scale: DeviceBuffer[DType.float32]
    var w_gu: DeviceBuffer[DType.int8]
    var w_gu_scale: DeviceBuffer[DType.float32]
    var w_down: DeviceBuffer[DType.int8]
    var w_down_scale: DeviceBuffer[DType.float32]
    var ck: DeviceBuffer[DType.float32]
    var cv: DeviceBuffer[DType.float32]


fn _narrow_into(
    dst: DeviceBuffer[DType.float32], src: List[Float64], n: Int, dst_off: Int
) raises -> Int:
    """Narrow `n` Float64 elements into a device buffer at `dst_off`. No transpose.

    This is the ONE-TIME Float64 -> Float32 conversion the whole design exists to hoist out of the
    per-token path: `accel.gemm_metal` pays it on every call and it is 53% of a decode-shaped GEMM.
    """
    if len(src) != n:
        return RESIDENT_ERR_UPLOAD_LENGTH
    var sp = src.unsafe_ptr()
    with dst.map_to_host() as h:
        for i in range(n):
            h[dst_off + i] = Float32(sp[i])
    return RESIDENT_OK


fn _narrow_transposed_into(
    dst: DeviceBuffer[DType.float32], src: List[Float64], k_in: Int, n_out: Int, row_off: Int
) raises -> Int:
    """Narrow and TRANSPOSE `[k_in, n_out]` Float64 into `[n_out, k_in]` Float32 at row `row_off`.

    The checkpoint on disk is `[in, out]` — `generate_manifest.py` pre-transposes HF's `[out, in]`
    so `gemm.blocked.sgemm_flat`'s fast path is reached during prefill. The GPU wants the opposite:
    one output column's `k` coefficients contiguous, so a 32-lane SIMD group reads 128 contiguous
    bytes per step. See `residentk.kernels`' module docstring for the occupancy measurement that
    makes this worth a one-time transpose.

    Blocked, not element-wise, for the reason `_TILE` documents.
    """
    if len(src) != k_in * n_out:
        return RESIDENT_ERR_UPLOAD_LENGTH
    var sp = src.unsafe_ptr()
    with dst.map_to_host() as h:
        var i0 = 0
        while i0 < k_in:
            var i1 = i0 + _TILE
            if i1 > k_in:
                i1 = k_in
            var j0 = 0
            while j0 < n_out:
                var j1 = j0 + _TILE
                if j1 > n_out:
                    j1 = n_out
                for j in range(j0, j1):
                    var dbase = (row_off + j) * k_in
                    for i in range(i0, i1):
                        h[dbase + i] = Float32(sp[i * n_out + j])
                j0 = j1
            i0 = i1
    return RESIDENT_OK


fn _narrow_into_f16(
    dst: DeviceBuffer[DType.float16], src: List[Float64], n: Int, dst_off: Int
) raises -> Int:
    """The fp16 twin of `_narrow_into`: Float64 -> Float16, no transpose. Used only for the tied
    embedding/lm_head table in the fp16 session — every OTHER fp16 buffer is written through
    `_narrow_transposed_into_f16`, because the checkpoint's weight matrices all need the same
    `[in, out]` -> `[out, in]` transpose the Float32 session pays."""
    if len(src) != n:
        return RESIDENT_ERR_UPLOAD_LENGTH
    var sp = src.unsafe_ptr()
    with dst.map_to_host() as h:
        for i in range(n):
            h[dst_off + i] = Float16(Float32(sp[i]))
    return RESIDENT_OK


fn _narrow_transposed_into_f16(
    dst: DeviceBuffer[DType.float16], src: List[Float64], k_in: Int, n_out: Int, row_off: Int
) raises -> Int:
    """The fp16 twin of `_narrow_transposed_into`: Float64 -> Float16, WITH the same blocked
    `[k_in, n_out]` -> `[n_out, k_in]` transpose. Narrowing to Float16 rather than Float32 changes
    only the element written at `h[dbase + i]`; the access pattern, the tiling and the reason for
    both are identical to the Float32 path — see that function's docstring."""
    if len(src) != k_in * n_out:
        return RESIDENT_ERR_UPLOAD_LENGTH
    var sp = src.unsafe_ptr()
    with dst.map_to_host() as h:
        var i0 = 0
        while i0 < k_in:
            var i1 = i0 + _TILE
            if i1 > k_in:
                i1 = k_in
            var j0 = 0
            while j0 < n_out:
                var j1 = j0 + _TILE
                if j1 > n_out:
                    j1 = n_out
                for j in range(j0, j1):
                    var dbase = (row_off + j) * k_in
                    for i in range(i0, i1):
                        h[dbase + i] = Float16(Float32(sp[i * n_out + j]))
                j0 = j1
            i0 = i1
    return RESIDENT_OK


comptime _I8_MAX: Float64 = 127.0
"""The quantized range's positive extreme. `[-127, 127]`, NOT `[-128, 127]` — see
`_quantize_row_i8`'s docstring for why the range is deliberately kept symmetric rather than using
Int8's full asymmetric range."""


fn _quantize_row_i8(v: Float64, inv_scale: Float64) -> Int8:
    """Round-half-away-from-zero, clamp to `[-127, 127]`. `inv_scale` is `1.0 / scale`, passed
    rather than dividing by `scale` at every call so the one division per row happens once, in the
    caller, not once per element."""
    var q = v * inv_scale
    var r = Int(q + 0.5) if q >= 0.0 else Int(q - 0.5)
    if r > 127:
        r = 127
    if r < -127:
        r = -127
    return Int8(r)


fn _quantize_into_i8(
    dst_w: DeviceBuffer[DType.int8], dst_scale: DeviceBuffer[DType.float32],
    src: List[Float64], n_rows: Int, width: Int, row_off: Int, scale_off: Int,
) raises -> Int:
    """Per-output-row symmetric int8 quantization, NO transpose — `src` is already `[n_rows,
    width]` row-major, exactly the tied embedding/lm_head table's own on-disk layout, so (unlike
    `_quantize_transposed_into_i8`) each row is already contiguous and needs only one pass: find
    that row's max `|value|`, derive its scale, quantize the same row immediately.

    Scale is `max(|row|) / 127` — the largest representable magnitude in the row maps to exactly
    127 (or -127), not 128, keeping the quantized range symmetric around zero so a dequantized
    value can never have a lopsided negative extreme with no positive counterpart. An all-zero row
    gets `scale = 1.0` (never zero), so no dequant multiply downstream can divide by zero or read a
    NaN scale — the same "never a zero divisor" discipline `residentk_scalars_ok` enforces for
    `eps`/`scale` elsewhere in this package.
    """
    if len(src) != n_rows * width:
        return RESIDENT_ERR_UPLOAD_LENGTH
    var sp = src.unsafe_ptr()
    with dst_scale.map_to_host() as hs:
        with dst_w.map_to_host() as hw:
            for r in range(n_rows):
                var base = r * width
                var maxabs = 0.0
                for i in range(width):
                    var av = _fabs64(sp[base + i])
                    if av > maxabs:
                        maxabs = av
                var scale = (maxabs / _I8_MAX) if maxabs > 0.0 else 1.0
                hs[scale_off + r] = Float32(scale)
                var inv_scale = 1.0 / scale
                var dbase = (row_off + r) * width
                for i in range(width):
                    hw[dbase + i] = _quantize_row_i8(sp[base + i], inv_scale)
    return RESIDENT_OK


fn _quantize_transposed_into_i8(
    dst_w: DeviceBuffer[DType.int8], dst_scale: DeviceBuffer[DType.float32],
    src: List[Float64], k_in: Int, n_out: Int, row_off: Int, scale_off: Int,
) raises -> Int:
    """Narrow, TRANSPOSE, and per-output-row symmetric-int8-quantize `[k_in, n_out]` Float64 into
    `[n_out, k_in]` Int8 at row `row_off`, with one Float32 scale per row at `scale_off`. The
    weight-matrix case: `src` is `[k_in, n_out]` (the checkpoint's own `[in, out]` layout), so
    output row `j`'s `k_in` elements are the STRIDED column `src[i * n_out + j]`, not a contiguous
    run the way `_quantize_into_i8`'s embedding-table case is.

    TWO blocked passes over `_narrow_transposed_into`'s own tiling (see that function's docstring
    for why blocking matters — the same cache-locality argument applies twice here): a row's scale
    depends on EVERY element of that row, so no element can be quantized until the whole row has
    been scanned. Pass 1 accumulates each output row's max `|value|` into `dst_scale`, tile by
    tile, then converts every accumulated max to a scale in one pass over the `n_out` rows. Pass 2
    re-reads `src` with the identical tile order and, for each element, reads the now-fixed scale
    for its row and quantizes into `dst_w`. Same symmetric-range, never-zero-scale discipline as
    `_quantize_into_i8` — see that function's docstring.
    """
    if len(src) != k_in * n_out:
        return RESIDENT_ERR_UPLOAD_LENGTH
    var sp = src.unsafe_ptr()

    # ── pass 1: per-row max |value|, blocked, then converted to a scale ──
    with dst_scale.map_to_host() as hs:
        for j in range(n_out):
            hs[scale_off + j] = 0.0
        var i0 = 0
        while i0 < k_in:
            var i1 = i0 + _TILE
            if i1 > k_in:
                i1 = k_in
            var j0 = 0
            while j0 < n_out:
                var j1 = j0 + _TILE
                if j1 > n_out:
                    j1 = n_out
                for j in range(j0, j1):
                    var m = hs[scale_off + j]
                    for i in range(i0, i1):
                        var av = Float32(_fabs64(sp[i * n_out + j]))
                        if av > m:
                            m = av
                    hs[scale_off + j] = m
                j0 = j1
            i0 = i1
        for j in range(n_out):
            var m = hs[scale_off + j]
            hs[scale_off + j] = (m / Float32(_I8_MAX)) if m > 0.0 else 1.0

    # ── pass 2: transpose + quantize, using the now-fixed scale ──
    with dst_scale.map_to_host() as hs2:
        with dst_w.map_to_host() as hw:
            var i0b = 0
            while i0b < k_in:
                var i1b = i0b + _TILE
                if i1b > k_in:
                    i1b = k_in
                var j0b = 0
                while j0b < n_out:
                    var j1b = j0b + _TILE
                    if j1b > n_out:
                        j1b = n_out
                    for j in range(j0b, j1b):
                        var scale = Float64(hs2[scale_off + j])
                        var inv_scale = 1.0 / scale
                        var dbase = (row_off + j) * k_in
                        for i in range(i0b, i1b):
                            hw[dbase + i] = _quantize_row_i8(sp[i * n_out + j], inv_scale)
                    j0b = j1b
                i0b = i1b
    return RESIDENT_OK


struct _ResidentQwen3(Movable):
    """Everything a decode session holds on the device, alive across the whole generation.

    `Movable` is mandatory, not decorative: without it `var moved = session^` fails with
    `cannot transfer value into destination, because '_ResidentQwen3' doesn't conform to 'Movable'`.
    `DeviceContext`, `DeviceBuffer`, `HostBuffer` and `DeviceFunction` are all themselves
    Copyable+Movable, so a `List[_LayerGpu]` of device buffers is a legal field.

    HAZARD, recorded because the compiler will not catch it: there is no lifetime tie between a
    `DeviceBuffer` and the `DeviceContext` it came from. Nothing stops the context being dropped
    first, and the result is a use-after-free with no diagnostic. Keeping every buffer in the same
    struct as its context is the discipline that prevents it; do not hand a buffer out past this
    struct's own lifetime.
    """

    var ctx: DeviceContext
    var d_model: Int
    var h_q: Int
    var h_kv: Int
    var d_head: Int
    var d_ff: Int
    var n_layers: Int
    var vocab: Int
    var max_ctx: Int
    var eps: Float32
    var scale: Float32

    var layers: List[_LayerGpu]
    var embed: DeviceBuffer[DType.float32]
    var final_norm: DeviceBuffer[DType.float32]
    var cos_t: DeviceBuffer[DType.float32]
    var sin_t: DeviceBuffer[DType.float32]

    var hidden: DeviceBuffer[DType.float32]
    var qkv: DeviceBuffer[DType.float32]
    var q_rot: DeviceBuffer[DType.float32]
    var attn_out: DeviceBuffer[DType.float32]
    var act: DeviceBuffer[DType.float32]
    var blk_val: DeviceBuffer[DType.float32]
    var blk_idx: DeviceBuffer[DType.int32]
    var out_val: DeviceBuffer[DType.float32]
    var out_idx: DeviceBuffer[DType.int32]
    var host_val: HostBuffer[DType.float32]
    var host_idx: HostBuffer[DType.int32]

    var f_embed: DeviceFunction[
        _embed_row_kernel, None, target = DeviceContext.default_device_info.target()
    ]
    var f_norm_gemv: DeviceFunction[
        _norm_gemv_kernel, None, target = DeviceContext.default_device_info.target()
    ]
    var f_gemv_acc: DeviceFunction[
        _gemv_accum_kernel, None, target = DeviceContext.default_device_info.target()
    ]
    var f_gu: DeviceFunction[
        _norm_gemv2_swiglu_kernel, None, target = DeviceContext.default_device_info.target()
    ]
    var f_rope: DeviceFunction[
        _qk_rope_write_kernel, None, target = DeviceContext.default_device_info.target()
    ]
    var f_sdpa: DeviceFunction[
        _sdpa_kernel, None, target = DeviceContext.default_device_info.target()
    ]
    var f_lm: DeviceFunction[
        _lmhead_argmax_kernel, None, target = DeviceContext.default_device_info.target()
    ]
    var f_argmax: DeviceFunction[
        _argmax_reduce_kernel, None, target = DeviceContext.default_device_info.target()
    ]

    fn __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
    ) raises:
        """Open the context, compile every kernel, and allocate every resident buffer. ONCE.

        Called only from inside a `@parameter if RESIDENT_GPU_BUILD` branch — see the module
        docstring for why a constructor cannot carry the gate itself.

        The caller must have validated the shape with `residentk_dims_check` first. This constructor
        does not re-check: it is private, it has exactly two call sites in the tree, and a
        constructor that returned a status would have to leave the fields in some state anyway.
        """
        self.ctx = DeviceContext()
        self.d_model = d_model
        self.h_q = h_q
        self.h_kv = h_kv
        self.d_head = d_head
        self.d_ff = d_ff
        self.n_layers = n_layers
        self.vocab = vocab
        self.max_ctx = max_ctx
        self.eps = Float32(eps)
        self.scale = Float32(scale)

        var n_qkv = (h_q + 2 * h_kv) * d_head
        var n_pairs = d_head // 2

        self.layers = List[_LayerGpu]()
        for _ in range(n_layers):
            self.layers.append(
                _LayerGpu(
                    self.ctx.enqueue_create_buffer[DType.float32](d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](d_head),
                    self.ctx.enqueue_create_buffer[DType.float32](d_head),
                    self.ctx.enqueue_create_buffer[DType.float32](n_qkv * d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](d_model * h_q * d_head),
                    self.ctx.enqueue_create_buffer[DType.float32](2 * d_ff * d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](d_model * d_ff),
                    self.ctx.enqueue_create_buffer[DType.float32](max_ctx * h_kv * d_head),
                    self.ctx.enqueue_create_buffer[DType.float32](max_ctx * h_kv * d_head),
                )
            )

        self.embed = self.ctx.enqueue_create_buffer[DType.float32](vocab * d_model)
        self.final_norm = self.ctx.enqueue_create_buffer[DType.float32](d_model)
        self.cos_t = self.ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)
        self.sin_t = self.ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)

        self.hidden = self.ctx.enqueue_create_buffer[DType.float32](d_model)
        self.qkv = self.ctx.enqueue_create_buffer[DType.float32](n_qkv)
        self.q_rot = self.ctx.enqueue_create_buffer[DType.float32](h_q * d_head)
        self.attn_out = self.ctx.enqueue_create_buffer[DType.float32](h_q * d_head)
        self.act = self.ctx.enqueue_create_buffer[DType.float32](d_ff)
        self.blk_val = self.ctx.enqueue_create_buffer[DType.float32](_LM_BLOCKS)
        self.blk_idx = self.ctx.enqueue_create_buffer[DType.int32](_LM_BLOCKS)
        self.out_val = self.ctx.enqueue_create_buffer[DType.float32](1)
        self.out_idx = self.ctx.enqueue_create_buffer[DType.int32](1)
        # Pinned host buffers for the 8-byte per-step readback. Indexable directly and measured at
        # 0 us to write, against ~250 us FLAT for `map_to_host()` regardless of size — which is why
        # no per-step path in this file calls `map_to_host`.
        self.host_val = self.ctx.enqueue_create_host_buffer[DType.float32](1)
        self.host_idx = self.ctx.enqueue_create_host_buffer[DType.int32](1)

        # Compiled once. See the module docstring: 180 us per launch through a held handle against
        # 390 us through the `enqueue_function[k, k]` parameter form.
        self.f_embed = self.ctx.compile_function_unchecked[_embed_row_kernel]()
        self.f_norm_gemv = self.ctx.compile_function_unchecked[_norm_gemv_kernel]()
        self.f_gemv_acc = self.ctx.compile_function_unchecked[_gemv_accum_kernel]()
        self.f_gu = self.ctx.compile_function_unchecked[_norm_gemv2_swiglu_kernel]()
        self.f_rope = self.ctx.compile_function_unchecked[_qk_rope_write_kernel]()
        self.f_sdpa = self.ctx.compile_function_unchecked[_sdpa_kernel]()
        self.f_lm = self.ctx.compile_function_unchecked[_lmhead_argmax_kernel]()
        self.f_argmax = self.ctx.compile_function_unchecked[_argmax_reduce_kernel]()

    fn device_name(self) raises -> String:
        return self.ctx.name()

    fn dispatch_budget(self) -> Int:
        return residentk_dispatch_budget(self.n_layers)

    fn upload_globals(
        mut self, embed: List[Float64], final_norm: List[Float64],
        cos_t: List[Float64], sin_t: List[Float64], n_pos: Int,
    ) raises -> Int:
        """The tied embedding/lm_head table, the final norm gain, and the RoPE tables.

        The embedding table is NOT transposed: `[vocab, d_model]` is already "one row per output
        column" for the lm_head projection AND "one row per token" for the gather, so one copy
        serves both — the same observation `prepare_qwen3_checkpoint.py` makes on the CPU side.
        """
        var n_pairs = self.d_head // 2
        if n_pos > self.max_ctx:
            return RESIDENT_ERR_CONTEXT_FULL
        var s = _narrow_into(self.embed, embed, self.vocab * self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(self.final_norm, final_norm, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        if len(cos_t) < n_pos * n_pairs or len(sin_t) < n_pos * n_pairs:
            return RESIDENT_ERR_UPLOAD_LENGTH
        with self.cos_t.map_to_host() as h:
            for i in range(n_pos * n_pairs):
                h[i] = Float32(cos_t[i])
        with self.sin_t.map_to_host() as h:
            for i in range(n_pos * n_pairs):
                h[i] = Float32(sin_t[i])
        return RESIDENT_OK

    fn upload_layer(
        mut self, layer: Int,
        ln1: List[Float64], ln2: List[Float64], qn: List[Float64], kn: List[Float64],
        wq: List[Float64], wk: List[Float64], wv: List[Float64], wo: List[Float64],
        wgate: List[Float64], wup: List[Float64], wdown: List[Float64],
    ) raises -> Int:
        """One layer's eleven checkpoint tensors, narrowed and packed into four device matrices.

        `wq`/`wk`/`wv` land in ONE `[(h_q + 2*h_kv) * d_head, d_model]` buffer at row offsets 0,
        `h_q*d_head` and `(h_q+h_kv)*d_head`; `wgate`/`wup` land in one `[2*d_ff, d_model]` buffer at
        rows 0 and `d_ff`. That packing is what makes the fused dispatches possible, and it costs
        nothing at run time because it happens here, once.
        """
        if layer < 0 or layer >= self.n_layers:
            return RESIDENT_ERR_UPLOAD_LENGTH
        ref lw = self.layers[layer]
        var s = _narrow_into(lw.ln1, ln1, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(lw.ln2, ln2, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(lw.qn, qn, self.d_head, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(lw.kn, kn, self.d_head, 0)
        if s != RESIDENT_OK:
            return s

        var n_q = self.h_q * self.d_head
        var n_kv = self.h_kv * self.d_head
        s = _narrow_transposed_into(lw.w_qkv, wq, self.d_model, n_q, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into(lw.w_qkv, wk, self.d_model, n_kv, n_q)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into(lw.w_qkv, wv, self.d_model, n_kv, n_q + n_kv)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into(lw.w_o, wo, n_q, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into(lw.w_gu, wgate, self.d_model, self.d_ff, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into(lw.w_gu, wup, self.d_model, self.d_ff, self.d_ff)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into(lw.w_down, wdown, self.d_ff, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        return RESIDENT_OK

    fn seal(mut self) raises -> Int:
        """Drain every upload before the first step. One synchronize for the whole load."""
        self.ctx.synchronize()
        return RESIDENT_OK

    fn step(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """ONE token: embed, `n_layers` fused layers, lm_head, argmax. Returns the greedy choice.

        `pos` is the absolute position of THIS token and also the KV-cache slot it writes. Attention
        then runs over `pos + 1` keys, which is every key that exists — see `_sdpa_kernel` on why no
        mask is applied and why that is a claim rather than an omission.

        The dispatch count is asserted against `residentk_dispatch_budget(n_layers)` by this
        function's own return value, and by `mojo/tests/libs/test_residentk_session.mojo`.
        """

        @parameter
        if not RESIDENT_GPU_BUILD:
            # Removed before shader codegen; this is what a GPU-less host compiles and runs.
            return _StepOut(-1, 0.0, 0, RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            if pos < 0 or pos >= self.max_ctx:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_CONTEXT_FULL)
            if token_id < 0 or token_id >= self.vocab:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_UPLOAD_LENGTH)

            var n_q = self.h_q * self.d_head
            var n_kv = self.h_kv * self.d_head
            var n_qkv = n_q + 2 * n_kv
            var n_keys = pos + 1
            var issued = 0

            # ── the embedding row, gathered on-device from the resident table ──
            self.ctx.enqueue_function_unchecked(
                self.f_embed,
                self.hidden.unsafe_ptr(), self.embed.unsafe_ptr(), token_id, self.d_model,
                grid_dim=_ceil_div(self.d_model, _TG), block_dim=_TG,
            )
            issued += 1

            for layer in range(self.n_layers):
                ref lw = self.layers[layer]

                # 1 ── rmsnorm(input_layernorm) + fused Q/K/V projection
                self.ctx.enqueue_function_unchecked(
                    self.f_norm_gemv,
                    self.qkv.unsafe_ptr(), self.hidden.unsafe_ptr(), lw.ln1.unsafe_ptr(),
                    lw.w_qkv.unsafe_ptr(), self.d_model, n_qkv, self.eps,
                    grid_dim=_ceil_div(n_qkv, _SUBS), block_dim=_TG,
                )
                # 2 ── q_norm + k_norm + RoPE + the in-place KV-cache slot write
                self.ctx.enqueue_function_unchecked(
                    self.f_rope,
                    self.q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                    self.qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                    self.cos_t.unsafe_ptr(), self.sin_t.unsafe_ptr(),
                    pos, self.h_q, self.h_kv, self.d_head, self.eps,
                    grid_dim=self.h_q + self.h_kv, block_dim=self.d_head,
                )
                # 3 ── attention over every cached key, online softmax
                self.ctx.enqueue_function_unchecked(
                    self.f_sdpa,
                    self.attn_out.unsafe_ptr(), self.q_rot.unsafe_ptr(),
                    lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                    n_keys, self.h_q, self.h_kv, self.d_head, self.scale,
                    grid_dim=self.h_q, block_dim=self.d_head,
                )
                # 4 ── o_proj accumulated straight into the residual stream
                self.ctx.enqueue_function_unchecked(
                    self.f_gemv_acc,
                    self.hidden.unsafe_ptr(), self.attn_out.unsafe_ptr(), lw.w_o.unsafe_ptr(),
                    n_q, self.d_model,
                    grid_dim=_ceil_div(self.d_model, _SUBS), block_dim=_TG,
                )
                # 5 ── rmsnorm(post_attention_layernorm) + gate/up + SwiGLU
                self.ctx.enqueue_function_unchecked(
                    self.f_gu,
                    self.act.unsafe_ptr(), self.hidden.unsafe_ptr(), lw.ln2.unsafe_ptr(),
                    lw.w_gu.unsafe_ptr(), self.d_model, self.d_ff, self.eps,
                    grid_dim=_ceil_div(self.d_ff, _SUBS), block_dim=_TG,
                )
                # 6 ── down_proj accumulated straight into the residual stream
                self.ctx.enqueue_function_unchecked(
                    self.f_gemv_acc,
                    self.hidden.unsafe_ptr(), self.act.unsafe_ptr(), lw.w_down.unsafe_ptr(),
                    self.d_ff, self.d_model,
                    grid_dim=_ceil_div(self.d_model, _SUBS), block_dim=_TG,
                )
                issued += 6

            # ── final rmsnorm + lm_head + per-threadgroup argmax, then the reduce ──
            var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
            self.ctx.enqueue_function_unchecked(
                self.f_lm,
                self.blk_val.unsafe_ptr(), self.blk_idx.unsafe_ptr(), self.hidden.unsafe_ptr(),
                self.final_norm.unsafe_ptr(), self.embed.unsafe_ptr(),
                self.d_model, self.vocab, self.eps, n_iters,
                grid_dim=_LM_BLOCKS, block_dim=_TG,
            )
            self.ctx.enqueue_function_unchecked(
                self.f_argmax,
                self.out_val.unsafe_ptr(), self.out_idx.unsafe_ptr(),
                self.blk_val.unsafe_ptr(), self.blk_idx.unsafe_ptr(), _LM_BLOCKS,
                grid_dim=1, block_dim=_TG,
            )
            issued += 2

            # ── 8 bytes back, not 608 KB ──
            self.ctx.enqueue_copy(self.host_val, self.out_val)
            self.ctx.enqueue_copy(self.host_idx, self.out_idx)
            self.ctx.synchronize()
            var tok = Int(self.host_idx.unsafe_ptr()[0])
            var lg = Float64(self.host_val.unsafe_ptr()[0])
            if tok < 0 or tok >= self.vocab:
                # The device argmax found no candidate. Reported rather than returned as a token:
                # a negative id would index the embedding table on the NEXT step, which on a GPU is
                # silent corruption rather than a bounds abort.
                return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
            return _StepOut(tok, lg, issued, RESIDENT_OK)


struct _ResidentQwen3F16(Movable):
    """The fp16-weight twin of `_ResidentQwen3`: identical session, identical dispatch plan,
    identical `step()` contract — the ONLY difference is that `w_qkv`/`w_o`/`w_gu`/`w_down` per
    layer and the tied `embed`/lm_head table are resident as Float16 rather than Float32, read
    through the `_f16` kernel twins.

    Additive, per the task this struct was built for: `_ResidentQwen3` above is untouched, still
    the Float32 arm, still what a caller gets by constructing that type. This struct exists
    alongside it so the two can be benchmarked and verified against the SAME reference from the
    SAME checkpoint, isolating precision as the only variable.

    Every field that is NOT one of those five buffers keeps the Float32 type `_ResidentQwen3` uses:
    activations (`hidden`, `qkv`, `q_rot`, `attn_out`, `act`), the KV cache (`ck`/`cv` inside
    `_LayerGpuF16`), the norm gains, the RoPE tables, and the argmax scratch. Mixed precision, not a
    half-precision session — see `_HP`'s docstring in `residentk.kernels`.
    """

    var ctx: DeviceContext
    var d_model: Int
    var h_q: Int
    var h_kv: Int
    var d_head: Int
    var d_ff: Int
    var n_layers: Int
    var vocab: Int
    var max_ctx: Int
    var eps: Float32
    var scale: Float32

    var layers: List[_LayerGpuF16]
    var embed: DeviceBuffer[DType.float16]
    var final_norm: DeviceBuffer[DType.float32]
    var cos_t: DeviceBuffer[DType.float32]
    var sin_t: DeviceBuffer[DType.float32]

    var hidden: DeviceBuffer[DType.float32]
    var qkv: DeviceBuffer[DType.float32]
    var q_rot: DeviceBuffer[DType.float32]
    var attn_out: DeviceBuffer[DType.float32]
    var act: DeviceBuffer[DType.float32]
    var blk_val: DeviceBuffer[DType.float32]
    var blk_idx: DeviceBuffer[DType.int32]
    var out_val: DeviceBuffer[DType.float32]
    var out_idx: DeviceBuffer[DType.int32]
    var host_val: HostBuffer[DType.float32]
    var host_idx: HostBuffer[DType.int32]

    var f_embed: DeviceFunction[
        _embed_row_kernel_f16, None, target = DeviceContext.default_device_info.target()
    ]
    var f_norm_gemv: DeviceFunction[
        _norm_gemv_kernel_f16, None, target = DeviceContext.default_device_info.target()
    ]
    var f_gemv_acc: DeviceFunction[
        _gemv_accum_kernel_f16, None, target = DeviceContext.default_device_info.target()
    ]
    var f_gu: DeviceFunction[
        _norm_gemv2_swiglu_kernel_f16, None, target = DeviceContext.default_device_info.target()
    ]
    var f_rope: DeviceFunction[
        _qk_rope_write_kernel, None, target = DeviceContext.default_device_info.target()
    ]
    var f_sdpa: DeviceFunction[
        _sdpa_kernel, None, target = DeviceContext.default_device_info.target()
    ]
    var f_lm: DeviceFunction[
        _lmhead_argmax_kernel_f16, None, target = DeviceContext.default_device_info.target()
    ]
    var f_argmax: DeviceFunction[
        _argmax_reduce_kernel, None, target = DeviceContext.default_device_info.target()
    ]

    fn __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
    ) raises:
        """Open the context, compile every kernel, and allocate every resident buffer. ONCE.

        Same call-site discipline as `_ResidentQwen3.__init__` — see that constructor's docstring
        and the module docstring for why the compile-time gate cannot sit on a constructor.
        """
        self.ctx = DeviceContext()
        self.d_model = d_model
        self.h_q = h_q
        self.h_kv = h_kv
        self.d_head = d_head
        self.d_ff = d_ff
        self.n_layers = n_layers
        self.vocab = vocab
        self.max_ctx = max_ctx
        self.eps = Float32(eps)
        self.scale = Float32(scale)

        var n_qkv = (h_q + 2 * h_kv) * d_head
        var n_pairs = d_head // 2

        self.layers = List[_LayerGpuF16]()
        for _ in range(n_layers):
            self.layers.append(
                _LayerGpuF16(
                    self.ctx.enqueue_create_buffer[DType.float32](d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](d_head),
                    self.ctx.enqueue_create_buffer[DType.float32](d_head),
                    self.ctx.enqueue_create_buffer[DType.float16](n_qkv * d_model),
                    self.ctx.enqueue_create_buffer[DType.float16](d_model * h_q * d_head),
                    self.ctx.enqueue_create_buffer[DType.float16](2 * d_ff * d_model),
                    self.ctx.enqueue_create_buffer[DType.float16](d_model * d_ff),
                    self.ctx.enqueue_create_buffer[DType.float32](max_ctx * h_kv * d_head),
                    self.ctx.enqueue_create_buffer[DType.float32](max_ctx * h_kv * d_head),
                )
            )

        self.embed = self.ctx.enqueue_create_buffer[DType.float16](vocab * d_model)
        self.final_norm = self.ctx.enqueue_create_buffer[DType.float32](d_model)
        self.cos_t = self.ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)
        self.sin_t = self.ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)

        self.hidden = self.ctx.enqueue_create_buffer[DType.float32](d_model)
        self.qkv = self.ctx.enqueue_create_buffer[DType.float32](n_qkv)
        self.q_rot = self.ctx.enqueue_create_buffer[DType.float32](h_q * d_head)
        self.attn_out = self.ctx.enqueue_create_buffer[DType.float32](h_q * d_head)
        self.act = self.ctx.enqueue_create_buffer[DType.float32](d_ff)
        self.blk_val = self.ctx.enqueue_create_buffer[DType.float32](_LM_BLOCKS)
        self.blk_idx = self.ctx.enqueue_create_buffer[DType.int32](_LM_BLOCKS)
        self.out_val = self.ctx.enqueue_create_buffer[DType.float32](1)
        self.out_idx = self.ctx.enqueue_create_buffer[DType.int32](1)
        self.host_val = self.ctx.enqueue_create_host_buffer[DType.float32](1)
        self.host_idx = self.ctx.enqueue_create_host_buffer[DType.int32](1)

        self.f_embed = self.ctx.compile_function_unchecked[_embed_row_kernel_f16]()
        self.f_norm_gemv = self.ctx.compile_function_unchecked[_norm_gemv_kernel_f16]()
        self.f_gemv_acc = self.ctx.compile_function_unchecked[_gemv_accum_kernel_f16]()
        self.f_gu = self.ctx.compile_function_unchecked[_norm_gemv2_swiglu_kernel_f16]()
        self.f_rope = self.ctx.compile_function_unchecked[_qk_rope_write_kernel]()
        self.f_sdpa = self.ctx.compile_function_unchecked[_sdpa_kernel]()
        self.f_lm = self.ctx.compile_function_unchecked[_lmhead_argmax_kernel_f16]()
        self.f_argmax = self.ctx.compile_function_unchecked[_argmax_reduce_kernel]()

    fn device_name(self) raises -> String:
        return self.ctx.name()

    fn dispatch_budget(self) -> Int:
        return residentk_dispatch_budget(self.n_layers)

    fn upload_globals(
        mut self, embed: List[Float64], final_norm: List[Float64],
        cos_t: List[Float64], sin_t: List[Float64], n_pos: Int,
    ) raises -> Int:
        """The tied embedding/lm_head table (narrowed to Float16), the final norm gain (Float32),
        and the RoPE tables (Float32). See `_ResidentQwen3.upload_globals` for why the embedding
        table is not transposed."""
        var n_pairs = self.d_head // 2
        if n_pos > self.max_ctx:
            return RESIDENT_ERR_CONTEXT_FULL
        var s = _narrow_into_f16(self.embed, embed, self.vocab * self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(self.final_norm, final_norm, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        if len(cos_t) < n_pos * n_pairs or len(sin_t) < n_pos * n_pairs:
            return RESIDENT_ERR_UPLOAD_LENGTH
        with self.cos_t.map_to_host() as h:
            for i in range(n_pos * n_pairs):
                h[i] = Float32(cos_t[i])
        with self.sin_t.map_to_host() as h:
            for i in range(n_pos * n_pairs):
                h[i] = Float32(sin_t[i])
        return RESIDENT_OK

    fn upload_layer(
        mut self, layer: Int,
        ln1: List[Float64], ln2: List[Float64], qn: List[Float64], kn: List[Float64],
        wq: List[Float64], wk: List[Float64], wv: List[Float64], wo: List[Float64],
        wgate: List[Float64], wup: List[Float64], wdown: List[Float64],
    ) raises -> Int:
        """One layer's eleven checkpoint tensors: norm gains narrowed to Float32 exactly as
        `_ResidentQwen3.upload_layer` does, the four GEMV weight matrices narrowed (and
        transposed) to Float16 instead."""
        if layer < 0 or layer >= self.n_layers:
            return RESIDENT_ERR_UPLOAD_LENGTH
        ref lw = self.layers[layer]
        var s = _narrow_into(lw.ln1, ln1, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(lw.ln2, ln2, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(lw.qn, qn, self.d_head, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(lw.kn, kn, self.d_head, 0)
        if s != RESIDENT_OK:
            return s

        var n_q = self.h_q * self.d_head
        var n_kv = self.h_kv * self.d_head
        s = _narrow_transposed_into_f16(lw.w_qkv, wq, self.d_model, n_q, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into_f16(lw.w_qkv, wk, self.d_model, n_kv, n_q)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into_f16(lw.w_qkv, wv, self.d_model, n_kv, n_q + n_kv)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into_f16(lw.w_o, wo, n_q, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into_f16(lw.w_gu, wgate, self.d_model, self.d_ff, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into_f16(lw.w_gu, wup, self.d_model, self.d_ff, self.d_ff)
        if s != RESIDENT_OK:
            return s
        s = _narrow_transposed_into_f16(lw.w_down, wdown, self.d_ff, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        return RESIDENT_OK

    fn seal(mut self) raises -> Int:
        """Drain every upload before the first step. One synchronize for the whole load."""
        self.ctx.synchronize()
        return RESIDENT_OK

    fn step(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """ONE token, identical dispatch plan to `_ResidentQwen3.step` — same six-per-layer, same
        fixed three, same budget. See that function's docstring; nothing about the SHAPE of the
        computation differs here, only which buffers a handful of the dispatches read from.
        """

        @parameter
        if not RESIDENT_GPU_BUILD:
            return _StepOut(-1, 0.0, 0, RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            if pos < 0 or pos >= self.max_ctx:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_CONTEXT_FULL)
            if token_id < 0 or token_id >= self.vocab:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_UPLOAD_LENGTH)

            var n_q = self.h_q * self.d_head
            var n_kv = self.h_kv * self.d_head
            var n_qkv = n_q + 2 * n_kv
            var n_keys = pos + 1
            var issued = 0

            self.ctx.enqueue_function_unchecked(
                self.f_embed,
                self.hidden.unsafe_ptr(), self.embed.unsafe_ptr(), token_id, self.d_model,
                grid_dim=_ceil_div(self.d_model, _TG), block_dim=_TG,
            )
            issued += 1

            for layer in range(self.n_layers):
                ref lw = self.layers[layer]

                self.ctx.enqueue_function_unchecked(
                    self.f_norm_gemv,
                    self.qkv.unsafe_ptr(), self.hidden.unsafe_ptr(), lw.ln1.unsafe_ptr(),
                    lw.w_qkv.unsafe_ptr(), self.d_model, n_qkv, self.eps,
                    grid_dim=_ceil_div(n_qkv, _SUBS), block_dim=_TG,
                )
                self.ctx.enqueue_function_unchecked(
                    self.f_rope,
                    self.q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                    self.qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                    self.cos_t.unsafe_ptr(), self.sin_t.unsafe_ptr(),
                    pos, self.h_q, self.h_kv, self.d_head, self.eps,
                    grid_dim=self.h_q + self.h_kv, block_dim=self.d_head,
                )
                self.ctx.enqueue_function_unchecked(
                    self.f_sdpa,
                    self.attn_out.unsafe_ptr(), self.q_rot.unsafe_ptr(),
                    lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                    n_keys, self.h_q, self.h_kv, self.d_head, self.scale,
                    grid_dim=self.h_q, block_dim=self.d_head,
                )
                self.ctx.enqueue_function_unchecked(
                    self.f_gemv_acc,
                    self.hidden.unsafe_ptr(), self.attn_out.unsafe_ptr(), lw.w_o.unsafe_ptr(),
                    n_q, self.d_model,
                    grid_dim=_ceil_div(self.d_model, _SUBS), block_dim=_TG,
                )
                self.ctx.enqueue_function_unchecked(
                    self.f_gu,
                    self.act.unsafe_ptr(), self.hidden.unsafe_ptr(), lw.ln2.unsafe_ptr(),
                    lw.w_gu.unsafe_ptr(), self.d_model, self.d_ff, self.eps,
                    grid_dim=_ceil_div(self.d_ff, _SUBS), block_dim=_TG,
                )
                self.ctx.enqueue_function_unchecked(
                    self.f_gemv_acc,
                    self.hidden.unsafe_ptr(), self.act.unsafe_ptr(), lw.w_down.unsafe_ptr(),
                    self.d_ff, self.d_model,
                    grid_dim=_ceil_div(self.d_model, _SUBS), block_dim=_TG,
                )
                issued += 6

            var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
            self.ctx.enqueue_function_unchecked(
                self.f_lm,
                self.blk_val.unsafe_ptr(), self.blk_idx.unsafe_ptr(), self.hidden.unsafe_ptr(),
                self.final_norm.unsafe_ptr(), self.embed.unsafe_ptr(),
                self.d_model, self.vocab, self.eps, n_iters,
                grid_dim=_LM_BLOCKS, block_dim=_TG,
            )
            self.ctx.enqueue_function_unchecked(
                self.f_argmax,
                self.out_val.unsafe_ptr(), self.out_idx.unsafe_ptr(),
                self.blk_val.unsafe_ptr(), self.blk_idx.unsafe_ptr(), _LM_BLOCKS,
                grid_dim=1, block_dim=_TG,
            )
            issued += 2

            self.ctx.enqueue_copy(self.host_val, self.out_val)
            self.ctx.enqueue_copy(self.host_idx, self.out_idx)
            self.ctx.synchronize()
            var tok = Int(self.host_idx.unsafe_ptr()[0])
            var lg = Float64(self.host_val.unsafe_ptr()[0])
            if tok < 0 or tok >= self.vocab:
                return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
            return _StepOut(tok, lg, issued, RESIDENT_OK)


struct _ResidentQwen3I8(Movable):
    """The int8-weight twin of `_ResidentQwen3`/`_ResidentQwen3F16`: identical session, identical
    dispatch plan, identical `step()` contract — the four GEMV weight matrices per layer and the
    tied embed/lm_head table are resident as Int8, each with a companion per-output-row Float32
    scale buffer, read through the `_i8` kernel twins (see `residentk.kernels._I8P`'s docstring for
    the quantization scheme and the in-register dequant this session's kernels perform).

    Additive alongside both existing arms, per the task this struct was built for: `_ResidentQwen3`
    and `_ResidentQwen3F16` above are untouched. Every field that is NOT a weight matrix or its
    scale keeps the Float32 type the other two arms use: activations, the KV cache, norm gains, the
    RoPE tables, and the argmax scratch. Mixed precision (Float32 activations/accumulator, Int8
    storage with a Float32 scale), not an all-int8 session.
    """

    var ctx: DeviceContext
    var d_model: Int
    var h_q: Int
    var h_kv: Int
    var d_head: Int
    var d_ff: Int
    var n_layers: Int
    var vocab: Int
    var max_ctx: Int
    var eps: Float32
    var scale: Float32

    var layers: List[_LayerGpuI8]
    var embed: DeviceBuffer[DType.int8]
    var embed_scale: DeviceBuffer[DType.float32]
    var final_norm: DeviceBuffer[DType.float32]
    var cos_t: DeviceBuffer[DType.float32]
    var sin_t: DeviceBuffer[DType.float32]

    var hidden: DeviceBuffer[DType.float32]
    var qkv: DeviceBuffer[DType.float32]
    var q_rot: DeviceBuffer[DType.float32]
    var attn_out: DeviceBuffer[DType.float32]
    var act: DeviceBuffer[DType.float32]
    var blk_val: DeviceBuffer[DType.float32]
    var blk_idx: DeviceBuffer[DType.int32]
    var out_val: DeviceBuffer[DType.float32]
    var out_idx: DeviceBuffer[DType.int32]
    var host_val: HostBuffer[DType.float32]
    var host_idx: HostBuffer[DType.int32]

    var f_embed: DeviceFunction[
        _embed_row_kernel_i8, None, target = DeviceContext.default_device_info.target()
    ]
    var f_norm_gemv: DeviceFunction[
        _norm_gemv_kernel_i8, None, target = DeviceContext.default_device_info.target()
    ]
    var f_gemv_acc: DeviceFunction[
        _gemv_accum_kernel_i8, None, target = DeviceContext.default_device_info.target()
    ]
    var f_gu: DeviceFunction[
        _norm_gemv2_swiglu_kernel_i8, None, target = DeviceContext.default_device_info.target()
    ]
    var f_rope: DeviceFunction[
        _qk_rope_write_kernel, None, target = DeviceContext.default_device_info.target()
    ]
    var f_sdpa: DeviceFunction[
        _sdpa_kernel, None, target = DeviceContext.default_device_info.target()
    ]
    var f_lm: DeviceFunction[
        _lmhead_argmax_kernel_i8, None, target = DeviceContext.default_device_info.target()
    ]
    var f_argmax: DeviceFunction[
        _argmax_reduce_kernel, None, target = DeviceContext.default_device_info.target()
    ]

    fn __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
    ) raises:
        """Open the context, compile every kernel, and allocate every resident buffer. ONCE.

        Same call-site discipline as `_ResidentQwen3.__init__` and `_ResidentQwen3F16.__init__` —
        see that constructor's docstring and the module docstring for why the compile-time gate
        cannot sit on a constructor.
        """
        self.ctx = DeviceContext()
        self.d_model = d_model
        self.h_q = h_q
        self.h_kv = h_kv
        self.d_head = d_head
        self.d_ff = d_ff
        self.n_layers = n_layers
        self.vocab = vocab
        self.max_ctx = max_ctx
        self.eps = Float32(eps)
        self.scale = Float32(scale)

        var n_qkv = (h_q + 2 * h_kv) * d_head
        var n_pairs = d_head // 2

        self.layers = List[_LayerGpuI8]()
        for _ in range(n_layers):
            self.layers.append(
                _LayerGpuI8(
                    self.ctx.enqueue_create_buffer[DType.float32](d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](d_head),
                    self.ctx.enqueue_create_buffer[DType.float32](d_head),
                    self.ctx.enqueue_create_buffer[DType.int8](n_qkv * d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](n_qkv),
                    self.ctx.enqueue_create_buffer[DType.int8](d_model * h_q * d_head),
                    self.ctx.enqueue_create_buffer[DType.float32](d_model),
                    self.ctx.enqueue_create_buffer[DType.int8](2 * d_ff * d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](2 * d_ff),
                    self.ctx.enqueue_create_buffer[DType.int8](d_model * d_ff),
                    self.ctx.enqueue_create_buffer[DType.float32](d_model),
                    self.ctx.enqueue_create_buffer[DType.float32](max_ctx * h_kv * d_head),
                    self.ctx.enqueue_create_buffer[DType.float32](max_ctx * h_kv * d_head),
                )
            )

        self.embed = self.ctx.enqueue_create_buffer[DType.int8](vocab * d_model)
        self.embed_scale = self.ctx.enqueue_create_buffer[DType.float32](vocab)
        self.final_norm = self.ctx.enqueue_create_buffer[DType.float32](d_model)
        self.cos_t = self.ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)
        self.sin_t = self.ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)

        self.hidden = self.ctx.enqueue_create_buffer[DType.float32](d_model)
        self.qkv = self.ctx.enqueue_create_buffer[DType.float32](n_qkv)
        self.q_rot = self.ctx.enqueue_create_buffer[DType.float32](h_q * d_head)
        self.attn_out = self.ctx.enqueue_create_buffer[DType.float32](h_q * d_head)
        self.act = self.ctx.enqueue_create_buffer[DType.float32](d_ff)
        self.blk_val = self.ctx.enqueue_create_buffer[DType.float32](_LM_BLOCKS)
        self.blk_idx = self.ctx.enqueue_create_buffer[DType.int32](_LM_BLOCKS)
        self.out_val = self.ctx.enqueue_create_buffer[DType.float32](1)
        self.out_idx = self.ctx.enqueue_create_buffer[DType.int32](1)
        self.host_val = self.ctx.enqueue_create_host_buffer[DType.float32](1)
        self.host_idx = self.ctx.enqueue_create_host_buffer[DType.int32](1)

        self.f_embed = self.ctx.compile_function_unchecked[_embed_row_kernel_i8]()
        self.f_norm_gemv = self.ctx.compile_function_unchecked[_norm_gemv_kernel_i8]()
        self.f_gemv_acc = self.ctx.compile_function_unchecked[_gemv_accum_kernel_i8]()
        self.f_gu = self.ctx.compile_function_unchecked[_norm_gemv2_swiglu_kernel_i8]()
        self.f_rope = self.ctx.compile_function_unchecked[_qk_rope_write_kernel]()
        self.f_sdpa = self.ctx.compile_function_unchecked[_sdpa_kernel]()
        self.f_lm = self.ctx.compile_function_unchecked[_lmhead_argmax_kernel_i8]()
        self.f_argmax = self.ctx.compile_function_unchecked[_argmax_reduce_kernel]()

    fn device_name(self) raises -> String:
        return self.ctx.name()

    fn dispatch_budget(self) -> Int:
        return residentk_dispatch_budget(self.n_layers)

    fn upload_globals(
        mut self, embed: List[Float64], final_norm: List[Float64],
        cos_t: List[Float64], sin_t: List[Float64], n_pos: Int,
    ) raises -> Int:
        """The tied embedding/lm_head table (per-row int8-quantized), the final norm gain
        (Float32), and the RoPE tables (Float32). See `_ResidentQwen3.upload_globals` for why the
        embedding table is not transposed."""
        var n_pairs = self.d_head // 2
        if n_pos > self.max_ctx:
            return RESIDENT_ERR_CONTEXT_FULL
        var s = _quantize_into_i8(self.embed, self.embed_scale, embed, self.vocab, self.d_model, 0, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(self.final_norm, final_norm, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        if len(cos_t) < n_pos * n_pairs or len(sin_t) < n_pos * n_pairs:
            return RESIDENT_ERR_UPLOAD_LENGTH
        with self.cos_t.map_to_host() as h:
            for i in range(n_pos * n_pairs):
                h[i] = Float32(cos_t[i])
        with self.sin_t.map_to_host() as h:
            for i in range(n_pos * n_pairs):
                h[i] = Float32(sin_t[i])
        return RESIDENT_OK

    fn upload_layer(
        mut self, layer: Int,
        ln1: List[Float64], ln2: List[Float64], qn: List[Float64], kn: List[Float64],
        wq: List[Float64], wk: List[Float64], wv: List[Float64], wo: List[Float64],
        wgate: List[Float64], wup: List[Float64], wdown: List[Float64],
    ) raises -> Int:
        """One layer's eleven checkpoint tensors: norm gains narrowed to Float32 exactly as
        `_ResidentQwen3.upload_layer` does, the four GEMV weight matrices narrowed, transposed,
        AND per-row int8-quantized instead."""
        if layer < 0 or layer >= self.n_layers:
            return RESIDENT_ERR_UPLOAD_LENGTH
        ref lw = self.layers[layer]
        var s = _narrow_into(lw.ln1, ln1, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(lw.ln2, ln2, self.d_model, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(lw.qn, qn, self.d_head, 0)
        if s != RESIDENT_OK:
            return s
        s = _narrow_into(lw.kn, kn, self.d_head, 0)
        if s != RESIDENT_OK:
            return s

        var n_q = self.h_q * self.d_head
        var n_kv = self.h_kv * self.d_head
        s = _quantize_transposed_into_i8(lw.w_qkv, lw.w_qkv_scale, wq, self.d_model, n_q, 0, 0)
        if s != RESIDENT_OK:
            return s
        s = _quantize_transposed_into_i8(lw.w_qkv, lw.w_qkv_scale, wk, self.d_model, n_kv, n_q, n_q)
        if s != RESIDENT_OK:
            return s
        s = _quantize_transposed_into_i8(
            lw.w_qkv, lw.w_qkv_scale, wv, self.d_model, n_kv, n_q + n_kv, n_q + n_kv
        )
        if s != RESIDENT_OK:
            return s
        s = _quantize_transposed_into_i8(lw.w_o, lw.w_o_scale, wo, n_q, self.d_model, 0, 0)
        if s != RESIDENT_OK:
            return s
        s = _quantize_transposed_into_i8(lw.w_gu, lw.w_gu_scale, wgate, self.d_model, self.d_ff, 0, 0)
        if s != RESIDENT_OK:
            return s
        s = _quantize_transposed_into_i8(
            lw.w_gu, lw.w_gu_scale, wup, self.d_model, self.d_ff, self.d_ff, self.d_ff
        )
        if s != RESIDENT_OK:
            return s
        s = _quantize_transposed_into_i8(lw.w_down, lw.w_down_scale, wdown, self.d_ff, self.d_model, 0, 0)
        if s != RESIDENT_OK:
            return s
        return RESIDENT_OK

    fn seal(mut self) raises -> Int:
        """Drain every upload before the first step. One synchronize for the whole load."""
        self.ctx.synchronize()
        return RESIDENT_OK

    fn step(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """ONE token, identical dispatch plan to `_ResidentQwen3.step`/`_ResidentQwen3F16.step` —
        same six-per-layer, same fixed three, same budget. See that function's docstring; nothing
        about the SHAPE of the computation differs here, only which buffers a handful of the
        dispatches read from, and that the weight-matrix dispatches now pass an extra scale-buffer
        argument.
        """

        @parameter
        if not RESIDENT_GPU_BUILD:
            return _StepOut(-1, 0.0, 0, RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            if pos < 0 or pos >= self.max_ctx:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_CONTEXT_FULL)
            if token_id < 0 or token_id >= self.vocab:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_UPLOAD_LENGTH)

            var n_q = self.h_q * self.d_head
            var n_kv = self.h_kv * self.d_head
            var n_qkv = n_q + 2 * n_kv
            var n_keys = pos + 1
            var issued = 0

            self.ctx.enqueue_function_unchecked(
                self.f_embed,
                self.hidden.unsafe_ptr(), self.embed.unsafe_ptr(), self.embed_scale.unsafe_ptr(),
                token_id, self.d_model,
                grid_dim=_ceil_div(self.d_model, _TG), block_dim=_TG,
            )
            issued += 1

            for layer in range(self.n_layers):
                ref lw = self.layers[layer]

                self.ctx.enqueue_function_unchecked(
                    self.f_norm_gemv,
                    self.qkv.unsafe_ptr(), self.hidden.unsafe_ptr(), lw.ln1.unsafe_ptr(),
                    lw.w_qkv.unsafe_ptr(), lw.w_qkv_scale.unsafe_ptr(),
                    self.d_model, n_qkv, self.eps,
                    grid_dim=_ceil_div(n_qkv, _SUBS), block_dim=_TG,
                )
                self.ctx.enqueue_function_unchecked(
                    self.f_rope,
                    self.q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                    self.qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                    self.cos_t.unsafe_ptr(), self.sin_t.unsafe_ptr(),
                    pos, self.h_q, self.h_kv, self.d_head, self.eps,
                    grid_dim=self.h_q + self.h_kv, block_dim=self.d_head,
                )
                self.ctx.enqueue_function_unchecked(
                    self.f_sdpa,
                    self.attn_out.unsafe_ptr(), self.q_rot.unsafe_ptr(),
                    lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                    n_keys, self.h_q, self.h_kv, self.d_head, self.scale,
                    grid_dim=self.h_q, block_dim=self.d_head,
                )
                self.ctx.enqueue_function_unchecked(
                    self.f_gemv_acc,
                    self.hidden.unsafe_ptr(), self.attn_out.unsafe_ptr(),
                    lw.w_o.unsafe_ptr(), lw.w_o_scale.unsafe_ptr(),
                    n_q, self.d_model,
                    grid_dim=_ceil_div(self.d_model, _SUBS), block_dim=_TG,
                )
                self.ctx.enqueue_function_unchecked(
                    self.f_gu,
                    self.act.unsafe_ptr(), self.hidden.unsafe_ptr(), lw.ln2.unsafe_ptr(),
                    lw.w_gu.unsafe_ptr(), lw.w_gu_scale.unsafe_ptr(),
                    self.d_model, self.d_ff, self.eps,
                    grid_dim=_ceil_div(self.d_ff, _SUBS), block_dim=_TG,
                )
                self.ctx.enqueue_function_unchecked(
                    self.f_gemv_acc,
                    self.hidden.unsafe_ptr(), self.act.unsafe_ptr(),
                    lw.w_down.unsafe_ptr(), lw.w_down_scale.unsafe_ptr(),
                    self.d_ff, self.d_model,
                    grid_dim=_ceil_div(self.d_model, _SUBS), block_dim=_TG,
                )
                issued += 6

            var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
            self.ctx.enqueue_function_unchecked(
                self.f_lm,
                self.blk_val.unsafe_ptr(), self.blk_idx.unsafe_ptr(), self.hidden.unsafe_ptr(),
                self.final_norm.unsafe_ptr(), self.embed.unsafe_ptr(), self.embed_scale.unsafe_ptr(),
                self.d_model, self.vocab, self.eps, n_iters,
                grid_dim=_LM_BLOCKS, block_dim=_TG,
            )
            self.ctx.enqueue_function_unchecked(
                self.f_argmax,
                self.out_val.unsafe_ptr(), self.out_idx.unsafe_ptr(),
                self.blk_val.unsafe_ptr(), self.blk_idx.unsafe_ptr(), _LM_BLOCKS,
                grid_dim=1, block_dim=_TG,
            )
            issued += 2

            self.ctx.enqueue_copy(self.host_val, self.out_val)
            self.ctx.enqueue_copy(self.host_idx, self.out_idx)
            self.ctx.synchronize()
            var tok = Int(self.host_idx.unsafe_ptr()[0])
            var lg = Float64(self.host_val.unsafe_ptr()[0])
            if tok < 0 or tok >= self.vocab:
                return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
            return _StepOut(tok, lg, issued, RESIDENT_OK)


fn _resident_preflight(
    d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
    n_layers: Int, n_prompt: Int, n_new: Int, max_ctx: Int, eps: Float64, scale: Float64,
) -> Int:
    """Every refusal a caller can hit, answered on the HOST before a device is touched.

    Separate from `_ResidentQwen3.__init__` on purpose: the constructor allocates 2.4 GB, and the
    honest time to say "this shape does not fit" or "this binary has no kernels" is before that,
    not after. Order matters — a shape refusal is true on every host and is reported first, so a
    reader is not sent hunting for hardware that could not have helped.
    """
    var shape = residentk_dims_check(d_model, h_q, h_kv, d_head, d_ff)
    if shape != RESIDENT_OK:
        return shape
    if n_layers < 1:
        return RESIDENT_ERR_UPLOAD_LENGTH
    var ctxs = residentk_context_check(n_prompt, n_new, max_ctx)
    if ctxs != RESIDENT_OK:
        return ctxs
    if max_ctx > RESIDENT_MAX_CONTEXT:
        return RESIDENT_ERR_CONTEXT_FULL
    if eps <= 0.0 or scale <= 0.0:
        return RESIDENT_ERR_UPLOAD_LENGTH

    @parameter
    if not RESIDENT_GPU_BUILD:
        return RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT
    if not has_accelerator():
        return RESIDENT_ERR_NO_DEVICE
    return RESIDENT_OK
