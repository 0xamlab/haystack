"""kvfuse_f2s4_decode_splitk_blob_driver.mojo -- feat/metal-beat (2026-08-23): forces codegen
of the kvprod-FUSED d64 split-K partial (`_native_kv_decode_splitk_partial_kernel_f2s4k`) for
blob extraction via `mojo build --emit object`, following
`native_kv_decode_attn_splitk_f2s4_blob_driver.mojo`'s exact pattern. The standalone driver
(kvfuse_f2s4_decode_splitk_driver.mojo) proved the partials BIT-IDENTICAL to the reference
kvprod+f2s4 pair (worst diff 0.0) and the cache append byte-exact, so the engine may prefer it
as the d64/qk0 effective partial and drop the per-layer kvprod dispatch. `ctx.enqueue_function
[kernel]` inside `main()` forces the compiler to lower the kernel to AIR/metallib; no GPU
dispatch needs to actually succeed. Lands in the object file's `__TEXT,__const` as one `MTLB`
blob.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build --emit object -I . -I ../attention_forge \
        -o /tmp/kvfuse_f2s4_decode_splitk_forge.o \
        ../attention_forge/kvfuse_f2s4_decode_splitk_blob_driver.mojo
    python3 tools/extract_blob.py /tmp/kvfuse_f2s4_decode_splitk_forge.o \
      ../attention_forge/generated/kvfuse_f2s4_decode_splitk_blob.c \
      --symbol algenta_kvfuse_f2s4_decode_splitk_blob
"""

from max.gpu.host import DeviceContext
from kvfuse_f2s4_decode_splitk import _native_kv_decode_splitk_partial_kernel_f2s4k


def main() raises:
    var ctx = DeviceContext()

    var h_q: Int64 = 4
    var h_kv: Int64 = 1
    var d_head: Int64 = 64
    var key_block_size: Int64 = 32
    var n_tok_k: Int64 = 64
    var n_blocks: Int64 = (n_tok_k + key_block_size - 1) // key_block_size  # = 2
    var n_splits: Int64 = 16
    var n_qkv: Int64 = (h_q + 2 * h_kv) * d_head
    var n_pairs: Int64 = d_head // 2

    var qkv_buf = ctx.enqueue_create_buffer[DType.float32](Int(n_qkv))
    var k_buf = ctx.enqueue_create_buffer[DType.float16](Int(h_kv * n_blocks * d_head * key_block_size))
    var v_buf = ctx.enqueue_create_buffer[DType.float16](Int(h_kv * n_blocks * key_block_size * d_head))
    var m_buf = ctx.enqueue_create_buffer[DType.float32](Int(h_q * n_splits))
    var l_buf = ctx.enqueue_create_buffer[DType.float32](Int(h_q * n_splits))
    var o_buf = ctx.enqueue_create_buffer[DType.float32](Int(h_q * n_splits * d_head))
    var cos_buf = ctx.enqueue_create_buffer[DType.float32](Int(n_tok_k * n_pairs))
    var sin_buf = ctx.enqueue_create_buffer[DType.float32](Int(n_tok_k * n_pairs))

    var scale64: Float64 = 1.0 / Float64(64) ** 0.5
    var scale: Float32 = Float32(scale64)

    ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f2s4k](
        m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
        qkv_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        n_tok_k, n_splits, h_q, h_kv, d_head, scale, key_block_size, n_blocks,
        cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(), n_tok_k - 1, Int64(0),
        grid_dim=Int(h_q * n_splits), block_dim=32,
    )
    print("KVFUSE F2S4 DECODE SPLITK BLOB DRIVER: codegen forced")
