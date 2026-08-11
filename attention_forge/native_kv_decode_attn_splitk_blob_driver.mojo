"""native_kv_decode_attn_splitk_blob_driver.mojo -- forces codegen of the split-K PARTIAL native-
KV decode attention kernel -- as of the 2026-08-11 n_splits ceiling-sweep day the codegen target
is the 2-KEY-UNROLLED `_native_kv_decode_splitk_partial_kernel_f4u2` (the `_f4` original stays in
`native_kv_decode_attn_splitk.mojo` for A/B history but is NOT codegenned, so the blob's metallib
contains exactly ONE `native_kv_decode_attn_splitk*` function and discovery cannot ambiguous-match).
For blob extraction via `mojo build --emit object`, following `native_kv_decode_
attn_blob_driver.mojo`'s exact pattern (itself following `candidate_a_blob_driver.mojo`'s). No GPU
dispatch needs to actually succeed; `ctx.enqueue_function[kernel]` inside `main()` forces the
compiler to lower the kernel to AIR/metallib. Lands in the object file's `__TEXT,__const` as one
`MTLB` blob. Standalone, throwaway driver -- only its EXTRACTED BLOB gets linked into a real
binary (the session discovers it by the LONGER `native_kv_decode_attn_splitk` substring, checked
BEFORE the naive kernel's `native_kv_decode_attn` substring -- see `_MBQwen3I8AllSimd7Prefill.
__init__`'s discovery loop campaign addendum; the merge half is the engine's existing
`_splitk_merge_kernel_simd`, never a blob).

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build --emit object -I . -I ../attention_forge \
        -o /tmp/native_kv_decode_attn_splitk_forge.o \
        ../attention_forge/native_kv_decode_attn_splitk_blob_driver.mojo
    python3 tools/extract_blob.py /tmp/native_kv_decode_attn_splitk_forge.o \
      ../attention_forge/generated/native_kv_decode_attn_splitk_blob.c \
      --symbol algenta_native_kv_decode_attn_splitk_blob
"""
from max.gpu.host import DeviceContext
from native_kv_decode_attn_splitk import _native_kv_decode_splitk_partial_kernel_f4u2


def main() raises:
    var ctx = DeviceContext()

    var h_q: Int64 = 2
    var h_kv: Int64 = 1
    var d_head: Int64 = 128
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

    var scale64: Float64 = 1.0 / Float64(128) ** 0.5
    var scale: Float32 = Float32(scale64)

    ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f4u2](
        m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        n_tok_k, n_splits, h_q, h_kv, d_head, scale, key_block_size, n_blocks,
        grid_dim=Int(h_q * n_splits), block_dim=Int(d_head // 4),
    )
    print("NATIVE KV DECODE ATTN SPLITK F4U2 BLOB DRIVER: codegen forced")
