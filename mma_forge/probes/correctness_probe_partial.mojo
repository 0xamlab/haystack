"""correctness_probe_partial.mojo -- forge-native correctness check for the partial-tile M/N fix
(see `mm8.mojo`'s own module docstring). Tests all three production kernels
(`_qkv_proj_gemm_mma8x8`, `_gemm_accum_mma8x8`, `_swiglu_gemm_mma8x8`) at a curated set of
DELIBERATELY non-32-aligned `(M,K,N)` shapes -- M smaller than one subtile row, M/N not multiples
of 8, M/N multiples of 8 but not 32, K not a multiple of 16 (exercises the already-correct K
padding alongside the NEW M/N padding in the same dispatch) -- plus one exactly-aligned control
shape to confirm no regression on the case that already worked.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . probes/correctness_probe_partial.mojo
"""
from max.gpu.host import DeviceContext
from mm8 import _qkv_proj_gemm_mma8x8, _gemm_accum_mma8x8, _swiglu_gemm_mma8x8


def _abs32(x: Float32) -> Float32:
    return -x if x < 0.0 else x


def test_assign(ctx: DeviceContext, m: Int, k: Int, n: Int) raises -> Bool:
    var xn_vals = List[Float32](capacity=m * k)
    for i in range(m * k):
        xn_vals.append(Float32((i * 7 + 3) % 13) / 6.0 - 1.0)
    var w_vals = List[Int8](capacity=n * k)
    for i in range(n * k):
        w_vals.append(Int8((i * 11 + 5) % 17) - 8)
    var wscale_vals = List[Float32](capacity=n)
    for i in range(n):
        wscale_vals.append(Float32(0.01) + Float32(i % 5) * Float32(0.001))

    var xn_buf = ctx.enqueue_create_buffer[DType.float32](m * k)
    var w_buf = ctx.enqueue_create_buffer[DType.int8](n * k)
    var wscale_buf = ctx.enqueue_create_buffer[DType.float32](n)
    var y_buf = ctx.enqueue_create_buffer[DType.float32](m * n)
    with xn_buf.map_to_host() as h:
        for i in range(m * k):
            h[i] = xn_vals[i]
    with w_buf.map_to_host() as h:
        for i in range(n * k):
            h[i] = w_vals[i]
    with wscale_buf.map_to_host() as h:
        for i in range(n):
            h[i] = wscale_vals[i]
    with y_buf.map_to_host() as h:
        for i in range(m * n):
            h[i] = Float32(-999.0)  # canary: must be fully overwritten for every valid (r,c)

    var grid = ((m + 31) // 32) * ((n + 31) // 32)
    ctx.enqueue_function[_qkv_proj_gemm_mma8x8](
        y_buf.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
        wscale_buf.unsafe_ptr(), Int64(m), Int64(k), Int64(n),
        grid_dim=grid, block_dim=256,
    )
    ctx.synchronize()

    var worst = Float32(0.0)
    with y_buf.map_to_host() as hy:
        for mi in range(m):
            for j in range(n):
                var acc = Float64(0.0)
                for kk in range(k):
                    acc += Float64(xn_vals[mi * k + kk]) * Float64(Float32(w_vals[j * k + kk]) * wscale_vals[j])
                var got = hy[mi * n + j]
                var want = Float32(acc)
                var d = _abs32(got - want)
                if d > worst:
                    worst = d
                if d > 0.02:
                    print("    MISMATCH assign (", mi, ",", j, "): got", got, "want", want)
    print("  assign M=", m, "K=", k, "N=", n, " worst delta:", worst)
    return worst <= 0.02


def test_accum(ctx: DeviceContext, m: Int, k: Int, n: Int) raises -> Bool:
    var x_vals = List[Float32](capacity=m * k)
    for i in range(m * k):
        x_vals.append(Float32((i * 7 + 3) % 13) / 6.0 - 1.0)
    var w_vals = List[Int8](capacity=n * k)
    for i in range(n * k):
        w_vals.append(Int8((i * 11 + 5) % 17) - 8)
    var wscale_vals = List[Float32](capacity=n)
    for i in range(n):
        wscale_vals.append(Float32(0.01) + Float32(i % 5) * Float32(0.001))
    var y_init = List[Float32](capacity=m * n)
    for i in range(m * n):
        y_init.append(Float32((i * 3 + 1) % 9) / 4.0 - 1.0)

    var x_buf = ctx.enqueue_create_buffer[DType.float32](m * k)
    var w_buf = ctx.enqueue_create_buffer[DType.int8](n * k)
    var wscale_buf = ctx.enqueue_create_buffer[DType.float32](n)
    var y_buf = ctx.enqueue_create_buffer[DType.float32](m * n)
    with x_buf.map_to_host() as h:
        for i in range(m * k):
            h[i] = x_vals[i]
    with w_buf.map_to_host() as h:
        for i in range(n * k):
            h[i] = w_vals[i]
    with wscale_buf.map_to_host() as h:
        for i in range(n):
            h[i] = wscale_vals[i]
    with y_buf.map_to_host() as h:
        for i in range(m * n):
            h[i] = y_init[i]

    var grid = ((m + 31) // 32) * ((n + 31) // 32)
    ctx.enqueue_function[_gemm_accum_mma8x8](
        y_buf.unsafe_ptr(), x_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
        wscale_buf.unsafe_ptr(), Int64(m), Int64(k), Int64(n),
        grid_dim=grid, block_dim=256,
    )
    ctx.synchronize()

    var worst = Float32(0.0)
    with y_buf.map_to_host() as hy:
        for mi in range(m):
            for j in range(n):
                var acc = Float64(y_init[mi * n + j])
                for kk in range(k):
                    acc += Float64(x_vals[mi * k + kk]) * Float64(Float32(w_vals[j * k + kk]) * wscale_vals[j])
                var got = hy[mi * n + j]
                var want = Float32(acc)
                var d = _abs32(got - want)
                if d > worst:
                    worst = d
                if d > 0.02:
                    print("    MISMATCH accum (", mi, ",", j, "): got", got, "want", want)
    print("  accum  M=", m, "K=", k, "N=", n, " worst delta:", worst)
    return worst <= 0.02


def test_swiglu(ctx: DeviceContext, m: Int, k: Int, n_ff: Int) raises -> Bool:
    from std.math import exp as std_exp
    var xn_vals = List[Float32](capacity=m * k)
    for i in range(m * k):
        xn_vals.append(Float32((i * 7 + 3) % 13) / 6.0 - 1.0)
    var w_vals = List[Int8](capacity=2 * n_ff * k)
    for i in range(2 * n_ff * k):
        w_vals.append(Int8((i * 13 + 7) % 19) - 9)
    var wscale_vals = List[Float32](capacity=2 * n_ff)
    for i in range(2 * n_ff):
        wscale_vals.append(Float32(0.01) + Float32(i % 5) * Float32(0.001))

    var xn_buf = ctx.enqueue_create_buffer[DType.float32](m * k)
    var w_buf = ctx.enqueue_create_buffer[DType.int8](2 * n_ff * k)
    var wscale_buf = ctx.enqueue_create_buffer[DType.float32](2 * n_ff)
    var act_buf = ctx.enqueue_create_buffer[DType.float32](m * n_ff)
    with xn_buf.map_to_host() as h:
        for i in range(m * k):
            h[i] = xn_vals[i]
    with w_buf.map_to_host() as h:
        for i in range(2 * n_ff * k):
            h[i] = w_vals[i]
    with wscale_buf.map_to_host() as h:
        for i in range(2 * n_ff):
            h[i] = wscale_vals[i]

    var grid = ((m + 31) // 32) * ((n_ff + 31) // 32)
    ctx.enqueue_function[_swiglu_gemm_mma8x8](
        act_buf.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
        wscale_buf.unsafe_ptr(), Int64(m), Int64(k), Int64(n_ff),
        grid_dim=grid, block_dim=256,
    )
    ctx.synchronize()

    var worst = Float32(0.0)
    with act_buf.map_to_host() as ha:
        for mi in range(m):
            for j in range(n_ff):
                var gacc = Float64(0.0)
                var uacc = Float64(0.0)
                for kk in range(k):
                    var av = Float64(xn_vals[mi * k + kk])
                    gacc += av * Float64(Float32(w_vals[j * k + kk]) * wscale_vals[j])
                    uacc += av * Float64(Float32(w_vals[(n_ff + j) * k + kk]) * wscale_vals[n_ff + j])
                var sig = 1.0 / (1.0 + Float64(std_exp(Float32(-gacc))))
                var want = Float32(gacc * sig * uacc)
                var got = ha[mi * n_ff + j]
                var d = _abs32(got - want)
                if d > worst:
                    worst = d
                if d > 0.02:
                    print("    MISMATCH swiglu (", mi, ",", j, "): got", got, "want", want)
    print("  swiglu M=", m, "K=", k, "N_FF=", n_ff, " worst delta:", worst)
    return worst <= 0.02


def main() raises:
    var ctx = DeviceContext()

    var shapes = List[Tuple[Int, Int, Int]]()
    shapes.append((32, 32, 32))     # aligned control -- must still pass
    shapes.append((1, 17, 1))       # smallest possible: M=1, N=1
    shapes.append((5, 20, 7))       # M and N both smaller than one 8x8 subtile
    shapes.append((13, 33, 29))     # M, K, N all odd/non-multiples of 8
    shapes.append((24, 48, 50))     # M,N multiples of 8 but not 32; N straddles a tile boundary
    shapes.append((37, 16, 100))    # M just past one 32-tile; N spans 4 tiles with a partial tail
    shapes.append((33, 64, 33))     # M,N each exactly one past a 32-tile boundary

    var all_ok = True
    for i in range(len(shapes)):
        var s = shapes[i]
        var m = s[0]
        var k = s[1]
        var n = s[2]
        if not test_assign(ctx, m, k, n):
            all_ok = False
        if not test_accum(ctx, m, k, n):
            all_ok = False
        if not test_swiglu(ctx, m, k, n):
            all_ok = False

    if all_ok:
        print("PARTIAL-TILE CORRECTNESS PROBE: PASS (all shapes, all 3 kernels)")
    else:
        print("PARTIAL-TILE CORRECTNESS PROBE: FAIL")
