"""debug_assign_m1.mojo -- minimal repro for the wide _pf_gemm_assign_kernel_i8 divergence at
m_rows=1, k=1024, n=4096 (the exact Gate-0 test failure). Checks whether this shares the same
fault signature (some positions get zero contribution, others duplicated) as the narrow-accum bug
documented in kernels.mojo, or is a separate issue.

    cd mojo_env
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -D ALGENTA_GPU -I ../mojo/engine ../mma_forge/probes/debug_assign_m1.mojo
"""
from max.gpu.host import DeviceContext
from residentk.kernels import _pf_gemm_assign_kernel_i8

comptime M: Int = 1
comptime K: Int = 1024
comptime N: Int = 4096


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
    with y_buf.map_to_host() as h:
        for i in range(M * N):
            h[i] = Float32(-999.0)

    var n_tile_cols = (N + 31) // 32
    var n_tile_rows = (M + 31) // 32
    ctx.enqueue_function[_pf_gemm_assign_kernel_i8](
        y_buf.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
        wscale_buf.unsafe_ptr(), M, K, N,
        grid_dim=n_tile_rows * n_tile_cols, block_dim=256,
    )
    ctx.synchronize()

    var n_mismatch = 0
    var n_zero_delta = 0
    var n_double_delta = 0
    with y_buf.map_to_host() as hy:
        for j in range(N):
            var acc = Float64(0.0)
            for kk in range(K):
                acc += Float64(xn_vals[kk]) * Float64(Float32(w_vals[j * K + kk]) * wscale_vals[j])
            var got = hy[j]
            var want = Float32(acc)
            var d = got - want
            if d < 0:
                d = -d
            if d > 0.02:
                n_mismatch += 1
                if n_mismatch <= 5:
                    print("MISMATCH n=", j, ": got=", got, " want=", want)
                if _abs32(got) < 0.001:
                    n_zero_delta += 1
                elif _abs32(got - Float32(2.0) * want) < 0.02:
                    n_double_delta += 1
    print("total mismatches:", n_mismatch, "/ N=", N)
    print("zero-contribution mismatches:", n_zero_delta)
    print("~2x-contribution mismatches:", n_double_delta)


def _abs32(x: Float32) -> Float32:
    return -x if x < 0.0 else x
