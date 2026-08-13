"""native_kv_decode_attn_splitk_f2_blob_driver.mojo -- feat/llama-native-deep (2026-08-13): forces
codegen of the d_head=64 split-K PARTIAL native-KV decode attention kernel for blob extraction
via `mojo build --emit object`, following `native_kv_decode_attn_splitk_blob_driver.mojo`'s exact
pattern. CODEGEN TARGET: the 2-KEY-UNROLLED `_native_kv_decode_splitk_partial_kernel_f2u2` --
the same day's interleaved e2e A/B measured it 1.086x the plain `_f2` at 1024-key depth (median
267.5 vs 246.3 tok/s, byte-identical greedy) and ~+3% at 256, so f2u2 ships as this blob's kernel
while `_f2` stays in the module for A/B history (EXACTLY the f4/f4u2 precedent of the d_head=128
blob: one function per blob keeps discovery unambiguous -- the session checks the LONGER
`native_kv_decode_attn_splitk_f2` substring BEFORE the generic `native_kv_decode_attn_splitk`
one). `ctx.enqueue_function[kernel]` inside `main()` forces the compiler to lower the kernel to
AIR/metallib; no GPU dispatch needs to actually succeed. Lands in the object file's
`__TEXT,__const` as one `MTLB` blob.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build --emit object -I . -I ../attention_forge \
        -o /tmp/native_kv_decode_attn_splitk_f2_forge.o \
        ../attention_forge/native_kv_decode_attn_splitk_f2_blob_driver.mojo
    python3 tools/extract_blob.py /tmp/native_kv_decode_attn_splitk_f2_forge.o \
      ../attention_forge/generated/native_kv_decode_attn_splitk_f2_blob.c \
      --symbol algenta_native_kv_decode_attn_splitk_f2_blob
"""
from max.gpu.host import DeviceContext
from native_kv_decode_attn_splitk_f2 import _native_kv_decode_splitk_partial_kernel_f2u2


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

    ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f2u2](
        m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        n_tok_k, n_splits, h_q, h_kv, d_head, scale, key_block_size, n_blocks,
        grid_dim=Int(h_q * n_splits), block_dim=32,
    )
    print("NATIVE KV DECODE ATTN SPLITK F2U2 BLOB DRIVER: codegen forced")
