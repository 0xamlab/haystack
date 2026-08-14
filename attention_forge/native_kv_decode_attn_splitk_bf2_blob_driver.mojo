"""native_kv_decode_attn_splitk_bf2_blob_driver.mojo -- feat/batched-llama (2026-08-14): forces
codegen of the d_head=64 BATCHED split-K decode partial (`_native_kv_decode_splitk_partial_batched_
kernel_bf2u2`) for blob extraction via `mojo build --emit object`, following
`native_kv_decode_attn_splitk_batched_blob_driver.mojo`'s exact pattern. `ctx.enqueue_function[
kernel]` inside `main()` lowers the kernel to AIR/metallib; it lands in the object file's
`__TEXT,__const` as one `MTLB` blob. ONE function per blob for unambiguous discovery (the module
carries exactly one kernel).

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build --emit object -I . -I ../attention_forge \
        -o /tmp/native_kv_decode_attn_splitk_bf2_forge.o \
        ../attention_forge/native_kv_decode_attn_splitk_bf2_blob_driver.mojo
    python3 tools/extract_blob.py /tmp/native_kv_decode_attn_splitk_bf2_forge.o \
      ../attention_forge/generated/native_kv_decode_attn_splitk_bf2_blob.c \
      --symbol algenta_native_kv_decode_attn_splitk_bf2_blob
"""
from max.gpu.host import DeviceContext
from native_kv_decode_attn_splitk_bf2 import _native_kv_decode_splitk_partial_batched_kernel_bf2u2


def main() raises:
    var ctx = DeviceContext()

    var B: Int64 = 4
    var h_q: Int64 = 2
    var h_kv: Int64 = 1
    var d_head: Int64 = 64
    var key_block_size: Int64 = 32
    var n_tok_k: Int64 = 64
    var n_blocks: Int64 = (n_tok_k + key_block_size - 1) // key_block_size  # = 2
    var n_splits: Int64 = 16
    var kv_stride: Int64 = h_kv * n_blocks * d_head * key_block_size

    var q_buf = ctx.enqueue_create_buffer[DType.float16](Int(B * h_q * d_head))
    var k_buf = ctx.enqueue_create_buffer[DType.float16](Int(B * kv_stride))
    var v_buf = ctx.enqueue_create_buffer[DType.float16](Int(B * kv_stride))
    var nkeys_buf = ctx.enqueue_create_buffer[DType.int64](Int(B))
    var m_buf = ctx.enqueue_create_buffer[DType.float32](Int(B * h_q * n_splits))
    var l_buf = ctx.enqueue_create_buffer[DType.float32](Int(B * h_q * n_splits))
    var o_buf = ctx.enqueue_create_buffer[DType.float32](Int(B * h_q * n_splits * d_head))

    var scale64: Float64 = 1.0 / Float64(64) ** 0.5
    var scale: Float32 = Float32(scale64)

    ctx.enqueue_function[_native_kv_decode_splitk_partial_batched_kernel_bf2u2](
        m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        nkeys_buf.unsafe_ptr(), kv_stride,
        n_splits, h_q, h_kv, d_head, scale, key_block_size, n_blocks,
        grid_dim=Int(B * h_q * n_splits), block_dim=Int(32),
    )
    print("NATIVE KV DECODE ATTN SPLITK BF2 BLOB DRIVER: codegen forced (bf2u2 partial)")
