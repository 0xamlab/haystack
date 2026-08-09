"""native_kv_producer_batched_blob_driver.mojo -- Project Slipstream Phase 3 (2026-08-09): forces
codegen of the batched KV producer (`_native_kv_producer_batched_kernel`) for blob extraction via
`mojo build --emit object`, following `native_kv_producer_blob_driver.mojo`'s exact pattern. Only
the EXTRACTED BLOB gets linked into a real binary (discovery must check the LONGER
`native_kv_producer_batched` substring BEFORE `native_kv_producer`).

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build --emit object -I . -I ../attention_forge \
        -o /tmp/native_kv_producer_batched_forge.o \
        ../attention_forge/native_kv_producer_batched_blob_driver.mojo
    python3 tools/extract_blob.py /tmp/native_kv_producer_batched_forge.o \
      ../attention_forge/generated/native_kv_producer_batched_blob.c \
      --symbol algenta_native_kv_producer_batched_blob
"""
from max.gpu.host import DeviceContext
from kvprod_batched import _native_kv_producer_batched_kernel


def main() raises:
    var ctx = DeviceContext()

    var B: Int64 = 4
    var h_q: Int64 = 2
    var h_kv: Int64 = 1
    var d_head: Int64 = 128
    var key_block_size: Int64 = 32
    var n_tok_k: Int64 = 64
    var n_blocks: Int64 = (n_tok_k + key_block_size - 1) // key_block_size  # = 2
    var kv_stride: Int64 = h_kv * n_blocks * d_head * key_block_size
    var n_qkv: Int64 = h_q * d_head + 2 * h_kv * d_head
    var n_pairs: Int64 = d_head // 2
    var max_pos: Int64 = 64

    var qkv_buf = ctx.enqueue_create_buffer[DType.float32](Int(B * n_qkv))
    var qn_buf = ctx.enqueue_create_buffer[DType.float32](Int(d_head))
    var kn_buf = ctx.enqueue_create_buffer[DType.float32](Int(d_head))
    var cos_buf = ctx.enqueue_create_buffer[DType.float32](Int((max_pos + 1) * n_pairs))
    var sin_buf = ctx.enqueue_create_buffer[DType.float32](Int((max_pos + 1) * n_pairs))
    var poss_buf = ctx.enqueue_create_buffer[DType.int64](Int(B))
    var qrot_buf = ctx.enqueue_create_buffer[DType.float16](Int(B * h_q * d_head))
    var k_buf = ctx.enqueue_create_buffer[DType.float16](Int(B * kv_stride))
    var v_buf = ctx.enqueue_create_buffer[DType.float16](Int(B * kv_stride))

    var eps: Float32 = 1.0e-6

    ctx.enqueue_function[_native_kv_producer_batched_kernel](
        qrot_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        qkv_buf.unsafe_ptr(), qn_buf.unsafe_ptr(), kn_buf.unsafe_ptr(),
        cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
        poss_buf.unsafe_ptr(), kv_stride,
        h_q, h_kv, d_head, key_block_size, n_blocks, eps,
        grid_dim=Int((h_q + h_kv) * B), block_dim=Int(d_head),
    )
    print("NATIVE KV PRODUCER BATCHED BLOB DRIVER: codegen forced")
