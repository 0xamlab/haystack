"""correctness_probe_narrow.mojo -- forge-native correctness check for `_gemm_accum_mma8x8_narrow`
(the BN=16 occupancy-tuning variant), against an independent Float64 CPU reference. M=32, K=32,
N=32 with BN_NARROW=16 gives n_tile_cols=2 -- exercises the multi-N-tile grid path, not just a
single tile.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . probes/correctness_probe_narrow.mojo
"""
from max.gpu.host import DeviceContext
from mm8 import _gemm_accum_mma8x8_narrow

comptime M: Int = 32
comptime K: Int = 32
comptime N: Int = 32


def _abs32(x: Float32) -> Float32:
    return -x if x < 0.0 else x


def main() raises:
    var ctx = DeviceContext()
    var x_vals = List[Float32](capacity=M * K)
    for i in range(M * K):
        x_vals.append(Float32((i * 7 + 3) % 13) / 6.0 - 1.0)
    var w_vals = List[Int8](capacity=N * K)
    for i in range(N * K):
        w_vals.append(Int8((i * 11 + 5) % 17) - 8)
    var wscale_vals = List[Float32](capacity=N)
    for i in range(N):
        wscale_vals.append(Float32(0.01) + Float32(i % 5) * Float32(0.001))
    var y_init_vals = List[Float32](capacity=M * N)
    for i in range(M * N):
        y_init_vals.append(Float32((i * 3 + 1) % 9) / 4.0 - 1.0)

    var x_buf = ctx.enqueue_create_buffer[DType.float32](M * K)
    var w_buf = ctx.enqueue_create_buffer[DType.int8](N * K)
    var wscale_buf = ctx.enqueue_create_buffer[DType.float32](N)
    var y_buf = ctx.enqueue_create_buffer[DType.float32](M * N)

    with x_buf.map_to_host() as h:
        for i in range(M * K):
            h[i] = x_vals[i]
    with w_buf.map_to_host() as h:
        for i in range(N * K):
            h[i] = w_vals[i]
    with wscale_buf.map_to_host() as h:
        for i in range(N):
            h[i] = wscale_vals[i]
    with y_buf.map_to_host() as h:
        for i in range(M * N):
            h[i] = y_init_vals[i]

    ctx.enqueue_function[_gemm_accum_mma8x8_narrow](
        y_buf.unsafe_ptr(), x_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
        wscale_buf.unsafe_ptr(), Int64(M), Int64(K), Int64(N),
        grid_dim=2, block_dim=256,
    )
    ctx.synchronize()

    var worst = Float32(0.0)
    with y_buf.map_to_host() as hy:
        for m in range(M):
            for j in range(N):
                var acc = Float64(y_init_vals[m * N + j])
                for kk in range(K):
                    var av = Float64(x_vals[m * K + kk])
                    var bv = Float64(Float32(w_vals[j * K + kk]) * wscale_vals[j])
                    acc += av * bv
                var got = hy[m * N + j]
                var want = Float32(acc)
                var d = _abs32(got - want)
                if d > worst:
                    worst = d
                if d > 0.01:
                    print("MISMATCH at (", m, ",", j, "): got", got, "want", want)
    print("gemm_accum_narrow worst delta:", worst)
    if worst <= 0.01:
        print("NARROW CORRECTNESS PROBE: PASS")
    else:
        print("NARROW CORRECTNESS PROBE: FAIL")
