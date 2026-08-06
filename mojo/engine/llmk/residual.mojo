"""
llmk.residual — elementwise add of two whole flat buffers. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_llmk_residual.mojo
benchmark: benchmarks/llm_smoke/qwen3_forward.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

`transformer_blocks.residual_connection` and `fused_kernels.fused_add_norm` are frozen and both
scalar, one `Float64` at a time. A transformer decoder layer needs `hidden = residual + block_out`
twice per layer (post-attention, post-FFN) over the WHOLE `[tokens, d_model]` buffer; looping the
frozen scalar helper by hand at every call site is exactly the "last line of the kernel, not the
kernel" pattern the rest of this plane's packages already named for attention/norm/FFN, so it gets
one real driver instead.
"""

from std.algorithm import parallelize
from std.sys.info import num_physical_cores
from llmk.contract import LLMK_OK, llmk_residual_dims_check

comptime PARALLEL_MIN_CELLS: Int = 1 << 15
"""Below ~32k cells, run single-threaded. Same threshold and reasoning as `normk`/`mlpk`/`gemm`: a
small add costs less than the fan-out and join."""


@fieldwise_init
struct ResidResult(Copyable, Movable):
    """`a + b`, its length, and a status code."""

    var out: List[Float64]
    var n: Int
    var status: Int


def residual_add_flat(a: List[Float64], b: List[Float64], n: Int) -> ResidResult:
    """`out[i] = a[i] + b[i]` for `i` in `[0, n)`. Exact-length, both operands (rule 1).

    @capability residual_add_flat
    complexity: O(n)
    counts:
    - n == len(a) [enforced]
    - n == len(b) [enforced]
    @endcapability
    """
    var shape = llmk_residual_dims_check(n, len(a), len(b))
    if shape != LLMK_OK:
        return ResidResult(List[Float64](), 0, shape)

    var out = List[Float64](capacity=n)
    for _ in range(n):
        out.append(0.0)

    var ap = a.unsafe_ptr()
    var bp = b.unsafe_ptr()
    var op = out.unsafe_ptr()
    var total = n
    var workers = num_physical_cores()
    if total < PARALLEL_MIN_CELLS or workers > total:
        workers = 1

    @parameter
    def _band(tid: Int) capturing:
        var each = total // workers
        var lo = tid * each
        var hi = lo + each if tid < workers - 1 else total
        for i in range(lo, hi):
            op[i] = ap[i] + bp[i]

    parallelize[_band](workers)

    return ResidResult(out^, n, LLMK_OK)
