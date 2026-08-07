"""mm8_driver.mojo -- forces codegen of the three PRODUCTION Phase 1/2 MMA kernels
(`_qkv_proj_gemm_mma8x8`, `_gemm_accum_mma8x8`, `_swiglu_gemm_mma8x8`) for blob extraction via
`mojo build --emit object`. Deliberately excludes `_gemm_accum_mma8x8_narrow` -- measured worse
than the wide kernel at every shape tried (see that kernel's own docstring) and never adopted; kept
correctness-verified in `mm8.mojo` as a real negative result, but never linked into the shipped
binary. No GPU dispatch needs to actually run for the object-emit step; `ctx.enqueue_function
[kernel]` inside `main()` is what forces the compiler to lower each kernel to AIR/metallib, exactly
as `mma_forge/abism.mojo`'s Phase-0 probe already proved. All three land in ONE object file's
`__TEXT,__const` as three separate `MTLB` blobs (`algenta_open_session`'s own scan loop already
handles back-to-back blobs -- Phase 0 mechanism, unmodified).

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build --emit object -I . -o /tmp/mm8_forge.o mm8_driver.mojo
    python3 tools/extract_blob.py /tmp/mm8_forge.o generated/mm8_blob.c --symbol algenta_mm8_blob
"""
from max.gpu.host import DeviceContext
from mm8 import _qkv_proj_gemm_mma8x8, _gemm_accum_mma8x8, _swiglu_gemm_mma8x8


def main() raises:
    var ctx = DeviceContext()
    var y_buf = ctx.enqueue_create_buffer[DType.float32](32 * 32)
    var xn_buf = ctx.enqueue_create_buffer[DType.float32](32 * 32)
    var w_buf = ctx.enqueue_create_buffer[DType.int8](64 * 32)
    var wscale_buf = ctx.enqueue_create_buffer[DType.float32](64)
    ctx.enqueue_function[_qkv_proj_gemm_mma8x8](
        y_buf.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
        wscale_buf.unsafe_ptr(), Int64(32), Int64(32), Int64(32),
        grid_dim=1, block_dim=256,
    )
    ctx.enqueue_function[_gemm_accum_mma8x8](
        y_buf.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
        wscale_buf.unsafe_ptr(), Int64(32), Int64(32), Int64(32),
        grid_dim=1, block_dim=256,
    )
    ctx.enqueue_function[_swiglu_gemm_mma8x8](
        y_buf.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr().bitcast[Int8](),
        wscale_buf.unsafe_ptr(), Int64(32), Int64(32), Int64(32),
        grid_dim=1, block_dim=256,
    )
    print("MM8 DRIVER: codegen forced")
