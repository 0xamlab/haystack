"""correctness_probe_all.mojo -- forge-native correctness check for Phase 2's two new kernels,
`_gemm_accum_mma8x8` (o_proj/down_proj) and `_swiglu_gemm_mma8x8`, against independent Float64 CPU
references. `_qkv_proj_gemm_mma8x8` already has its own dedicated probe (`correctness_probe.mojo`)
and its own cross-toolchain check against the real scalar oracle -- not re-tested here.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . probes/correctness_probe_all.mojo
"""
from max.gpu.host import DeviceContext
from mm8 import _gemm_accum_mma8x8, _swiglu_gemm_mma8x8

comptime M: Int = 32
comptime K: Int = 32
comptime N: Int = 32


def _abs32(x: Float32) -> Float32:
    return -x if x < 0.0 else x


def test_gemm_accum(ctx: DeviceContext) raises -> Bool:
    var xn_vals = List[Float32](capacity=M * K)
    for i in range(M * K):
        xn_vals.append(Float32((i * 7 + 3) % 13) / 6.0 - 1.0)
    var w_vals = List[Int8](capacity=N * K)
    for i in range(N * K):
        w_vals.append(Int8((i * 11 + 5) % 17) - 8)
    var wscale_vals = List[Float32](capacity=N)
    for i in range(N):
        wscale_vals.append(Float32(0.01) + Float32(i % 5) * Float32(0.001))
    var y_init_vals = List[Float32](capacity=M * N)
    for i in range(M * N):
        y_init_vals.append(Float32((i * 3 + 1) % 9) / 4.0 - 1.0)

    var xn_buf = ctx.enqueue_create_buffer[DType.float32](M * K)
    var w_buf = ctx.enqueue_create_buffer[DType.int8](N * K)
    var wscale_buf = ctx.enqueue_create_buffer[DType.float32](N)
    var y_buf = ctx.enqueue_create_buffer[DType.float32](M * N)

    with xn_buf.map_to_host() as h:
        for i in range(M * K):
            h[i] = xn_vals[i]
    with w_buf.map_to_host() as h:
        for i in range(N * K):
            h[i] = w_vals[i]
    with wscale_buf.map_to_host() as h:
        for i in range(N):
            h[i] = wscale_vals[i]
    with y_buf.map_to_host() as h:
        for i in range(M * N):
            h[i] = y_init_vals[i]

    ctx.enqueue_function[_gemm_accum_mma8x8](
        y_buf.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
        wscale_buf.unsafe_ptr(), Int64(M), Int64(K), Int64(N),
        grid_dim=1, block_dim=256,
    )
    ctx.synchronize()

    var worst = Float32(0.0)
    with y_buf.map_to_host() as hy:
        for m in range(M):
            for j in range(N):
                var acc = Float64(y_init_vals[m * N + j])
                for kk in range(K):
                    var av = Float64(xn_vals[m * K + kk])
                    var bv = Float64(Float32(w_vals[j * K + kk]) * wscale_vals[j])
                    acc += av * bv
                var got = hy[m * N + j]
                var want = Float32(acc)
                var d = _abs32(got - want)
                if d > worst:
                    worst = d
                if d > 0.01:
                    print("ACCUM MISMATCH at (", m, ",", j, "): got", got, "want", want)
    print("gemm_accum worst delta:", worst)
    return worst <= 0.01


def test_swiglu(ctx: DeviceContext) raises -> Bool:
    comptime n_ff: Int = N
    var xn_vals = List[Float32](capacity=M * K)
    for i in range(M * K):
        xn_vals.append(Float32((i * 7 + 3) % 13) / 6.0 - 1.0)
    var w_vals = List[Int8](capacity=2 * n_ff * K)
    for i in range(2 * n_ff * K):
        w_vals.append(Int8((i * 11 + 5) % 17) - 8)
    var wscale_vals = List[Float32](capacity=2 * n_ff)
    for i in range(2 * n_ff):
        wscale_vals.append(Float32(0.01) + Float32(i % 5) * Float32(0.001))

    var xn_buf = ctx.enqueue_create_buffer[DType.float32](M * K)
    var w_buf = ctx.enqueue_create_buffer[DType.int8](2 * n_ff * K)
    var wscale_buf = ctx.enqueue_create_buffer[DType.float32](2 * n_ff)
    var act_buf = ctx.enqueue_create_buffer[DType.float32](M * n_ff)

    with xn_buf.map_to_host() as h:
        for i in range(M * K):
            h[i] = xn_vals[i]
    with w_buf.map_to_host() as h:
        for i in range(2 * n_ff * K):
            h[i] = w_vals[i]
    with wscale_buf.map_to_host() as h:
        for i in range(2 * n_ff):
            h[i] = wscale_vals[i]

    ctx.enqueue_function[_swiglu_gemm_mma8x8](
        act_buf.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
        wscale_buf.unsafe_ptr(), Int64(M), Int64(K), Int64(n_ff),
        grid_dim=1, block_dim=256,
    )
    ctx.synchronize()

    var worst = Float32(0.0)
    with act_buf.map_to_host() as ha:
        for m in range(M):
            for j in range(n_ff):
                var gacc = Float64(0.0)
                var uacc = Float64(0.0)
                for kk in range(K):
                    var av = Float64(xn_vals[m * K + kk])
                    var gv = Float64(Float32(w_vals[j * K + kk]) * wscale_vals[j])
                    var uv = Float64(Float32(w_vals[(n_ff + j) * K + kk]) * wscale_vals[n_ff + j])
                    gacc += av * gv
                    uacc += av * uv
                var sig = 1.0 / (1.0 + Float64(exp2_approx(-gacc)))
                var want = Float32(gacc * sig * uacc)
                var got = ha[m * n_ff + j]
                var d = _abs32(got - want)
                if d > worst:
                    worst = d
                if d > 0.01:
                    print("SWIGLU MISMATCH at (", m, ",", j, "): got", got, "want", want)
    print("swiglu worst delta:", worst)
    return worst <= 0.01


def exp2_approx(x: Float64) -> Float64:
    from std.math import exp as std_exp
    return Float64(std_exp(Float32(x)))


def main() raises:
    var ctx = DeviceContext()
    var ok1 = test_gemm_accum(ctx)
    var ok2 = test_swiglu(ctx)
    if ok1 and ok2:
        print("ALL PHASE-2 CORRECTNESS PROBES: PASS")
    else:
        print("PHASE-2 CORRECTNESS PROBES: FAIL")
