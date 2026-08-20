"""residentk_cuda_smoke.mojo — Phase 0 of the CUDA-native session: the FIRST residentk kernels on
real NVIDIA hardware, through the portable max.gpu.host API. No Metal shim, no metallib — the same
fused decode kernels `residentk.session` dispatches, cross-compiled for an sm_75 target and
launched via `DeviceContext.enqueue_function[kernel](...)`.

What is validated, and how
--------------------------
Two kernels round-trip with real device buffers at Qwen3-0.6B's own decode shapes:

  * `_norm_gemv_kernel`, the fused input-rmsnorm + QKV projection, at the model's real QKV shape
    (`k = d_model = 1024`, `n = (h_q + 2*h_kv) * d_head = 3072`) — this kernel exercises shared
    staging, two tree reductions, barriers and the 4-wide vectorized loads, i.e. every portable
    construct the CUDA backend has not run before;
  * `_gemv_accum_kernel`, the fused o_proj/down_proj + residual accumulate, at the down_proj shape
    (`k = d_ff = 3072`, `n = d_model = 1024`).

Numerics are judged the same way `accel.gemm_metal.gemm_metal_agreement` judges the Metal GEMM: a
Float64 oracle computed from the SAME Float32-narrowed inputs the kernel consumed, with the bound
`f32_eps * k * (1 + |oracle|)` per output element.

Build (the CUDA lane recipe, no CUDA toolkit needed on the build host):

    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_75 \
        -I mojo/engine benchmarks/llm_smoke/residentk_cuda_smoke.mojo --emit object -o smoke.o
    clang smoke.o -o smoke -L <max-lib> -Wl,-rpath,<max-lib> \
        -lKGENCompilerRTShared -lAsyncRTRuntimeGlobals -lMSupportGlobals -lAsyncRTMojoBindings \
        -lMGPRT libpython3.14.so -lstdc++ -ldl -lpthread -lm
"""

from std.origin import MutAnyOrigin
from max.gpu.host import DeviceContext
from std.sys import exit, has_accelerator, is_defined
from std.math import sqrt
from residentk.kernels import _TG, _SUBS, _norm_gemv_kernel, _gemv_accum_kernel

comptime GPU_BUILD: Bool = is_defined["ALGENTA_GPU"]()
comptime CUDA_BUILD: Bool = is_defined["ALGENTA_CUDA"]()
"""The two-tier gate the CUDA lane in scripts/build_mojo_binary.sh forms: ALGENTA_GPU compiles the
portable kernels in, ALGENTA_CUDA selects the CUDA backend answer, and the ABSENCE of
ALGENTA_METAL keeps the Metal batched-dispatch shim machinery compiled out."""


def _lcg(seed: Int) -> Float64:
    """Deterministic pseudo-random in [0, 1) — reproducible oracles on any host (the same
    generator cuda_lane_test used for the first CUDA lane proof)."""
    var s = (seed * 6364136223846793005 + 1442695040888963407) & 0x7FFFFFFFFFFFFFFF
    return Float64(s % 1000003) / 1000003.0


def _gains(n: Int, seed: Int) -> List[Float64]:
    """rmsnorm gains in [0.5, 1.5) — positive, like a real checkpoint's gamma."""
    var g = List[Float64](capacity=n)
    for i in range(n):
        g.append(0.5 + _lcg(seed + i))
    return g^


def run_norm_gemv(ctx: DeviceContext) raises -> Bool:
    """`y = W @ (rmsnorm(x) * gamma)` at the Qwen3-0.6B fused-QKV shape.

    k = d_model = 1024, n = n_qkv = (16 + 2*8) * 128 = 3072. Weight held `[n, k]` row-major — the
    resident layout (checkpoint `[in, out]` transposed once at upload; the smoke feeds the already-
    transposed layout directly). eps = 1e-6, the model's own rms_norm_eps.
    """
    var k = 1024
    var n = 3072
    var eps = Float32(1e-6)

    var x = List[Float64](capacity=k)
    for i in range(k):
        x.append(_lcg(i + 11))
    var gamma = _gains(k, 5011)
    var w = List[Float64](capacity=n * k)
    for i in range(n * k):
        w.append((_lcg(i + 7919) - 0.5) * 0.1)

    var x_buf = ctx.enqueue_create_buffer[DType.float32](k)
    var g_buf = ctx.enqueue_create_buffer[DType.float32](k)
    var w_buf = ctx.enqueue_create_buffer[DType.float32](n * k)
    var y_buf = ctx.enqueue_create_buffer[DType.float32](n)

    # Narrow host-side exactly as residentk.session's upload does.
    var xp = x.unsafe_ptr()
    var gp = gamma.unsafe_ptr()
    var wp = w.unsafe_ptr()
    with x_buf.map_to_host() as h:
        for i in range(k):
            h[i] = Float32(xp[i])
    with g_buf.map_to_host() as h:
        for i in range(k):
            h[i] = Float32(gp[i])
    with w_buf.map_to_host() as h:
        for i in range(n * k):
            h[i] = Float32(wp[i])

    ctx.enqueue_function[_norm_gemv_kernel](
        y_buf.unsafe_ptr(), x_buf.unsafe_ptr(), g_buf.unsafe_ptr(), w_buf.unsafe_ptr(),
        Int64(k), Int64(n), eps,
        grid_dim=(n + _SUBS - 1) // _SUBS, block_dim=_TG,
    )
    ctx.synchronize()

    # Oracle in Float64 from the SAME Float32-narrowed inputs the kernel consumed.
    var f32_eps = 1.1920929e-7
    var worst = 0.0
    var bound_at_worst = 0.0
    var bad_count = 0
    with y_buf.map_to_host() as h:
        # rmsnorm of the narrowed x, in Float64.
        var ss = 0.0
        for i in range(k):
            var v = Float64(Float32(xp[i]))
            ss += v * v
        var inv = 1.0 / sqrt(ss / Float64(k) + Float64(eps))
        for j in range(n):
            var oracle = 0.0
            for i in range(k):
                var xn = Float64(Float32(xp[i])) * inv * Float64(Float32(gp[i]))
                oracle += xn * Float64(Float32(wp[j * k + i]))
            var gpu_val = Float64(h[j])
            var delta = gpu_val - oracle
            if delta < 0.0:
                delta = -delta
            var mag = oracle if oracle >= 0.0 else -oracle
            var bound = f32_eps * Float64(k) * (1.0 + mag)
            if delta > bound:
                bad_count += 1
            if delta > worst:
                worst = delta
                bound_at_worst = bound

    print(
        "  norm_gemv",
        k, "x", n,
        ": worst_abs_delta =", worst,
        "bound =", bound_at_worst,
        "elements_over_bound =", bad_count,
    )
    return bad_count == 0


