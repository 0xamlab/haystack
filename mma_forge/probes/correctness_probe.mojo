"""correctness_probe.mojo -- forge-native correctness check for `_qkv_proj_gemm_mma8x8`, entirely
within the forge toolchain (own DeviceContext, no cross-toolchain extraction yet). Per the approved
plan: fix kernel bugs here first, before ever touching the blob-extraction/relink path.

M=32, K=32, N=32 (tile-aligned on all three axes -- avoids the Phase-1-deferred partial-tile M/N
padding entirely, and K=32 exercises TWO n_steps of BK=16 each, so the accumulate-across-steps path
is real, not vacuous). w is stored [N,K] row-major, int8, matching the scalar oracle exactly.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . probes/correctness_probe.mojo
"""
from max.gpu.host import DeviceContext
from mm8 import _qkv_proj_gemm_mma8x8

comptime _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
comptime _I8P = UnsafePointer[Int8, origin=MutAnyOrigin]

comptime M: Int = 32
comptime K: Int = 32
comptime N: Int = 32


def _abs32(x: Float32) -> Float32:
    return -x if x < 0.0 else x


def main() raises:
    var ctx = DeviceContext()

    var xn_vals = List[Float32](capacity=M * K)
    for i in range(M * K):
        xn_vals.append(Float32((i * 7 + 3) % 13) / 6.0 - 1.0)

    var w_vals = List[Int8](capacity=N * K)
    for i in range(N * K):
        w_vals.append(Int8((i * 11 + 5) % 17) - 8)

    var wscale_vals = List[Float32](capacity=N)
    for i in range(N):
        wscale_vals.append(Float32(0.01) + Float32(i % 5) * Float32(0.001))

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

    var n_tile_cols = (N + 32 - 1) // 32
    var n_tile_rows = (M + 32 - 1) // 32
    var grid = n_tile_cols * n_tile_rows

    ctx.enqueue_function[_qkv_proj_gemm_mma8x8](
        y_buf.unsafe_ptr(),
        xn_buf.unsafe_ptr(),
        w_buf.unsafe_ptr().bitcast[Int8](),
        wscale_buf.unsafe_ptr(),
        Int64(M), Int64(K), Int64(N),
        grid_dim=grid, block_dim=256,
    )
    ctx.synchronize()

    var worst = Float32(0.0)
    with y_buf.map_to_host() as hy:
        for m in range(M):
            for j in range(N):
                var acc = Float64(0.0)
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
                    print("MISMATCH at (", m, ",", j, "): got", got, "want", want)

    print("worst delta:", worst)
    if worst <= 0.01:
        print("QKV_PROJ MMA8x8 CORRECTNESS PROBE: PASS")
    else:
        print("QKV_PROJ MMA8x8 CORRECTNESS PROBE: FAIL")
