"""native_kv_decode_attn_splitk_f2s4_blob_driver.mojo -- feat/llama-q80gap (2026-08-13): forces
codegen of the d_head=64 4-KEY-STAGED SIMD-K split-K PARTIAL native-KV decode attention kernel
for blob extraction via `mojo build --emit object`, following
`native_kv_decode_attn_splitk_f2_blob_driver.mojo`'s exact pattern. CODEGEN TARGET:
`_native_kv_decode_splitk_partial_kernel_f2s4` -- the standalone A/B driver measured it 1.30x
f2u2 @1056 keys and 1.48x @2048 keys with BIT-IDENTICAL (m, l, o) partials, so it replaces f2u2
as the d_head=64 effective partial. `ctx.enqueue_function[kernel]` inside `main()` forces the
compiler to lower the kernel to AIR/metallib; no GPU dispatch needs to actually succeed. Lands in
the object file's `__TEXT,__const` as one `MTLB` blob.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build --emit object -I . -I ../attention_forge \
        -o /tmp/native_kv_decode_attn_splitk_f2s4_forge.o \
        ../attention_forge/native_kv_decode_attn_splitk_f2s4_blob_driver.mojo
    python3 tools/extract_blob.py /tmp/native_kv_decode_attn_splitk_f2s4_forge.o \
      ../attention_forge/generated/native_kv_decode_attn_splitk_f2s4_blob.c \
      --symbol algenta_native_kv_decode_attn_splitk_f2s4_blob
"""

from max.gpu.host import DeviceContext
from native_kv_decode_attn_splitk_f2s4 import _native_kv_decode_splitk_partial_kernel_f2s4


def main() raises:
    var ctx = DeviceContext()

    var h_q: Int64 = 4
    var h_kv: Int64 = 1
    var d_head: Int64 = 64
    var key_block_size: Int64 = 32
    var n_tok_k: Int64 = 64
    var n_blocks: Int64 = (n_tok_k + key_block_size - 1) // key_block_size  # = 2
    var n_splits: Int64 = 16

    var q_buf = ctx.enqueue_create_buffer[DType.float16](Int(h_q * d_head))
    var k_buf = ctx.enqueue_create_buffer[DType.float16](Int(h_kv * n_blocks * d_head * key_block_size))
    var v_buf = ctx.enqueue_create_buffer[DType.float16](Int(h_kv * n_blocks * key_block_size * d_head))
    var m_buf = ctx.enqueue_create_buffer[DType.float32](Int(h_q * n_splits))
    var l_buf = ctx.enqueue_create_buffer[DType.float32](Int(h_q * n_splits))
    var o_buf = ctx.enqueue_create_buffer[DType.float32](Int(h_q * n_splits * d_head))

    var scale64: Float64 = 1.0 / Float64(64) ** 0.5
    var scale: Float32 = Float32(scale64)

    ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f2s4](
        m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        n_tok_k, n_splits, h_q, h_kv, d_head, scale, key_block_size, n_blocks,
        grid_dim=Int(h_q * n_splits), block_dim=32,
    )
    print("NATIVE KV DECODE ATTN SPLITK F2S4 BLOB DRIVER: codegen forced")