def run_gemv_accum(ctx: DeviceContext) raises -> Bool:
    """`y += W @ x` at the down_proj shape: k = d_ff = 3072, n = d_model = 1024.

    `y` starts at a known nonzero value so the ACCUMULATE (not assign) is what is checked.
    """
    var k = 3072
    var n = 1024

    var x = List[Float64](capacity=k)
    for i in range(k):
        x.append((_lcg(i + 101) - 0.5) * 2.0)
    var y0 = List[Float64](capacity=n)
    for i in range(n):
        y0.append((_lcg(i + 202) - 0.5) * 4.0)
    var w = List[Float64](capacity=n * k)
    for i in range(n * k):
        w.append((_lcg(i + 30303) - 0.5) * 0.1)

    var x_buf = ctx.enqueue_create_buffer[DType.float32](k)
    var w_buf = ctx.enqueue_create_buffer[DType.float32](n * k)
    var y_buf = ctx.enqueue_create_buffer[DType.float32](n)

    var xp = x.unsafe_ptr()
    var y0p = y0.unsafe_ptr()
    var wp = w.unsafe_ptr()
    with x_buf.map_to_host() as h:
        for i in range(k):
            h[i] = Float32(xp[i])
    with y_buf.map_to_host() as h:
        for i in range(n):
            h[i] = Float32(y0p[i])
    with w_buf.map_to_host() as h:
        for i in range(n * k):
            h[i] = Float32(wp[i])

    ctx.enqueue_function[_gemv_accum_kernel](
        y_buf.unsafe_ptr(), x_buf.unsafe_ptr(), w_buf.unsafe_ptr(),
        Int64(k), Int64(n),
        grid_dim=(n + _SUBS - 1) // _SUBS, block_dim=_TG,
    )
    ctx.synchronize()

    var f32_eps = 1.1920929e-7
    var worst = 0.0
    var bound_at_worst = 0.0
    var bad_count = 0
    with y_buf.map_to_host() as h:
        for j in range(n):
            var oracle = Float64(Float32(y0p[j]))
            for i in range(k):
                oracle += Float64(Float32(wp[j * k + i])) * Float64(Float32(xp[i]))
            var gpu_val = Float64(h[j])
            var delta = gpu_val - oracle
            if delta < 0.0:
                delta = -delta
            var mag = oracle if oracle >= 0.0 else -oracle
            var bound = f32_eps * Float64(k) * (1.0 + mag)
            if delta > bound:
                bad_count += 1
            if delta > worst:
                worst = delta
                bound_at_worst = bound

    print(
        "  gemv_accum",
        k, "x", n,
        ": worst_abs_delta =", worst,
        "bound =", bound_at_worst,
        "elements_over_bound =", bad_count,
    )
    return bad_count == 0


def main():
    print("=== residentk CUDA smoke — first portable resident kernels on NVIDIA ===")
    print("build gate: ALGENTA_GPU =", GPU_BUILD, "| ALGENTA_CUDA =", CUDA_BUILD)

    @parameter
    if not (GPU_BUILD and CUDA_BUILD):
        print("FAIL: built without -D ALGENTA_GPU -D ALGENTA_CUDA")
        exit(1)

    if not has_accelerator():
        print("FAIL: has_accelerator() is false at runtime — no CUDA device visible")
        exit(1)

    try:
        var ctx = DeviceContext()
        print("device:", ctx.name())

        print("[1/2] _norm_gemv_kernel (fused rmsnorm+QKV, 1024 x 3072):")
        var a = run_norm_gemv(ctx)
        print("  norm_gemv:", "PASS" if a else "FAIL")

        print("[2/2] _gemv_accum_kernel (down_proj+residual, 3072 x 1024):")
        var b = run_gemv_accum(ctx)
        print("  gemv_accum:", "PASS" if b else "FAIL")

        if a and b:
            print("RESULT: PASS — residentk kernels correct on NVIDIA hardware")
            exit(0)
        else:
            print("RESULT: FAIL — numeric mismatch")
            exit(1)
    except e:
        print("FAIL: exception during GPU execution:", e)
        exit(1)
