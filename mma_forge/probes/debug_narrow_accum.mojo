"""debug_narrow_accum.mojo -- minimal, single-tile repro to root-cause the real narrow-tile scalar
GEMM correctness bug in `_pf_gnrw_accum_kernel_i8` (mojo/engine/residentk/kernels.mojo), found while
re-running the Gate-0 kernel-diff suite on Mojo 1.0.0b2. Byte-identical kernel source to the
0.26.3-era version (only `fn`->`def` etc. syntax changed) previously passed this same diff test.

M=8, N=32, K=16 -- exactly ONE tile, ONE K-step, no partial-tile edge cases at all, so any
divergence here is the narrow kernel's OWN inner loop, not a tiling/boundary issue.

    cd mojo_env
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -D ALGENTA_GPU -I ../mojo/engine ../mma_forge/probes/debug_narrow_accum.mojo
"""
from max.gpu.host import DeviceContext
from residentk.kernels import _pf_gnrw_accum_kernel_i8

comptime M: Int = 8
comptime K: Int = 16
comptime N: Int = 32


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
    var y_init = List[Float32](capacity=M * N)
    for i in range(M * N):
        y_init.append(Float32((i * 3 + 1) % 9) / 4.0 - 1.0)

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
            h[i] = y_init[i]

    ctx.enqueue_function[_pf_gnrw_accum_kernel_i8](
        y_buf.unsafe_ptr(), x_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
        wscale_buf.unsafe_ptr(), M, K, N,
        grid_dim=1, block_dim=128,
    )
    ctx.synchronize()

    with y_buf.map_to_host() as hy:
        for mi in range(M):
            for j in range(N):
                var acc = Float64(y_init[mi * N + j])
                for kk in range(K):
                    acc += Float64(x_vals[mi * K + kk]) * Float64(Float32(w_vals[j * K + kk]) * wscale_vals[j])
                var got = hy[mi * N + j]
                var want = Float32(acc)
                var d = got - want
                if d < 0:
                    d = -d
                if d > 0.01:
                    print("MISMATCH (m=", mi, ",n=", j, "): got=", got, " want=", want,
                          " y_init=", y_init[mi * N + j])
    print("done")
